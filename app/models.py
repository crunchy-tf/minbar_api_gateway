# api_gateway_service/app/models.py
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Any
from datetime import datetime

class TimeSeriesPoint(BaseModel):
    timestamp: datetime
    value: float

class TimeSeriesData(BaseModel):
    signal_name: str
    points: List[TimeSeriesPoint]
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class TopicTrend(BaseModel):
    topic_id: Any
    topic_name: str
    trend_data: List[TimeSeriesPoint]

class SentimentDistribution(BaseModel):
    label: str
    count: int

class TopicSentiment(BaseModel):
    topic_id: Any
    topic_name: str
    sentiments: List[SentimentDistribution]

class KeywordDetail(BaseModel):
    keyword: str
    frequency: Optional[int] = None
    relevance_score: Optional[float] = None
    concept_id: Optional[str] = None

class TopicKeywords(BaseModel):
    topic_id: Any
    topic_name: str
    keywords: List[KeywordDetail]

class OverallSentimentTrend(BaseModel):
    sentiment_label: str
    trend_data: List[TimeSeriesPoint]

class RankedItem(BaseModel):
    name: str
    id: Optional[Any] = None
    score: float
    details: Optional[Dict[str, Any]] = None

class OverviewStats(BaseModel):
    total_documents_processed: Optional[int] = None
    active_topics_count: Optional[int] = None
    last_data_ingested_at: Optional[datetime] = None

class KeywordManagerKeywordInfo(BaseModel):
    term: str
    language: str
    concept_id: str
    concept_display_name: str

class ZScorePointAPI(BaseModel):
    timestamp: datetime
    original_value: float
    z_score: Optional[float] = None

class ZScoreResultAPI(BaseModel):
    points: List[ZScorePointAPI]
    window: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

class MovingAveragePointAPI(BaseModel):
    timestamp: datetime
    value: float

class MovingAverageResultAPI(BaseModel):
    points: List[MovingAveragePointAPI]
    window: int
    type: str
    metadata: Optional[Dict[str, Any]] = None

class STLComponentAPI(BaseModel):
    timestamp: datetime
    value: Optional[float] = None

class STLDecompositionAPI(BaseModel):
    trend: List[STLComponentAPI]
    seasonal: List[STLComponentAPI]
    residual: List[STLComponentAPI]
    period_used: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

class BasicStatsAPI(BaseModel):
    count: int
    sum_val: float
    mean: float
    median: float
    min_val: float
    max_val: float
    std_dev: float
    variance: float
    metadata: Optional[Dict[str, Any]] = None

class TimeSeriesRequestParams(BaseModel):
    start_time: datetime
    end_time: datetime
    time_aggregation: str = Field(default="hourly", pattern="^(hourly|daily|weekly)$")
    topic_id: Optional[str] = None
    sentiment_label: Optional[str] = None
    keyword: Optional[str] = None

    @field_validator('end_time')
    def end_time_after_start_time(cls, v, values):
        if 'start_time' in values.data and v <= values.data['start_time']:
            raise ValueError('end_time must be after start_time')
        return v