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

def _parse_json_field(db_record: asyncpg.Record, field_name: str, signal_name_for_log: str, parser_type_log: str) -> Optional[Any]:
    field_value = db_record.get(field_name)
    parsed_field = None
    if isinstance(field_value, str):
        try:
            parsed_field = json.loads(field_value)
        except json.JSONDecodeError:
            logger.warning(f"{parser_type_log} Parser: Failed to parse {field_name} string for signal '{signal_name_for_log}'. Content: '{field_value}'")
    elif isinstance(field_value, (dict, list)):
        parsed_field = field_value
    elif field_value is not None:
        logger.warning(f"{parser_type_log} Parser: {field_name} is not a string, dict, or list for signal '{signal_name_for_log}'. Type: {type(field_value)}")
    return parsed_field

def _parse_zscore_result(db_record: asyncpg.Record) -> Optional[ZScoreResultAPI]:
    signal_name_for_log = db_record.get('original_signal_name', 'UnknownSignal')
    parser_type_log = "ZScore"
    logger.debug(f"{parser_type_log} Parser: Starting for signal '{signal_name_for_log}'.")

    data = _parse_json_field(db_record, 'result_structured_jsonb', signal_name_for_log, parser_type_log)
    metadata = _parse_json_field(db_record, 'metadata', signal_name_for_log, parser_type_log)

    if not isinstance(data, dict) or "points" not in data:
        logger.warning(f"{parser_type_log} Parser: Invalid 'data' structure or missing 'points' for signal '{signal_name_for_log}'. Data: {repr(data)[:500]}")
        return None
    try:
        valid_points = [ZScorePointAPI(**p) for p in data.get("points", []) if isinstance(p, dict)]
        if not valid_points and data.get("points"):
             logger.error(f"{parser_type_log} Parser: No valid points after filtering for signal '{signal_name_for_log}'. Original points: {data.get('points')}")
             return None
        return ZScoreResultAPI(points=valid_points, window=data.get("window"), metadata=metadata)
    except Exception as e:
        logger.error(f"{parser_type_log} Parser: Error creating ZScoreResultAPI for '{signal_name_for_log}'. Error: {repr(e)}", exc_info=True)
        logger.debug(f"Problematic data for ZScore '{signal_name_for_log}': {repr(data)}")
        logger.debug(f"Problematic metadata for ZScore '{signal_name_for_log}': {repr(metadata)}")
        return None

def _parse_ma_result(db_record: asyncpg.Record) -> Optional[MovingAverageResultAPI]:
    signal_name_for_log = db_record.get('original_signal_name', 'UnknownSignal')
    parser_type_log = "MA"
    logger.debug(f"{parser_type_log} Parser: Starting for signal '{signal_name_for_log}'.")

    data = _parse_json_field(db_record, 'result_series_jsonb', signal_name_for_log, parser_type_log)
    params = _parse_json_field(db_record, 'parameters', signal_name_for_log, parser_type_log)
    metadata = _parse_json_field(db_record, 'metadata', signal_name_for_log, parser_type_log)

    if not isinstance(data, dict) or "points" not in data:
        logger.warning(f"{parser_type_log} Parser: Invalid 'data' (from result_series_jsonb) structure or missing 'points' for signal '{signal_name_for_log}'. Data: {repr(data)[:500]}")
        return None
    if params is None: params = {}
    if not isinstance(params, dict):
        logger.warning(f"{parser_type_log} Parser: Parsed 'params' is not a dictionary for signal '{signal_name_for_log}'. Type: {type(params)}. Using defaults.")
        params = {}

    try:
        valid_points = [MovingAveragePointAPI(**p) for p in data.get("points", []) if isinstance(p, dict)]
        if not valid_points and data.get("points"):
             logger.error(f"{parser_type_log} Parser: No valid points after filtering for signal '{signal_name_for_log}'. Original points: {data.get('points')}")
             return None
        
        window_val = params.get("window", settings.DEFAULT_MOVING_AVERAGE_WINDOW)
        type_val = params.get("type", "simple")
        return MovingAverageResultAPI(points=valid_points, window=window_val, type=type_val, metadata=metadata)
    except Exception as e:
        logger.error(f"{parser_type_log} Parser: Error creating MovingAverageResultAPI for '{signal_name_for_log}'. Error: {repr(e)}", exc_info=True)
        logger.debug(f"Problematic data for MA '{signal_name_for_log}': {repr(data)}")
        logger.debug(f"Problematic params for MA '{signal_name_for_log}': {repr(params)}")
        logger.debug(f"Problematic metadata for MA '{signal_name_for_log}': {repr(metadata)}")
        return None

def _parse_stl_result(db_record: asyncpg.Record) -> Optional[STLDecompositionAPI]:
    signal_name_for_log = db_record.get('original_signal_name', 'UnknownSignal')
    parser_type_log = "STL"
    logger.debug(f"{parser_type_log} Parser: Starting for signal '{signal_name_for_log}'.")

    data = _parse_json_field(db_record, 'result_structured_jsonb', signal_name_for_log, parser_type_log)
    metadata = _parse_json_field(db_record, 'metadata', signal_name_for_log, parser_type_log)

    if not isinstance(data, dict) or not all(k in data for k in ["trend", "seasonal", "residual", "original_timestamps"]):
        logger.warning(f"{parser_type_log} Parser: Invalid 'data' structure or missing essential keys for signal '{signal_name_for_log}'. Data: {repr(data)[:500]}")
        return None
    try:
        original_timestamps_parsed = []
        for ts_str in data.get('original_timestamps', []):
            try: original_timestamps_parsed.append(datetime.fromisoformat(str(ts_str).replace("Z", "+00:00")))
            except: original_timestamps_parsed.append(None)
        
        trend_list = data.get('trend', [])
        seasonal_list = data.get('seasonal', [])
        residual_list = data.get('residual', [])
        min_len = min(len(original_timestamps_parsed), len(trend_list), len(seasonal_list), len(residual_list))

        valid_trend = [STLComponentAPI(timestamp=original_timestamps_parsed[i], value=trend_list[i]) for i in range(min_len) if original_timestamps_parsed[i] and trend_list[i] is not None]
        valid_seasonal = [STLComponentAPI(timestamp=original_timestamps_parsed[i], value=seasonal_list[i]) for i in range(min_len) if original_timestamps_parsed[i] and seasonal_list[i] is not None]
        valid_residual = [STLComponentAPI(timestamp=original_timestamps_parsed[i], value=residual_list[i]) for i in range(min_len) if original_timestamps_parsed[i] and residual_list[i] is not None]
        
        return STLDecompositionAPI(
            trend=valid_trend, seasonal=valid_seasonal, residual=valid_residual,
            period_used=data.get("period_used"), metadata=metadata
        )
    except Exception as e:
        logger.error(f"{parser_type_log} Parser: Error creating STLDecompositionAPI for '{signal_name_for_log}'. Error: {repr(e)}", exc_info=True)
        logger.debug(f"Problematic data for STL '{signal_name_for_log}': {repr(data)}")
        return None

def _parse_basic_stats_result(db_record: asyncpg.Record) -> Optional[BasicStatsAPI]:
    signal_name_for_log = db_record.get('original_signal_name', 'UnknownSignal')
    parser_type_log = "BasicStats"
    logger.debug(f"{parser_type_log} Parser: Starting for signal '{signal_name_for_log}'.")

    data = _parse_json_field(db_record, 'result_structured_jsonb', signal_name_for_log, parser_type_log)
    metadata = _parse_json_field(db_record, 'metadata', signal_name_for_log, parser_type_log)
    
    required_keys = ["count", "sum_val", "mean", "median", "min_val", "max_val", "std_dev", "variance"]
    if not isinstance(data, dict) or not all(k in data for k in required_keys):
        logger.warning(f"{parser_type_log} Parser: Invalid 'data' structure or missing keys for signal '{signal_name_for_log}'. Data: {repr(data)[:500]}")
        return None
    try:
        # Ensure numeric fields are numeric
        for key in required_keys:
            if not isinstance(data[key], (int, float)):
                try: data[key] = float(data[key])
                except: 
                    logger.error(f"{parser_type_log} Parser: Cannot convert {key} to float for '{signal_name_for_log}'. Value: {data[key]}"); return None
        return BasicStatsAPI(**data, metadata=metadata)
    except Exception as e:
        logger.error(f"{parser_type_log} Parser: Error creating BasicStatsAPI for '{signal_name_for_log}'. Error: {repr(e)}", exc_info=True)
        logger.debug(f"Problematic data for BasicStats '{signal_name_for_log}': {repr(data)}")
        return None

def _parse_simple_timeseries_result(db_record: asyncpg.Record, analysis_name_log_prefix: str) -> Optional[List[TimeSeriesPoint]]:
    signal_name_for_log = db_record.get('original_signal_name', 'UnknownSignal')
    parser_type_log = analysis_name_log_prefix
    logger.debug(f"{parser_type_log} Parser: Starting for signal '{signal_name_for_log}'.")

    data = _parse_json_field(db_record, 'result_series_jsonb', signal_name_for_log, parser_type_log)

    if not isinstance(data, dict) or "points" not in data:
        logger.warning(f"{parser_type_log} Parser: Invalid 'data' structure or missing 'points' for signal '{signal_name_for_log}'. Data: {repr(data)[:500]}")
        return None
    try:
        valid_points = [TimeSeriesPoint(**p) for p in data.get("points", []) if isinstance(p, dict)]
        if not valid_points and data.get("points"):
            logger.error(f"{parser_type_log} Parser: No valid points after filtering for signal '{signal_name_for_log}'. Original points: {data.get('points')}")
            return None
        return valid_points
    except Exception as e:
        logger.error(f"{parser_type_log} Parser: Error creating List[TimeSeriesPoint] for '{signal_name_for_log}'. Error: {repr(e)}", exc_info=True)
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
        if parsed_result:
            return parsed_result
    else:
        parsed_results_list = []
        for i, record in enumerate(db_records):
            logger.debug(f"AnalysisRouter: Parsing record {i} for {analysis_type_path} on '{original_signal_name}'.")
            parsed = parser_func(record)
            if parsed:
                parsed_results_list.append(parsed)
        if parsed_results_list:
            return parsed_results_list

    logger.error(f"AnalysisRouter: Could not parse ANY stored analysis result for '{analysis_type_path}', signal '{original_signal_name}'. Last raw record (if any): {dict(db_records[-1]) if db_records else 'None'}")
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error parsing stored analysis result for '{analysis_type_path}'. Please check server logs for parsing details.")