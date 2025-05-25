from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from typing import Any, Optional, List, Union, Dict
from datetime import datetime
from loguru import logger
import json

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
    data = db_record['result_structured_jsonb']
    metadata = db_record['metadata']
    if isinstance(data, dict) and "points" in data:
        return ZScoreResultAPI(
            points=[ZScorePointAPI(**p) for p in data.get("points", [])],
            window=data.get("window"),
            metadata=metadata
        )
    return None

def _parse_ma_result(db_record: asyncpg.Record) -> Optional[MovingAverageResultAPI]:
    data = db_record['result_series_jsonb'] 
    params = db_record['parameters']
    metadata = db_record['metadata']
    if isinstance(data, dict) and "points" in data and isinstance(params, dict):
        return MovingAverageResultAPI(
            points=[MovingAveragePointAPI(**p) for p in data.get("points", [])],
            window=params.get("window", settings.DEFAULT_MOVING_AVERAGE_WINDOW),
            type=params.get("type", "simple"),
            metadata=metadata
        )
    return None

def _parse_stl_result(db_record: asyncpg.Record) -> Optional[STLDecompositionAPI]:
    data = db_record['result_structured_jsonb']
    metadata = db_record['metadata']
    if isinstance(data, dict) and all(k in data for k in ["trend", "seasonal", "residual", "original_timestamps"]):
        return STLDecompositionAPI(
            trend=[STLComponentAPI(timestamp=ts, value=val) for ts, val in zip(data['original_timestamps'], data['trend'])],
            seasonal=[STLComponentAPI(timestamp=ts, value=val) for ts, val in zip(data['original_timestamps'], data['seasonal'])],
            residual=[STLComponentAPI(timestamp=ts, value=val) for ts, val in zip(data['original_timestamps'], data['residual'])],
            period_used=data.get("period_used"),
            metadata=metadata
        )
    return None

def _parse_basic_stats_result(db_record: asyncpg.Record) -> Optional[BasicStatsAPI]:
    data = db_record['result_structured_jsonb']
    metadata = db_record['metadata']
    if isinstance(data, dict) and all(k in data for k in ["count", "mean", "median"]): # Check a few key fields
        return BasicStatsAPI(**data, metadata=metadata)
    return None

def _parse_simple_timeseries_result(db_record: asyncpg.Record) -> Optional[List[TimeSeriesPoint]]:
    data = db_record['result_series_jsonb'] # For ROC, PercentChange
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
    response_model=Union[ZScoreResultAPI, MovingAverageResultAPI, STLDecompositionAPI, BasicStatsAPI, List[TimeSeriesPoint], Dict[str, Any]]
)
@async_cache_decorator(ttl_seconds=900)
async def get_precomputed_analysis_result(
    analysis_type_path: str = Path(..., description=f"Type of analysis. Supported: {', '.join(ANALYSIS_TYPES_DB_MAP.keys())}"),
    original_signal_name: str = Path(..., description="Name of the original signal, e.g., 'topic_5_document_count' or 'agg_signals_topic_hourly.topic_5.document_count'"),
    start_time: datetime = Query(..., description="Start of the time range for analysis_timestamp"),
    end_time: datetime = Query(..., description="End of the time range for analysis_timestamp"),
    latest_only: bool = Query(True, description="If true, fetches only the most recent analysis result within the time range.")
):
    analysis_type_db_key = analysis_type_path.lower()
    analysis_type_db_value = ANALYSIS_TYPES_DB_MAP.get(analysis_type_db_key)

    if not analysis_type_db_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid analysis type path: {analysis_type_path}. Supported: {list(ANALYSIS_TYPES_DB_MAP.keys())}")

    table_name = f"{settings.ANALYSIS_RESULTS_TABLE_PREFIX}_{analysis_type_db_value}"
    
    order_by_clause = "ORDER BY analysis_timestamp DESC" if latest_only else "ORDER BY analysis_timestamp ASC"
    limit_clause = "LIMIT 1" if latest_only else ""

    query = f"""
        SELECT original_signal_name, analysis_type, parameters, 
               result_value_numeric, result_series_jsonb, result_structured_jsonb, metadata
        FROM {table_name}
        WHERE original_signal_name = $1 
          AND analysis_type = $2 
          AND analysis_timestamp >= $3 
          AND analysis_timestamp <= $4
        {order_by_clause}
        {limit_clause}; 
    """
    
    db_records = await fetch_data(query, original_signal_name, analysis_type_db_value, start_time, end_time)
    
    if not db_records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No pre-computed '{analysis_type_path}' analysis found for signal '{original_signal_name}' in the time range.")

    parser_func = PARSER_MAP.get(analysis_type_db_value)
    if not parser_func:
        logger.warning(f"No specific parser for analysis type '{analysis_type_db_value}'. Returning raw record.")
        return dict(db_records[0]) # Return the first record as a dict if latest_only, or list of dicts

    if latest_only:
        parsed_result = parser_func(db_records[0])
        if parsed_result:
            return parsed_result
    else: # Return list of parsed results
        parsed_results_list = []
        for record in db_records:
            parsed = parser_func(record)
            if parsed:
                parsed_results_list.append(parsed)
        if parsed_results_list:
            return parsed_results_list
        
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not parse stored analysis result for '{analysis_type_path}'.")