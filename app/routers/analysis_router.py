# api_gateway_service/app/routers/analysis_router.py
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from typing import Any, Optional, List, Union, Dict
from datetime import datetime
from loguru import logger
import json
import asyncpg

from app.security import get_current_username
from app.db_connector import fetch_data
from app.config import settings
from app.models import (
    ZScoreResultAPI, MovingAverageResultAPI, STLDecompositionAPI, BasicStatsAPI,
    TimeSeriesPoint, ZScorePointAPI, MovingAveragePointAPI, STLComponentAPI,
    TimeSeriesRequestParams
)
from app.cache_manager import async_cache_decorator

router = APIRouter(
    prefix="/analysis",
    tags=["Pre-computed Analysis Results"],
    dependencies=[Depends(get_current_username)]
)

ANALYSIS_TYPES_DB_MAP = {
    "zscore": "z_score",
    "movingaverage": "moving_average",
    "stldecomposition": "stl_decomposition",
    "basicstats": "basic_stats",
    "rateofchange": "rate_of_change",
    "percentchange": "percent_change"
}

# --- Parsers for specific analysis types ---
def _parse_zscore_result(db_record: asyncpg.Record) -> Optional[ZScoreResultAPI]:
    data_str = db_record.get('result_structured_jsonb')
    metadata_str = db_record.get('metadata')
    data = None
    metadata = None

    if isinstance(data_str, str):
        try: data = json.loads(data_str)
        except json.JSONDecodeError: logger.warning(f"ZScore: Failed to parse result_structured_jsonb: {data_str}"); return None
    elif isinstance(data_str, dict): data = data_str
    else: logger.warning(f"ZScore: result_structured_jsonb is None or not a string/dict: {type(data_str)}"); return None

    if isinstance(metadata_str, str):
        try: metadata = json.loads(metadata_str)
        except json.JSONDecodeError: logger.warning(f"ZScore: Failed to parse metadata JSONB: {metadata_str}") # Continue with metadata as None
    elif isinstance(metadata_str, dict): metadata = metadata_str

    if isinstance(data, dict) and "points" in data:
        try:
            valid_points = []
            points_data = data.get("points", [])
            if not isinstance(points_data, list):
                logger.warning(f"ZScore: 'points' data is not a list: {type(points_data)}. Record: {db_record.get('original_signal_name')}")
                return None
            for p_item in points_data:
                if isinstance(p_item, dict):
                    valid_points.append(ZScorePointAPI(**p_item))
                else: logger.warning(f"ZScore: Invalid item type in points list: {type(p_item)}. Item: {p_item}")
            
            if not valid_points and points_data:
                 logger.error(f"ZScore: No valid points found after checking points list for {db_record.get('original_signal_name')}")
                 return None

            return ZScoreResultAPI(points=valid_points, window=data.get("window"), metadata=metadata)
        except Exception as e:
            logger.error(f"ZScore: Error creating ZScoreResultAPI model for {db_record.get('original_signal_name')}: {e}. Data: {data}", exc_info=True)
            return None
    logger.warning(f"ZScore: Could not form ZScoreResultAPI for {db_record.get('original_signal_name')}. Data type: {type(data)}")
    return None

def _parse_ma_result(db_record: asyncpg.Record) -> Optional[MovingAverageResultAPI]:
    data_str = db_record.get('result_series_jsonb')
    params_str = db_record.get('parameters')
    metadata_str = db_record.get('metadata')
    
    data = None
    params = {} # Default to empty dict
    metadata = None

    # Parse data for moving_average_signal
    if isinstance(data_str, str):
        try: data = json.loads(data_str)
        except json.JSONDecodeError: logger.warning(f"MA: Failed to parse result_series_jsonb: {data_str}"); return None
    elif isinstance(data_str, dict): data = data_str
    else: logger.warning(f"MA: result_series_jsonb is None or not a string/dict: {type(data_str)} for signal {db_record.get('original_signal_name')}"); return None

    # Parse parameters
    if isinstance(params_str, str):
        try: params = json.loads(params_str)
        except json.JSONDecodeError: logger.warning(f"MA: Failed to parse parameters JSONB: {params_str}. Using default params.")
    elif isinstance(params_str, dict): params = params_str
    # If params_str is None, params remains default {}

    # Parse metadata
    if isinstance(metadata_str, str):
        try: metadata = json.loads(metadata_str)
        except json.JSONDecodeError: logger.warning(f"MA: Failed to parse metadata JSONB: {metadata_str}")
    elif isinstance(metadata_str, dict): metadata = metadata_str

    # Validate structure and create Pydantic model
    if isinstance(data, dict) and "points" in data and isinstance(params, dict):
        try:
            valid_points = []
            points_data_list = data.get("points", [])
            if not isinstance(points_data_list, list):
                logger.warning(f"MA: 'points' in result_series_jsonb is not a list: {type(points_data_list)} for signal {db_record.get('original_signal_name')}")
                return None
            
            for p_item in points_data_list:
                if isinstance(p_item, dict):
                    valid_points.append(MovingAveragePointAPI(**p_item))
                else:
                    logger.warning(f"MA: Invalid item type in points list: {type(p_item)}. Item: {p_item} for signal {db_record.get('original_signal_name')}")
            
            # If points_data_list was not empty but valid_points is, it means all items were invalid
            if not valid_points and points_data_list:
                 logger.error(f"MA: No valid points found after checking list items for signal {db_record.get('original_signal_name')}")
                 return None

            # Log final values before Pydantic model creation for MA
            logger.debug(f"MA: Attempting Pydantic model creation for signal {db_record.get('original_signal_name')}")
            logger.debug(f"MA: Points for model: {valid_points}")
            logger.debug(f"MA: Window from params: {params.get('window', settings.DEFAULT_MOVING_AVERAGE_WINDOW)}")
            logger.debug(f"MA: Type from params: {params.get('type', 'simple')}")
            logger.debug(f"MA: Metadata for model: {metadata}")

            return MovingAverageResultAPI(
                points=valid_points,
                window=params.get("window", settings.DEFAULT_MOVING_AVERAGE_WINDOW),
                type=params.get("type", "simple"),
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"MA: Error creating MovingAverageResultAPI model for {db_record.get('original_signal_name')}: {e}. Data: {data}, Params: {params}", exc_info=True)
            return None
    
    logger.warning(f"MA: Could not form MovingAverageResultAPI for {db_record.get('original_signal_name')}. Data type: {type(data)}, Data content: {str(data)[:200]}, Params type: {type(params)}, Params content: {params}")
    return None

def _parse_stl_result(db_record: asyncpg.Record) -> Optional[STLDecompositionAPI]:
    data_str = db_record.get('result_structured_jsonb')
    metadata_str = db_record.get('metadata')
    data = None
    metadata = None

    if isinstance(data_str, str):
        try: data = json.loads(data_str)
        except json.JSONDecodeError: logger.warning(f"STL: Failed to parse result_structured_jsonb: {data_str}"); return None
    elif isinstance(data_str, dict): data = data_str
    else: logger.warning(f"STL: result_structured_jsonb is None or not a string/dict: {type(data_str)}"); return None

    if isinstance(metadata_str, str):
        try: metadata = json.loads(metadata_str)
        except json.JSONDecodeError: logger.warning(f"STL: Failed to parse metadata JSONB: {metadata_str}")
    elif isinstance(metadata_str, dict): metadata = metadata_str

    if isinstance(data, dict) and all(k in data for k in ["trend", "seasonal", "residual", "original_timestamps"]):
        try:
            original_timestamps_parsed = []
            ots_data = data.get('original_timestamps', [])
            if not isinstance(ots_data, list):
                logger.warning(f"STL: 'original_timestamps' not a list: {type(ots_data)} for {db_record.get('original_signal_name')}")
                return None
            for ts_str in ots_data:
                try: original_timestamps_parsed.append(datetime.fromisoformat(str(ts_str).replace("Z", "+00:00")))
                except (ValueError, AttributeError): logger.warning(f"STL: Could not parse timestamp '{ts_str}'."); original_timestamps_parsed.append(None)

            trend_data = data.get('trend', [])
            seasonal_data = data.get('seasonal', [])
            residual_data = data.get('residual', [])

            if not (isinstance(trend_data, list) and isinstance(seasonal_data, list) and isinstance(residual_data, list)):
                logger.warning(f"STL: Trend, seasonal, or residual data is not a list for {db_record.get('original_signal_name')}.")
                return None

            min_len = min(len(original_timestamps_parsed), len(trend_data), len(seasonal_data), len(residual_data))

            return STLDecompositionAPI(
                trend=[STLComponentAPI(timestamp=original_timestamps_parsed[i], value=trend_data[i]) for i in range(min_len) if original_timestamps_parsed[i] is not None],
                seasonal=[STLComponentAPI(timestamp=original_timestamps_parsed[i], value=seasonal_data[i]) for i in range(min_len) if original_timestamps_parsed[i] is not None],
                residual=[STLComponentAPI(timestamp=original_timestamps_parsed[i], value=residual_data[i]) for i in range(min_len) if original_timestamps_parsed[i] is not None],
                period_used=data.get("period_used"),
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"STL: Error creating STLDecompositionAPI model for {db_record.get('original_signal_name')}: {e}. Data: {data}", exc_info=True)
            return None
    logger.warning(f"STL: Could not form STLDecompositionAPI for {db_record.get('original_signal_name')}. Data type: {type(data)}")
    return None

def _parse_basic_stats_result(db_record: asyncpg.Record) -> Optional[BasicStatsAPI]:
    data_str = db_record.get('result_structured_jsonb')
    metadata_str = db_record.get('metadata')
    data = None
    metadata = None

    if isinstance(data_str, str):
        try: data = json.loads(data_str)
        except json.JSONDecodeError: logger.warning(f"BasicStats: Failed to parse result_structured_jsonb: {data_str}"); return None
    elif isinstance(data_str, dict): data = data_str
    else: logger.warning(f"BasicStats: result_structured_jsonb is None or not a string/dict: {type(data_str)}"); return None
    
    if isinstance(metadata_str, str):
        try: metadata = json.loads(metadata_str)
        except json.JSONDecodeError: logger.warning(f"BasicStats: Failed to parse metadata JSONB: {metadata_str}")
    elif isinstance(metadata_str, dict): metadata = metadata_str

    if isinstance(data, dict) and all(k in data for k in ["count", "mean", "median", "min_val", "max_val", "std_dev", "variance"]):
        try:
            # Ensure all required numeric fields are actually numbers
            for key in ["count", "sum_val", "mean", "median", "min_val", "max_val", "std_dev", "variance"]:
                if key in data and not isinstance(data[key], (int, float)):
                    logger.warning(f"BasicStats: Field '{key}' is not numeric: {data[key]} (type: {type(data[key])}) for {db_record.get('original_signal_name')}")
                    # Attempt conversion or return None
                    try: data[key] = float(data[key])
                    except (ValueError, TypeError): return None
            
            return BasicStatsAPI(**data, metadata=metadata)
        except Exception as e:
            logger.error(f"BasicStats: Error creating BasicStatsAPI model for {db_record.get('original_signal_name')}: {e}. Data: {data}", exc_info=True)
            return None
    logger.warning(f"BasicStats: Could not form BasicStatsAPI for {db_record.get('original_signal_name')}. Missing keys or data not dict. Data: {data}")
    return None

def _parse_simple_timeseries_result(db_record: asyncpg.Record, analysis_name: str) -> Optional[List[TimeSeriesPoint]]:
    data_str = db_record.get('result_series_jsonb')
    data = None

    if isinstance(data_str, str):
        try: data = json.loads(data_str)
        except json.JSONDecodeError: logger.warning(f"{analysis_name}: Failed to parse result_series_jsonb: {data_str}"); return None
    elif isinstance(data_str, dict): data = data_str
    else: logger.warning(f"{analysis_name}: result_series_jsonb is None or not a string/dict: {type(data_str)}"); return None

    if isinstance(data, dict) and "points" in data:
        try:
            valid_points = []
            points_data_list = data.get("points", [])
            if not isinstance(points_data_list, list):
                logger.warning(f"{analysis_name}: 'points' data is not a list: {type(points_data_list)} for {db_record.get('original_signal_name')}")
                return None

            for p_item in points_data_list:
                if isinstance(p_item, dict):
                    valid_points.append(TimeSeriesPoint(**p_item))
                else:
                    logger.warning(f"{analysis_name}: Invalid item type in points list: {type(p_item)}. Item: {p_item}")
            
            if not valid_points and points_data_list:
                 logger.error(f"{analysis_name}: No valid points found after checking points list for {db_record.get('original_signal_name')}")
                 return None
            return valid_points
        except Exception as e:
            logger.error(f"{analysis_name}: Error creating List[TimeSeriesPoint] for {db_record.get('original_signal_name')}: {e}. Data: {data}", exc_info=True)
            return None
    logger.warning(f"{analysis_name}: Could not form List[TimeSeriesPoint] for {db_record.get('original_signal_name')}. Data: {data}")
    return None


PARSER_MAP = {
    "z_score": _parse_zscore_result,
    "moving_average": _parse_ma_result,
    "stl_decomposition": _parse_stl_result,
    "basic_stats": _parse_basic_stats_result,
    "rate_of_change": lambda rec: _parse_simple_timeseries_result(rec, "RateOfChange"),
    "percent_change": lambda rec: _parse_simple_timeseries_result(rec, "PercentChange")
}
RESPONSE_MODEL_MAP = {
    "z_score": ZScoreResultAPI,
    "moving_average": MovingAverageResultAPI,
    "stl_decomposition": STLDecompositionAPI,
    "basic_stats": BasicStatsAPI,
    "rate_of_change": List[TimeSeriesPoint],
    "percent_change": List[TimeSeriesPoint]
}

@router.get(
    "/{analysis_type_path}/{original_signal_name}",
    summary="Get Pre-computed Time Series Analysis Result",
    response_model=Union[ZScoreResultAPI, MovingAverageResultAPI, STLDecompositionAPI, BasicStatsAPI, List[TimeSeriesPoint], Dict[str, Any]]
)
@async_cache_decorator(ttl_seconds=900)
async def get_precomputed_analysis_result(
    analysis_type_path: str = Path(..., description=f"Type of analysis. Supported: {', '.join(ANALYSIS_TYPES_DB_MAP.keys())}"),
    original_signal_name: str = Path(..., description="Name of the original signal, e.g., 'topic_5_document_count'"),
    start_time: datetime = Query(..., description="Start of the time range for analysis_timestamp"),
    end_time: datetime = Query(..., description="End of the time range for analysis_timestamp"),
    latest_only: bool = Query(True, description="If true, fetches only the most recent analysis result within the time range.")
):
    analysis_type_db_key = analysis_type_path.lower()
    analysis_type_db_value = ANALYSIS_TYPES_DB_MAP.get(analysis_type_db_key)

    if not analysis_type_db_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid analysis type path: {analysis_type_path}. Supported: {list(ANALYSIS_TYPES_DB_MAP.keys())}")

    table_name = f"\"{settings.ANALYSIS_RESULTS_TABLE_PREFIX}_{analysis_type_db_value}\""
    
    order_by_clause = "ORDER BY analysis_timestamp DESC" if latest_only else "ORDER BY analysis_timestamp ASC"
    limit_clause = "LIMIT 1" if latest_only else ""

    query = f"""
        SELECT "original_signal_name", "analysis_type", "parameters", 
               "result_value_numeric", "result_series_jsonb", "result_structured_jsonb", "metadata"
        FROM {table_name}
        WHERE "original_signal_name" = $1 
          AND "analysis_type" = $2 
          AND "analysis_timestamp" >= $3 
          AND "analysis_timestamp" <= $4
        {order_by_clause}
        {limit_clause}; 
    """
    
    logger.debug(f"AnalysisRouter: Querying {table_name} for signal '{original_signal_name}', type '{analysis_type_db_value}' between {start_time} and {end_time}")
    db_records = await fetch_data(query, original_signal_name, analysis_type_db_value, start_time, end_time)
    
    if not db_records:
        logger.warning(f"AnalysisRouter: No records found for {analysis_type_path} on signal '{original_signal_name}'.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No pre-computed '{analysis_type_path}' analysis found for signal '{original_signal_name}' in the time range.")

    parser_func = PARSER_MAP.get(analysis_type_db_value)
    # This should always find a parser because analysis_type_db_value is validated from ANALYSIS_TYPES_DB_MAP
    # which should have a corresponding key in PARSER_MAP.

    if latest_only:
        logger.debug(f"AnalysisRouter: Parsing latest record for {analysis_type_path} on '{original_signal_name}'. Record: {dict(db_records[0]) if db_records else 'None'}")
        parsed_result = parser_func(db_records[0])
        if parsed_result:
            return parsed_result
    else: 
        parsed_results_list = []
        for i, record in enumerate(db_records):
            logger.debug(f"AnalysisRouter: Parsing record {i} for {analysis_type_path} on '{original_signal_name}'. Record: {dict(record)}")
            parsed = parser_func(record)
            if parsed:
                parsed_results_list.append(parsed)
        if parsed_results_list:
            return parsed_results_list
        
    logger.error(f"AnalysisRouter: Could not parse ANY stored analysis result for '{analysis_type_path}', signal '{original_signal_name}'. Last raw record (if any): {dict(db_records[-1]) if db_records else 'None'}")
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error parsing stored analysis result for '{analysis_type_path}'.")