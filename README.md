#!/bin/bash

# ==============================================================================
# Minbar Keyword Manager (Assumed running on localhost:8000 within its VM)
# ==============================================================================
echo "--- Testing Minbar Keyword Manager (Port 8000) ---"

# GET /
echo "GET /"
curl -X GET "http://localhost:8000/"
echo ""
echo ""

# GET /health
echo "GET /health"
curl -X GET "http://localhost:8000/health"
echo ""
echo ""

# POST /api/v1/concepts (Minimal)
echo "POST /api/v1/concepts (Minimal)"
curl -X POST "http://localhost:8000/api/v1/concepts" \
-H "Content-Type: application/json" \
-d '{
  "english_term": "fever"
}'
echo ""
echo ""

# POST /api/v1/concepts (With optional fields)
echo "POST /api/v1/concepts (With optional fields)"
curl -X POST "http://localhost:8000/api/v1/concepts" \
-H "Content-Type: application/json" \
-d '{
  "english_term": "seasonal flu",
  "categories": ["infectious_disease"],
  "french_term": "grippe saisonnière",
  "arabic_term": "الانفلونزا الموسمية"
}'
echo ""
echo ""

# GET /api/v1/concepts (Paginated)
echo "GET /api/v1/concepts (Paginated)"
curl -X GET "http://localhost:8000/api/v1/concepts?skip=0&limit=2"
echo ""
echo ""

# GET /api/v1/concepts (Default pagination)
echo "GET /api/v1/concepts (Default pagination)"
curl -X GET "http://localhost:8000/api/v1/concepts"
echo ""
echo ""

# GET /api/v1/concepts/{concept_id}
# **NOTE: Replace 66243f8a1d5b8e9f7a0c1d2e with an ACTUAL concept_id from your DB if testing this.**
echo "GET /api/v1/concepts/{concept_id} (replace ID with a valid one)"
curl -X GET "http://localhost:8000/api/v1/concepts/66243f8a1d5b8e9f7a0c1d2e"
echo ""
echo ""

# POST /api/v1/feedback (Minimal)
# **NOTE: Replace 66243f8a1d5b8e9f7a0c1d2e with an ACTUAL concept_id from your DB.**
echo "POST /api/v1/feedback (Minimal - replace ID with a valid one)"
curl -X POST "http://localhost:8000/api/v1/feedback" \
-H "Content-Type: application/json" \
-d '{
  "concept_id": "66243f8a1d5b8e9f7a0c1d2e",
  "language": "en",
  "relevance_metric": 0.8,
  "source": "test_ingester_script"
}'
echo ""
echo ""

# POST /api/v1/feedback (With optional term)
# **NOTE: Replace 66243f8a1d5b8e9f7a0c1d2e with an ACTUAL concept_id from your DB.**
echo "POST /api/v1/feedback (With optional term - replace ID with a valid one)"
curl -X POST "http://localhost:8000/api/v1/feedback" \
-H "Content-Type: application/json" \
-d '{
  "concept_id": "66243f8a1d5b8e9f7a0c1d2e",
  "language": "en",
  "relevance_metric": 0.85,
  "source": "test_ingester_script",
  "term": "high temperature"
}'
echo ""
echo ""

# POST /api/v1/concepts/generate (Specific category)
echo "POST /api/v1/concepts/generate (Specific category)"
curl -X POST "http://localhost:8000/api/v1/concepts/generate?category=mental_health"
echo ""
echo ""

# POST /api/v1/concepts/generate (Random category)
echo "POST /api/v1/concepts/generate (Random category)"
curl -X POST "http://localhost:8000/api/v1/concepts/generate"
echo ""
echo ""

# GET /api/v1/keywords (Example)
echo "GET /api/v1/keywords (Example)"
curl -X GET "http://localhost:8000/api/v1/keywords?lang=fr&limit=5&min_score=0.3"
echo ""
echo ""

# GET /api/v1/keywords (Minimal)
echo "GET /api/v1/keywords (Minimal)"
curl -X GET "http://localhost:8000/api/v1/keywords?lang=en"
echo ""
echo ""


# ==============================================================================
# Minbar - Social Media Ingester (Assumed running on localhost:8001 within its VM)
# ==============================================================================
echo "--- Testing Minbar - Social Media Ingester (Port 8001) ---"

# GET /
echo "GET /"
curl -X GET "http://localhost:8001/"
echo ""
echo ""

# GET /health
echo "GET /health"
curl -X GET "http://localhost:8001/health"
echo ""
echo ""

# POST /trigger-ingestion
echo "POST /trigger-ingestion"
curl -X POST "http://localhost:8001/trigger-ingestion"
echo ""
echo ""


# ==============================================================================
# Minbar Data Preprocessor (Assumed running on localhost:8002 within its VM)
# ==============================================================================
echo "--- Testing Minbar Data Preprocessor (Port 8002) ---"

# GET /
echo "GET /"
curl -X GET "http://localhost:8002/"
echo ""
echo ""

# GET /health
echo "GET /health"
curl -X GET "http://localhost:8002/health"
echo ""
echo ""

# POST /trigger-processing
echo "POST /trigger-processing"
curl -X POST "http://localhost:8002/trigger-processing"
echo ""
echo ""


# ==============================================================================
# Minbar NLP Analyzer Service (Assumed running on localhost:8001 within its VM)
# ==============================================================================
echo "--- Testing Minbar NLP Analyzer Service (Port 8001) ---"

# POST /analyze
# **NOTE: Replace raw_mongo_id, keyword_concept_id with relevant values if needed for specific testing.**
echo "POST /analyze"
curl -X POST "http://localhost:8001/analyze" \
-H "Content-Type: application/json" \
-d '{
  "raw_mongo_id": "sampleMongoId123",
  "source": "test_post",
  "original_timestamp": "2024-05-01T12:00:00Z",
  "retrieved_by_keyword": "health concerns",
  "keyword_language": "en",
  "keyword_concept_id": "sampleConceptId456",
  "detected_language": "en",
  "cleaned_text": "I am feeling very anxious about the new hospital policies and the rising cost of medication.",
  "tokens_processed": ["feeling", "anxious", "new", "hospital", "policies", "rising", "cost", "medication"],
  "lemmas": ["feel", "anxious", "new", "hospital", "policy", "rise", "cost", "medication"],
  "original_url": "http://example.com/post/1"
}'
echo ""
echo ""


# ==============================================================================
# Minbar Signal Extraction Service (Assumed running on localhost:8002 within its VM)
# ==============================================================================
echo "--- Testing Minbar Signal Extraction Service (Port 8002) ---"

# POST /extract-signal
# **NOTE: This endpoint is primarily for testing aggregation logic.**
# **Replace document details and IDs with relevant test data.**
echo "POST /extract-signal"
curl -X POST "http://localhost:8002/extract-signal" \
-H "Content-Type: application/json" \
-d '{
  "topic_id": "topic_health_access_001",
  "topic_name": "001_access_healthcare_costs",
  "documents": [
    {
      "raw_mongo_id": "mongoDocSignal1",
      "original_timestamp": "2024-05-01T14:00:00Z",
      "overall_sentiment": [
        {"label": "Concerned", "score": 0.9},
        {"label": "Anxious", "score": 0.7}
      ],
      "extracted_keywords_frequency": [
        {"keyword": "access", "frequency": 5},
        {"keyword": "cost", "frequency": 4}
      ]
    },
    {
      "raw_mongo_id": "mongoDocSignal2",
      "original_timestamp": "2024-05-01T14:30:00Z",
      "overall_sentiment": [
        {"label": "Concerned", "score": 0.8}
      ],
      "extracted_keywords_frequency": [
        {"keyword": "insurance", "frequency": 3},
        {"keyword": "cost", "frequency": 2}
      ]
    }
  ],
  "timeframe_start": "2024-05-01T14:00:00Z",
  "timeframe_end": "2024-05-01T15:00:00Z"
}'
echo ""
echo ""


# ==============================================================================
# Minbar Time Series Analysis Service (Assumed running on localhost:8003 within its VM)
# ==============================================================================
echo "--- Testing Minbar Time Series Analysis Service (Port 8003) ---"

# POST /analyze (Providing data directly for basic_stats)
echo "POST /analyze (Providing data directly for basic_stats)"
curl -X POST "http://localhost:8003/analyze" \
-H "Content-Type: application/json" \
-d '{
  "time_series_data": {
    "signal_name": "manual_test_signal_temp",
    "points": [
      {"timestamp": "2024-05-01T00:00:00Z", "value": 20.0},
      {"timestamp": "2024-05-01T01:00:00Z", "value": 22.5},
      {"timestamp": "2024-05-01T02:00:00Z", "value": 21.0},
      {"timestamp": "2024-05-01T03:00:00Z", "value": 23.0},
      {"timestamp": "2024-05-01T04:00:00Z", "value": 20.5}
    ],
    "metadata": {"unit": "celsius"}
  },
  "analysis_type": "basic_stats",
  "parameters": {}
}'
echo ""
echo ""

# POST /analyze (Fetching data for moving_average)
# **NOTE: This requires data to exist in your TimescaleDB for 'topic_123_document_count'.**
# **Adjust signal_name, start_time, end_time to match your data.**
echo "POST /analyze (Fetching data for moving_average - requires data in DB)"
curl -X POST "http://localhost:8003/analyze" \
-H "Content-Type: application/json" \
-d '{
  "signal_name": "topic_123_document_count",
  "start_time": "2024-04-01T00:00:00Z",
  "end_time": "2024-05-02T00:00:00Z",
  "analysis_type": "moving_average",
  "parameters": {
    "window": 3,
    "type": "simple"
  }
}'
echo ""
echo ""

# POST /analyze (Fetching data for z_score with specific metric column)
# **NOTE: This requires data to exist in your TimescaleDB for topic 'exampleTopic' and metric 'avg_sentiment_concerned'.**
# **Adjust signal_name, start_time, end_time, and parameters.metric_column_to_analyze to match your data.**
echo "POST /analyze (Fetching data for z_score with specific metric - requires data in DB)"
curl -X POST "http://localhost:8003/analyze" \
-H "Content-Type: application/json" \
-d '{
  "signal_name": "topic_exampleTopic", 
  "start_time": "2024-04-10T00:00:00Z",
  "end_time": "2024-04-20T00:00:00Z",
  "analysis_type": "z_score",
  "parameters": {
    "metric_column_to_analyze": "dominant_sentiment_score", 
    "window": 5 
  }
}'
echo ""
echo ""

echo "--- All Tests Attempted ---"
