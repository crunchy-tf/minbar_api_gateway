# api_gateway_service/app/routers/analysis_router.py
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from typing import Any, Optional, List, Union, Dict 
from datetime import datetime
from loguru import logger
import json
import asyncpg # <<< --- ADDED IMPORT --- <<<

from app.security import get_current_username
from app.db_connector import fetch_data
from app.config import settings
from app.models import (
    ZScoreResultAPI, MovingAverageResultAPI, STLDecompositionAPI, BasicStatsAPI,
    TimeSeriesPoint, ZScorePointAPI, MovingAveragePointAPI, STLComponentAPI,
    TimeSeriesRequestParams # Assuming this is used or will be used by some endpoint here
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
    data = db_record.get('result_structured_jsonb') # Use .get() for safety
    metadata = db_record.get('metadata')
    if isinstance(data, str): # If it's a JSON string from DB, parse it
        try: data = json.loads(data)
        except json.JSONDecodeError: logger.warning("Failed to parse ZScore JSONB"); return None
    
    if isinstance(data, dict) and "points" in data:
        return ZScoreResultAPI(
            points=[ZScorePointAPI(**p) for p in data.get("points", [])],
            window=data.get("window"),
            metadata=json.loads(metadata) if isinstance(metadata, str) else metadata
        )
    return None

def _parse_ma_result(db_record: asyncpg.Record) -> Optional[MovingAverageResultAPI]:
    data = db_record.get('result_series_jsonb') 
    params = db_record.get('parameters')
    metadata = db_record.get('metadata')

    if isinstance(data, str): 
        try: data = json.loads(data)
        except json.JSONDecodeError: logger.warning("Failed to parse MA data JSONB"); return None
    if isinstance(params, str):
        try: params = json.loads(params)
        except json.JSONDecodeError: logger.warning("Failed to parse MA params JSONB"); params = {} # Default if params fail

    if isinstance(data, dict) and "points" in data and isinstance(params, dict):
        return MovingAverageResultAPI(
            points=[MovingAveragePointAPI(**p) for p in data.get("points", [])],
            window=params.get("window", settings.DEFAULT_MOVING_AVERAGE_WINDOW),
            type=params.get("type", "simple"),
            metadata=json.loads(metadata) if isinstance(metadata, str) else metadata
        )
    return None

def _parse_stl_result(db_record: asyncpg.Record) -> Optional[STLDecompositionAPI]:
    data = db_record.get('result_structured_jsonb')
    metadata = db_record.get('metadata')
    if isinstance(data, str):
        try: data = json.loads(data)
        except json.JSONDecodeError: logger.warning("Failed to parse STL JSONB"); return None

    if isinstance(data, dict) and all(k in data for k in ["trend", "seasonal", "residual", "original_timestamps"]):
        # Ensure original_timestamps are converted back to datetime if stored as strings
        original_timestamps_parsed = []
        if isinstance(data.get('original_timestamps'), list):
            for ts_str in data['original_timestamps']:
                try:
                    original_timestamps_parsed.append(datetime.fromisoformat(ts_str.replace("Z", "+00:00")))
                except (ValueError, AttributeError): # Handle if not string or invalid format
                    logger.warning(f"Could not parse timestamp '{ts_str}' in STL data.")
                    original_timestamps_parsed.append(None) # Or handle error differently
        
        # Handle cases where timestamps couldn't be parsed or are fewer than other components
        min_len = min(len(original_timestamps_parsed), len(data['trend']), len(data['seasonal']), len(data['residual']))

        return STLDecompositionAPI(
            trend=[STLComponentAPI(timestamp=original_timestamps_parsed[i], value=data['trend'][i]) for i in range(min_len) if original_timestamps_parsed[i]],
            seasonal=[STLComponentAPI(timestamp=original_timestamps_parsed[i], value=data['seasonal'][i]) for i in range(min_len) if original_timestamps_parsed[i]],
            residual=[STLComponentAPI(timestamp=original_timestamps_parsed[i], value=data['residual'][i]) for i in range(min_len) if original_timestamps_parsed[i]],
            period_used=data.get("period_used"),
            metadata=json.loads(metadata) if isinstance(metadata, str) else metadata
        )
    return None

def _parse_basic_stats_result(db_record: asyncpg.Record) -> Optional[BasicStatsAPI]:
    data = db_record.get('result_structured_jsonb')
    metadata = db_record.get('metadata')
    if isinstance(data, str):
        try: data = json.loads(data)
        except json.JSONDecodeError: logger.warning("Failed to parse BasicStats JSONB"); return None
        
    if isinstance(data, dict) and all(k in data for k in ["count", "mean", "median"]):
        return BasicStatsAPI(**data, metadata=json.loads(metadata) if isinstance(metadata, str) else metadata)
    return None

def _parse_simple_timeseries_result(db_record: asyncpg.Record) -> Optional[List[TimeSeriesPoint]]:
    data = db_record.get('result_series_jsonb')
    if isinstance(data, str):
        try: data = json.loads(data)
        except json.JSONDecodeError: logger.warning("Failed to parse SimpleTimeSeries JSONB"); return None
        
    if isinstance(data, dict) and "points" in data:
        return [TimeSeriesPoint(**p) for p in data.get("points", [])]
    return None

PARSER_MAP = {
    "z_score": _parse_zscore_result,
    "moving_average": _parse_ma_result,
    "stl_decomposition": _parse_stl_result,
    "basic_stats": _parse_basic_stats_result,
    "rate_of_change": _parse_simple_timeseries_result,
    "percent_change": _parse_simple_timeseries_result
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
    # The response_model will be dynamically chosen or be a Union if FastAPI supports it well enough here
    # For now, let's keep the Union or allow Any and rely on correct parsing.
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

    table_name = f"\"{settings.ANALYSIS_RESULTS_TABLE_PREFIX}_{analysis_type_db_value}\"" # Ensure table name is quoted
    
    order_by_clause = "ORDER BY analysis_timestamp DESC" if latest_only else "ORDER BY analysis_timestamp ASC"
    limit_clause = "LIMIT 1" if latest_only else ""

    # Quoted column names
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
    
    db_records = await fetch_data(query, original_signal_name, analysis_type_db_value, start_time, end_time)
    
    if not db_records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No pre-computed '{analysis_type_path}' analysis found for signal '{original_signal_name}' in the time range.")

    parser_func = PARSER_MAP.get(analysis_type_db_value)
    if not parser_func:
        logger.warning(f"No specific parser for analysis type '{analysis_type_db_value}'. Returning raw record(s).")
        return [dict(r) for r in db_records] if not latest_only else dict(db_records[0])

    if latest_only:
        parsed_result = parser_func(db_records[0])
        if parsed_result:
            return parsed_result
    else: 
        parsed_results_list = []
        for record in db_records:
            parsed = parser_func(record)
            if parsed:
                parsed_results_list.append(parsed)
        if parsed_results_list:
            return parsed_results_list
        
    # Fallback if parsing fails but records were found
    logger.error(f"Could not parse stored analysis result for '{analysis_type_path}', signal '{original_signal_name}'. Data: {db_records}")
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not parse stored analysis result for '{analysis_type_path}'.")