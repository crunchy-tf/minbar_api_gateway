from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from typing import List, Optional, Any, Dict
from datetime import datetime, timedelta
from loguru import logger
import json

from app.security import get_current_username
from app.db_connector import fetch_data
from app.models import (
    TopicTrend, TimeSeriesPoint, SentimentDistribution, TopicSentiment,
    KeywordDetail, TopicKeywords, OverallSentimentTrend, RankedItem, OverviewStats,
    TimeSeriesRequestParams
)
from app.config import settings
from app.cache_manager import async_cache_decorator

router = APIRouter(
    prefix="/signals",
    tags=["Signals & Trends"],
    dependencies=[Depends(get_current_username)]
)

def get_signal_table_name(agg_level: str) -> str:
    if agg_level == "hourly":
        return f"{settings.SOURCE_SIGNALS_TABLE_PREFIX}_topic_hourly"
    elif agg_level == "daily":
        return f"{settings.SOURCE_SIGNALS_TABLE_PREFIX}_topic_daily"
    raise HTTPException(status_code=400, detail=f"Unsupported time_aggregation level: {agg_level}")

@router.get("/overview", response_model=OverviewStats)
@async_cache_decorator(ttl_seconds=600)
async def get_system_overview(
    days_past: int = Query(7, ge=1, le=365, description="Number of past days to consider for stats")
):
    try:
        signal_table_hourly = get_signal_table_name("hourly")
        
        total_docs_query = f"""
            SELECT SUM(document_count) as total_docs 
            FROM {signal_table_hourly} 
            WHERE signal_timestamp >= (NOW() AT TIME ZONE 'UTC' - INTERVAL '{days_past} days');
        """
        active_topics_query = f"""
            SELECT COUNT(DISTINCT topic_id) as active_topics 
            FROM {signal_table_hourly} 
            WHERE signal_timestamp >= (NOW() AT TIME ZONE 'UTC' - INTERVAL '{days_past} days');
        """
        last_ingested_query = f"SELECT MAX(signal_timestamp) as last_ingested FROM {signal_table_hourly};"
        
        total_docs_res = await fetch_data(total_docs_query)
        active_topics_res = await fetch_data(active_topics_query)
        last_ingested_res = await fetch_data(last_ingested_query)

        return OverviewStats(
            total_documents_processed=total_docs_res[0]['total_docs'] if total_docs_res and total_docs_res[0]['total_docs'] is not None else 0,
            active_topics_count=active_topics_res[0]['active_topics'] if active_topics_res and active_topics_res[0]['active_topics'] is not None else 0,
            last_data_ingested_at=last_ingested_res[0]['last_ingested'] if last_ingested_res and last_ingested_res[0]['last_ingested'] else None
        )
    except Exception as e:
        logger.error(f"Error fetching overview stats: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not fetch overview statistics.")

@router.get("/topics/list", response_model=List[Dict[str, Any]])
@async_cache_decorator(ttl_seconds=3600)
async def list_active_topics(
    limit: int = Query(20, ge=1, le=100),
    min_doc_count: int = Query(5, ge=1),
    days_past: int = Query(7, ge=1, le=30)
):
    signal_table = get_signal_table_name("hourly")
    query = f"""
        SELECT 
            topic_id, 
            topic_name, 
            SUM(document_count) as total_documents_in_period,
            MAX(signal_timestamp) as last_seen
        FROM {signal_table}
        WHERE signal_timestamp >= (NOW() AT TIME ZONE 'UTC' - INTERVAL '{days_past} days')
        GROUP BY topic_id, topic_name
        HAVING SUM(document_count) >= $1
        ORDER BY total_documents_in_period DESC
        LIMIT $2;
    """
    records = await fetch_data(query, min_doc_count, limit)
    return [dict(r) for r in records]

@router.get("/topics/{topic_id}/trend", response_model=TopicTrend)
@async_cache_decorator(ttl_seconds=300)
async def get_topic_trend(
    topic_id: str = Path(..., description="The ID of the topic"),
    params: TimeSeriesRequestParams = Depends()
):
    signal_table = get_signal_table_name(params.time_aggregation)
    query = f"""
        SELECT signal_timestamp as timestamp, document_count as value, topic_name
        FROM {signal_table}
        WHERE topic_id = $1 AND signal_timestamp >= $2 AND signal_timestamp <= $3
        ORDER BY signal_timestamp ASC;
    """
    records = await fetch_data(query, topic_id, params.start_time, params.end_time)
    if not records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No trend data found for topic_id {topic_id} in the given range and aggregation level.")
    
    topic_name_val = records[0]['topic_name'] if records else "Unknown Topic"
    return TopicTrend(
        topic_id=topic_id,
        topic_name=topic_name_val,
        trend_data=[TimeSeriesPoint(timestamp=r['timestamp'], value=r['value']) for r in records]
    )

@router.get("/topics/{topic_id}/sentiment_distribution", response_model=TopicSentiment)
@async_cache_decorator(ttl_seconds=300)
async def get_topic_sentiment_distribution(
    topic_id: str = Path(..., description="The ID of the topic"),
    params: TimeSeriesRequestParams = Depends()
):
    signal_table = get_signal_table_name(params.time_aggregation)
    query = f"""
        SELECT 
            dominant_sentiment_label as label, 
            SUM(document_count) as count,
            MAX(topic_name) as topic_name_from_query
        FROM {signal_table}
        WHERE topic_id = $1 AND signal_timestamp >= $2 AND signal_timestamp <= $3
              AND dominant_sentiment_label IS NOT NULL
        GROUP BY dominant_sentiment_label
        ORDER BY count DESC;
    """
    records = await fetch_data(query, topic_id, params.start_time, params.end_time)
    
    topic_name_val = "Unknown Topic"
    if records and records[0]['topic_name_from_query']:
        topic_name_val = records[0]['topic_name_from_query']
    else:
        name_query = f"SELECT topic_name FROM {signal_table} WHERE topic_id = $1 AND signal_timestamp >= $2 AND signal_timestamp <= $3 LIMIT 1;"
        name_rec = await fetch_data(name_query, topic_id, params.start_time, params.end_time)
        if name_rec and name_rec[0]['topic_name']:
            topic_name_val = name_rec[0]['topic_name']
        elif name_rec is None or not name_rec : # If name_rec is None or empty list
            alt_name_query = f"SELECT topic_name FROM {signal_table} WHERE topic_id = $1 LIMIT 1;" # broader search for name
            alt_name_rec = await fetch_data(alt_name_query, topic_id)
            if alt_name_rec and alt_name_rec[0]['topic_name']:
                 topic_name_val = alt_name_rec[0]['topic_name']
            else:
                 topic_name_val = f"Topic {topic_id}"


    return TopicSentiment(
        topic_id=topic_id,
        topic_name=topic_name_val,
        sentiments=[SentimentDistribution(label=r['label'], count=r['count']) for r in records if r['label'] is not None]
    )

@router.get("/topics/{topic_id}/top_keywords", response_model=TopicKeywords)
@async_cache_decorator(ttl_seconds=900)
async def get_topic_top_keywords(
    topic_id: str = Path(..., description="The ID of the topic"),
    params: TimeSeriesRequestParams = Depends(),
    limit: int = Query(10, ge=1, le=25)
):
    signal_table = get_signal_table_name(params.time_aggregation)
    query = f"""
        SELECT topic_name, top_keywords
        FROM {signal_table}
        WHERE topic_id = $1 AND signal_timestamp >= $2 AND signal_timestamp <= $3
        ORDER BY signal_timestamp DESC
        LIMIT 1; 
    """
    records = await fetch_data(query, topic_id, params.start_time, params.end_time)
    
    topic_name_val = f"Topic {topic_id}"
    keywords_list = []

    if records and records[0]['top_keywords']:
        topic_name_val = records[0]['topic_name'] or topic_name_val
        keywords_data_jsonb = records[0]['top_keywords']
        
        parsed_keywords = []
        if isinstance(keywords_data_jsonb, list): # Directly a list of dicts
            parsed_keywords = keywords_data_jsonb
        elif isinstance(keywords_data_jsonb, str): # A JSON string
            try:
                parsed_keywords = json.loads(keywords_data_jsonb)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse top_keywords JSONB string for topic {topic_id}")
        
        for kw_dict in parsed_keywords[:limit]:
            if isinstance(kw_dict, dict):
                 keywords_list.append(KeywordDetail(
                     keyword=kw_dict.get('keyword', 'unknown'), 
                     frequency=kw_dict.get('total_frequency') # Use total_frequency as 'frequency'
                ))
    else: # If no records or no keywords, try to get topic name
        name_query = f"SELECT topic_name FROM {signal_table} WHERE topic_id = $1 AND signal_timestamp >= $2 AND signal_timestamp <= $3 LIMIT 1;"
        name_rec = await fetch_data(name_query, topic_id, params.start_time, params.end_time)
        if name_rec and name_rec[0]['topic_name']:
            topic_name_val = name_rec[0]['topic_name']
        elif name_rec is None or not name_rec :
            alt_name_query = f"SELECT topic_name FROM {signal_table} WHERE topic_id = $1 LIMIT 1;"
            alt_name_rec = await fetch_data(alt_name_query, topic_id)
            if alt_name_rec and alt_name_rec[0]['topic_name']:
                 topic_name_val = alt_name_rec[0]['topic_name']

    return TopicKeywords(
        topic_id=topic_id,
        topic_name=topic_name_val,
        keywords=keywords_list
    )


@router.get("/sentiments/overall_trend", response_model=List[OverallSentimentTrend])
@async_cache_decorator(ttl_seconds=300)
async def get_overall_sentiment_trends(
    params: TimeSeriesRequestParams = Depends(),
    sentiment_labels: Optional[str] = Query("Concerned,Anxious,Satisfied,Angry", description="Comma-separated list of sentiment labels.")
):
    signal_table = get_signal_table_name(params.time_aggregation)
    labels_to_query = [label.strip() for label in sentiment_labels.split(',')] if sentiment_labels else settings.HEALTHCARE_SENTIMENT_LABELS
    trends = []

    for label in labels_to_query:
        query = f"""
            SELECT 
                signal_timestamp as timestamp, 
                AVG((jsonb_extract_path_text(aggregated_sentiment_avg_scores, $1))::float) as value
            FROM {signal_table}
            WHERE jsonb_extract_path_text(aggregated_sentiment_avg_scores, $1) IS NOT NULL
              AND signal_timestamp >= $2 
              AND signal_timestamp <= $3
            GROUP BY signal_timestamp
            HAVING AVG((jsonb_extract_path_text(aggregated_sentiment_avg_scores, $1))::float) IS NOT NULL
            ORDER BY signal_timestamp ASC;
        """
        records = await fetch_data(query, label, params.start_time, params.end_time)
        trends.append(OverallSentimentTrend(
            sentiment_label=label,
            trend_data=[TimeSeriesPoint(timestamp=r['timestamp'], value=r['value']) for r in records if r['value'] is not None]
        ))
    return trends

@router.get("/rankings/top_topics", response_model=List[RankedItem])
@async_cache_decorator(ttl_seconds=600)
async def get_top_ranked_topics(
    params: TimeSeriesRequestParams = Depends(),
    rank_by: str = Query("recent_volume", enum=["recent_volume", "volume_increase_abs", "high_concern_score"]),
    limit: int = Query(5, ge=1, le=20)
):
    signal_table = get_signal_table_name(params.time_aggregation)
    results = []
    
    if rank_by == "recent_volume":
        query = f"""
            SELECT topic_id, topic_name, SUM(document_count) as score
            FROM {signal_table}
            WHERE signal_timestamp >= $1 AND signal_timestamp <= $2
            GROUP BY topic_id, topic_name
            ORDER BY score DESC NULLS LAST
            LIMIT $3;
        """
        records = await fetch_data(query, params.start_time, params.end_time, limit)
        results = [RankedItem(id=r['topic_id'], name=r['topic_name'], score=r['score'] or 0.0) for r in records]
    
    elif rank_by == "high_concern_score":
        # Average 'Concerned' score over the period for each topic
        query = f"""
            SELECT 
                topic_id, 
                topic_name, 
                AVG((jsonb_extract_path_text(aggregated_sentiment_avg_scores, 'Concerned'))::float) as score
            FROM {signal_table}
            WHERE signal_timestamp >= $1 AND signal_timestamp <= $2
                AND jsonb_extract_path_text(aggregated_sentiment_avg_scores, 'Concerned') IS NOT NULL
            GROUP BY topic_id, topic_name
            ORDER BY score DESC NULLS LAST
            LIMIT $3;
        """
        records = await fetch_data(query, params.start_time, params.end_time, limit)
        results = [RankedItem(id=r['topic_id'], name=r['topic_name'], score=r['score'] or 0.0) for r in records]

    elif rank_by == "volume_increase_abs":
        # Compare current period volume with previous period volume
        # This query is more complex and illustrative
        window_duration_seconds = (params.end_time - params.start_time).total_seconds()
        prev_start_time = params.start_time - timedelta(seconds=window_duration_seconds)
        prev_end_time = params.start_time - timedelta(microseconds=1) # Just before current period starts

        query = f"""
            WITH current_period_volume AS (
                SELECT topic_id, topic_name, SUM(document_count) as current_vol
                FROM {signal_table}
                WHERE signal_timestamp >= $1 AND signal_timestamp <= $2
                GROUP BY topic_id, topic_name
            ),
            previous_period_volume AS (
                SELECT topic_id, SUM(document_count) as prev_vol
                FROM {signal_table}
                WHERE signal_timestamp >= $3 AND signal_timestamp <= $4
                GROUP BY topic_id
            )
            SELECT 
                cpv.topic_id, 
                cpv.topic_name, 
                (cpv.current_vol - COALESCE(ppv.prev_vol, 0)) as score
            FROM current_period_volume cpv
            LEFT JOIN previous_period_volume ppv ON cpv.topic_id = ppv.topic_id
            ORDER BY score DESC NULLS LAST
            LIMIT $5;
        """
        records = await fetch_data(query, params.start_time, params.end_time, prev_start_time, prev_end_time, limit)
        results = [RankedItem(id=r['topic_id'], name=r['topic_name'], score=r['score'] or 0.0) for r in records]
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Ranking type '{rank_by}' not implemented or invalid.")

    return results