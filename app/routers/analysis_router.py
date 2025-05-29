# api_gateway_service/app/routers/analysis_router.py
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse
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
    TimeSeriesRequestParams, TimeSeriesData # Ensure TimeSeriesData is imported
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

def _parse_json_field(db_record: asyncpg.Record, field_name: str, signal_name_for_log: str, parser_type_log: str) -> Optional[Any]:
    field_value = db_record.get(field_name)
    if field_value is None:
        # logger.trace(f"{parser_type_log} Parser: Field '{field_name}' is NULL in DB for signal '{signal_name_for_log}'.")
        return None
    if isinstance(field_value, (dict, list)): # Already parsed by asyncpg potentially
        return field_value
    if isinstance(field_value, str):
        try:
            return json.loads(field_value)
        except json.JSONDecodeError:
            logger.warning(f"{parser_type_log} Parser: Failed to parse JSON string for field '{field_name}', signal '{signal_name_for_log}'. Content: '{field_value[:200]}'")
            return None
    logger.warning(f"{parser_type_log} Parser: Field '{field_name}' is not a string, dict, or list for signal '{signal_name_for_log}'. Type: {type(field_value)}. Value: {repr(field_value)[:200]}")
    return None

def _validate_points_list(points_data_list: Any, PointModel: Any, signal_name_for_log: str, parser_type_log: str) -> Optional[List[Any]]:
    if not isinstance(points_data_list, list):
        logger.warning(f"{parser_type_log} Parser: 'points' data is not a list for signal '{signal_name_for_log}'. Type: {type(points_data_list)}")
        return None
    
    valid_points = []
    for i, p_item in enumerate(points_data_list):
        if isinstance(p_item, dict):
            try:
                valid_points.append(PointModel(**p_item))
            except Exception as e_point:
                logger.warning(f"{parser_type_log} Parser: Error creating {PointModel.__name__} for point {i} of signal '{signal_name_for_log}'. Error: {repr(e_point)}. Item: {repr(p_item)}")
        else:
            logger.warning(f"{parser_type_log} Parser: Invalid item type in points list (index {i}) for signal '{signal_name_for_log}'. Type: {type(p_item)}. Item: {repr(p_item)}")
    
    if not valid_points and points_data_list: # points_data_list was not empty, but all items failed validation/parsing
         logger.error(f"{parser_type_log} Parser: No valid points constructed for signal '{signal_name_for_log}'. Original points: {repr(points_data_list)[:500]}")
         return None
    return valid_points


def _parse_zscore_result(db_record: asyncpg.Record) -> Optional[ZScoreResultAPI]:
    signal_name_for_log = db_record.get('original_signal_name', 'UnknownSignal')
    parser_type_log = "ZScore"
    data = _parse_json_field(db_record, 'result_structured_jsonb', signal_name_for_log, parser_type_log)
    metadata_from_db = _parse_json_field(db_record, 'metadata', signal_name_for_log, parser_type_log)

    if not isinstance(data, dict):
        logger.warning(f"{parser_type_log} Parser: Main data is not a dict for signal '{signal_name_for_log}'. Data: {repr(data)[:200]}")
        return None
        
    points_data = data.get("points")
    valid_points = _validate_points_list(points_data, ZScorePointAPI, signal_name_for_log, parser_type_log)
    if valid_points is None and points_data is not None : # If points_data existed but _validate_points_list returned None (all failed)
        return None

    try:
        return ZScoreResultAPI(points=valid_points or [], window=data.get("window"), metadata=metadata_from_db)
    except Exception as e:
        logger.error(f"{parser_type_log} Parser Error creating ZScoreResultAPI for '{signal_name_for_log}': {repr(e)}", exc_info=True)
        logger.debug(f"Problematic data for ZScore '{signal_name_for_log}': data={repr(data)}, metadata={repr(metadata_from_db)}")
        return None

def _parse_ma_result(db_record: asyncpg.Record) -> Optional[MovingAverageResultAPI]:
    signal_name_for_log = db_record.get('original_signal_name', 'UnknownSignal')
    parser_type_log = "MA"
    data = _parse_json_field(db_record, 'result_series_jsonb', signal_name_for_log, parser_type_log)
    params = _parse_json_field(db_record, 'parameters', signal_name_for_log, parser_type_log)
    metadata_from_db = _parse_json_field(db_record, 'metadata', signal_name_for_log, parser_type_log)

    if not isinstance(data, dict):
        logger.warning(f"{parser_type_log} Parser: Main data (from result_series_jsonb) is not a dict for signal '{signal_name_for_log}'. Data: {repr(data)[:200]}")
        return None
    if params is None or not isinstance(params, dict): params = {}
        
    points_data = data.get("points")
    valid_points = _validate_points_list(points_data, MovingAveragePointAPI, signal_name_for_log, parser_type_log)
    if valid_points is None and points_data is not None: return None

    try:
        window_val = params.get("window", settings.DEFAULT_MOVING_AVERAGE_WINDOW)
        type_val = params.get("type", "simple")
        return MovingAverageResultAPI(points=valid_points or [], window=window_val, type=type_val, metadata=metadata_from_db)
    except Exception as e:
        logger.error(f"{parser_type_log} Parser Error creating MovingAverageResultAPI for '{signal_name_for_log}': {repr(e)}", exc_info=True)
        logger.debug(f"Problematic data for MA '{signal_name_for_log}': data={repr(data)}, params={repr(params)}, metadata={repr(metadata_from_db)}")
        return None

def _parse_stl_result(db_record: asyncpg.Record) -> Optional[STLDecompositionAPI]:
    signal_name_for_log = db_record.get('original_signal_name', 'UnknownSignal')
    parser_type_log = "STL"
    data = _parse_json_field(db_record, 'result_structured_jsonb', signal_name_for_log, parser_type_log)
    metadata_from_db = _parse_json_field(db_record, 'metadata', signal_name_for_log, parser_type_log)
    required_keys = ["trend", "seasonal", "residual", "original_timestamps"]
    if not isinstance(data, dict) or not all(k in data for k in required_keys):
        logger.warning(f"{parser_type_log} Parser: Invalid 'data' or missing keys for signal '{signal_name_for_log}'. Data: {repr(data)[:200]}")
        return None
    try:
        original_timestamps_parsed = [datetime.fromisoformat(str(ts_str).replace("Z", "+00:00")) if isinstance(ts_str, str) else None for ts_str in data.get('original_timestamps', [])]
        trend_list, seasonal_list, residual_list = data.get('trend', []), data.get('seasonal', []), data.get('residual', [])
        min_len = min(len(original_timestamps_parsed), len(trend_list), len(seasonal_list), len(residual_list))
        
        def create_stl_points(timestamps, values):
            points = []
            for i in range(min_len):
                if timestamps[i] and values[i] is not None: # Check value is not None
                    points.append(STLComponentAPI(timestamp=timestamps[i], value=values[i]))
            return points

        valid_trend = create_stl_points(original_timestamps_parsed, trend_list)
        valid_seasonal = create_stl_points(original_timestamps_parsed, seasonal_list)
        valid_residual = create_stl_points(original_timestamps_parsed, residual_list)
        
        return STLDecompositionAPI(
            trend=valid_trend, seasonal=valid_seasonal, residual=valid_residual,
            period_used=data.get("period_used"), metadata=metadata_from_db
        )
    except Exception as e:
        logger.error(f"{parser_type_log} Parser Error for '{signal_name_for_log}': {repr(e)}", exc_info=True)
        logger.debug(f"Problematic data for STL '{signal_name_for_log}': {repr(data)}")
        return None

def _parse_basic_stats_result(db_record: asyncpg.Record) -> Optional[BasicStatsAPI]:
    signal_name_for_log = db_record.get('original_signal_name', 'UnknownSignal')
    parser_type_log = "BasicStats"
    data = _parse_json_field(db_record, 'result_structured_jsonb', signal_name_for_log, parser_type_log)
    metadata_from_db = _parse_json_field(db_record, 'metadata', signal_name_for_log, parser_type_log)
    required_keys = ["count", "sum_val", "mean", "median", "min_val", "max_val", "std_dev", "variance"]
    if not isinstance(data, dict) or not all(k in data for k in required_keys):
        logger.warning(f"{parser_type_log} Parser: Invalid 'data' or missing keys for signal '{signal_name_for_log}'. Missing: {set(required_keys) - set(data.keys() if isinstance(data, dict) else [])}. Data: {repr(data)[:200]}")
        return None
    try:
        for key in required_keys:
            if data[key] is None: # Explicitly handle if a required numeric key is None
                logger.error(f"{parser_type_log} Parser: Required numeric field '{key}' is None for '{signal_name_for_log}'.")
                return None
            if not isinstance(data[key], (int, float)):
                try: data[key] = float(data[key])
                except (ValueError, TypeError): logger.error(f"{parser_type_log} Parser: Cannot convert {key} to float for '{signal_name_for_log}'. Value: {data[key]}"); return None
        return BasicStatsAPI(**data, metadata=metadata_from_db)
    except Exception as e:
        logger.error(f"{parser_type_log} Parser Error for '{signal_name_for_log}': {repr(e)}", exc_info=True)
        logger.debug(f"Problematic data for BasicStats '{signal_name_for_log}': {repr(data)}")
        return None

def _parse_simple_timeseries_result(db_record: asyncpg.Record, analysis_name_log_prefix: str) -> Optional[TimeSeriesData]:
    signal_name_for_log = db_record.get('original_signal_name', 'UnknownSignal')
    parser_type_log = analysis_name_log_prefix
    data = _parse_json_field(db_record, 'result_series_jsonb', signal_name_for_log, parser_type_log)

    if not isinstance(data, dict):
        logger.warning(f"{parser_type_log} Parser: Main data (from result_series_jsonb) is not a dict for signal '{signal_name_for_log}'. Data: {repr(data)[:200]}")
        return None
        
    points_data = data.get("points")
    signal_name_from_data = data.get("signal_name")
    metadata_from_data = data.get("metadata")

    if points_data is None or signal_name_from_data is None:
        logger.warning(f"{parser_type_log} Parser: 'data' (from result_series_jsonb) missing 'points' or 'signal_name' for signal '{signal_name_for_log}'. Data: {repr(data)[:200]}")
        return None

    valid_points = _validate_points_list(points_data, TimeSeriesPoint, signal_name_for_log, parser_type_log)
    if valid_points is None and points_data is not None: return None

    try:
        return TimeSeriesData(signal_name=signal_name_from_data, points=valid_points or [], metadata=metadata_from_data or {})
    except Exception as e:
        logger.error(f"{parser_type_log} Parser: Error creating TimeSeriesData for '{signal_name_for_log}'. Error: {repr(e)}", exc_info=True)
        logger.debug(f"Problematic data for {parser_type_log} '{signal_name_for_log}': {repr(data)}")
        return None

PARSER_MAP = {
    "z_score": _parse_zscore_result,
    "moving_average": _parse_ma_result,
    "stl_decomposition": _parse_stl_result,
    "basic_stats": _parse_basic_stats_result,
    "rate_of_change": lambda rec: _parse_simple_timeseries_result(rec, "RoC"),
    "percent_change": lambda rec: _parse_simple_timeseries_result(rec, "PctChange")
}

@router.get(
    "/{analysis_type_path}/{original_signal_name}",
    summary="Get Pre-computed Time Series Analysis Result",
    response_model=Union[
        ZScoreResultAPI, MovingAverageResultAPI, STLDecompositionAPI, BasicStatsAPI,
        TimeSeriesData, 
        List[ZScoreResultAPI], List[MovingAverageResultAPI], List[STLDecompositionAPI], List[BasicStatsAPI],
        List[TimeSeriesData],
        Dict[str, Any]
    ]
)
@async_cache_decorator(ttl_seconds=900)
async def get_precomputed_analysis_result(
    analysis_type_path: str = Path(..., description=f"Type of analysis. Supported: {', '.join(ANALYSIS_TYPES_DB_MAP.keys())}"),
    original_signal_name: str = Path(..., description="Name of the original signal, e.g., 'topic_5_document_count'"),
    start_time: datetime = Query(..., description="Start of the time range for analysis_timestamp (ISO format)"),
    end_time: datetime = Query(..., description="End of the time range for analysis_timestamp (ISO format)"),
    latest_only: bool = Query(True, description="If true, fetches only the most recent analysis result within the time range.")
):
    analysis_type_db_key = analysis_type_path.lower()
    analysis_type_db_value = ANALYSIS_TYPES_DB_MAP.get(analysis_type_db_key)

    if not analysis_type_db_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid analysis type path: '{analysis_type_path}'. Supported: {list(ANALYSIS_TYPES_DB_MAP.keys())}")

    table_name = f"\"{settings.ANALYSIS_RESULTS_TABLE_PREFIX}_{analysis_type_db_value}\""

    order_by_clause = "ORDER BY analysis_timestamp DESC" if latest_only else "ORDER BY analysis_timestamp ASC"
    limit_clause = "LIMIT 1" if latest_only else ""

    query = f"""
        SELECT "analysis_timestamp", "original_signal_name", "analysis_type", "parameters",
               "result_value_numeric", "result_series_jsonb", "result_structured_jsonb", "metadata"
        FROM {table_name}
        WHERE "original_signal_name" = $1
          AND "analysis_type" = $2
          AND "analysis_timestamp" >= $3
          AND "analysis_timestamp" <= $4
        {order_by_clause}
        {limit_clause};
    """
    logger.debug(f"AnalysisRouter: Querying {table_name} for signal '{original_signal_name}', type '{analysis_type_db_value}' between {start_time} and {end_time}, latest_only={latest_only}")

    try:
        db_records = await fetch_data(query, original_signal_name, analysis_type_db_value, start_time, end_time)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AnalysisRouter: Unexpected error during fetch_data for {original_signal_name}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching analysis data.")

    if not db_records:
        logger.warning(f"AnalysisRouter: No records found for {analysis_type_path} on signal '{original_signal_name}' in range {start_time}-{end_time}.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No pre-computed '{analysis_type_path}' analysis found for signal '{original_signal_name}' in the time range.")

    parser_func = PARSER_MAP.get(analysis_type_db_value)

    if latest_only:
        logger.debug(f"AnalysisRouter: Parsing latest record for {analysis_type_path} on '{original_signal_name}'.")
        parsed_result = parser_func(db_records[0])
        if parsed_result is None:
             logger.error(f"AnalysisRouter: Parser returned None for latest record of {analysis_type_path} on '{original_signal_name}'. DB Record: {dict(db_records[0]) if db_records else 'None'}")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error parsing stored analysis result for '{analysis_type_path}'.")
        return parsed_result
    else: 
        parsed_results_list = []
        for i, record in enumerate(db_records):
            logger.debug(f"AnalysisRouter: Parsing record {i} for {analysis_type_path} on '{original_signal_name}'.")
            parsed = parser_func(record)
            if parsed is not None:
                parsed_results_list.append(parsed)
            else:
                logger.warning(f"AnalysisRouter: Failed to parse record index {i} for {analysis_type_path} on '{original_signal_name}'. Skipping this record. DB Record: {dict(record)}")
        
        if parsed_results_list:
            return parsed_results_list
        else: 
            logger.error(f"AnalysisRouter: Could not parse ANY stored analysis results for '{analysis_type_path}', signal '{original_signal_name}' when latest_only=false. All records failed parsing.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error parsing all stored analysis results for '{analysis_type_path}'. Please check server logs.")