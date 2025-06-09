### API GATEWAY DOCUMENTATION AND EXAMPLE ENDPOINTS AND RESPONSES:

ENDPOINT: GET / 
EXAMPLE:
curl -u admin:changeme "http://34.155.97.220:8080/"
{"message":"Welcome to Minbar API Gateway, admin! All systems operational."}

ENDPOINT: GET /health
EXAMPLE:
curl -u admin:changeme "http://34.155.97.220:8080/health"
{"status":"ok","service_name":"Minbar API Gateway","dependencies":{"database":"connected","keyword_manager":"connected"}}

Endpoint: GET /signals/overview
EXAMPLE:
curl -u admin:changeme "http://34.155.97.220:8080/signals/overview?days_past=30"
{"total_documents_processed":4443,"active_topics_count":67,"last_data_ingested_at":"2025-05-29T16:00:00Z"}

Endpoint: GET /signals/topics/list
EXAMPLE:
curl -u admin:changeme "http://34.155.97.220:8080/signals/topics/list?limit=3&min_doc_count=5&days_past=30"
[{"topic_id":"402","topic_name":"Hospitals Overwhelmed: Long Wait Times & Bed Shortages","total_documents_in_period":264,"last_seen":"2025-05-23T16:00:00Z"},{"topic_id":"777","topic_name":"Unverified Rumors: New Virus Strain Emergence","total_documents_in_period":260,"last_seen":"2025-05-27T14:00:00Z"},{"topic_id":"1001","topic_name":"Funding for Mental Health Services Debate","total_documents_in_period":239,"last_seen":"2025-05-20T21:00:00Z"}]

Endpoint: GET /signals/topics/{topic_id}/trend
EXAMPLE:
curl -u admin:changeme "http://34.155.97.220:8080/signals/topics/3/trend?time_aggregation=hourly&start_time=2025-05-20T00:00:00Z&end_time=2025-05-20T23:59:59Z"
{"topic_id":"3","topic_name":"3_vaccine_hesitancy_side_effects_rumors","trend_data":[{"timestamp":"2025-05-20T10:00:00Z","value":15.0},{"timestamp":"2025-05-20T11:00:00Z","value":18.0},{"timestamp":"2025-05-20T12:00:00Z","value":12.0},{"timestamp":"2025-05-20T13:00:00Z","value":20.0},{"timestamp":"2025-05-20T14:00:00Z","value":22.0},{"timestamp":"2025-05-20T15:00:00Z","value":17.0},{"timestamp":"2025-05-20T16:00:00Z","value":19.0}]}

Endpoint: GET /signals/topics/{topic_id}/sentiment_distribution
EXAMPLE:
curl -u admin:changeme "http://34.155.97.220:8080/signals/topics/3/sentiment_distribution?time_aggregation=hourly&start_time=2025-05-20T00:00:00Z&end_time=2025-05-20T23:59:59Z"
{"topic_id":"3","topic_name":"3_vaccine_hesitancy_side_effects_rumors","sentiments":[{"label":"Concerned","count":123}]}

Endpoint: GET /signals/topics/{topic_id}/top_keywords
EXAMPLE:
curl -u admin:changeme "http://34.155.97.220:8080/signals/topics/3/top_keywords?time_aggregation=hourly&start_time=2025-05-20T00:00:00Z&end_time=2025-05-20T23:59:59Z&limit=3"
{"topic_id":"3","topic_name":"3_vaccine_hesitancy_side_effects_rumors","keywords":[{"keyword":"trust science","frequency":20,"relevance_score":null,"concept_id":null},{"keyword":"conspiracy","frequency":18,"relevance_score":null,"concept_id":null}]}

Endpoint: GET /signals/sentiments/overall_trend
EXAMPLE:
curl -u admin:changeme "http://34.155.97.220:8080/signals/sentiments/overall_trend?time_aggregation=hourly&start_time=2025-05-20T00:00:00Z&end_time=2025-05-23T23:59:59Z&sentiment_labels=Concerned,Anxious"
[{"sentiment_label":"Concerned","trend_data":[{"timestamp":"2025-05-20T09:00:00Z","value":0.15},{"timestamp":"2025-05-20T10:00:00Z","value":0.27},{"timestamp":"2025-05-20T11:00:00Z","value":0.40666666666666657},{"timestamp":"2025-05-20T12:00:00Z","value":0.38000000000000006},{"timestamp":"2025-05-20T13:00:00Z","value":0.3625},{"timestamp":"2025-05-20T14:00:00Z","value":0.43},{"timestamp":"2025-05-20T15:00:00Z","value":0.388},{"timestamp":"2025-05-20T16:00:00Z","value":0.4766666666666666},{"timestamp":"2025-05-20T17:00:00Z","value":0.3},{"timestamp":"2025-05-20T18:00:00Z","value":0.435},{"timestamp":"2025-05-20T19:00:00Z","value":0.31},{"timestamp":"2025-05-20T20:00:00Z","value":0.26},{"timestamp":"2025-05-20T21:00:00Z","value":0.29},{"timestamp":"2025-05-21T09:00:00Z","value":0.18},{"timestamp":"2025-05-21T10:00:00Z","value":0.19},{"timestamp":"2025-05-21T11:00:00Z","value":0.155},{"timestamp":"2025-05-21T12:00:00Z","value":0.25333333333333335},{"timestamp":"2025-05-21T13:00:00Z","value":0.22999999999999998},{"timestamp":"2025-05-21T14:00:00Z","value":0.26},{"timestamp":"2025-05-21T15:00:00Z","value":0.24666666666666667},{"timestamp":"2025-05-21T16:00:00Z","value":0.36},{"timestamp":"2025-05-21T17:00:00Z","value":0.46},{"timestamp":"2025-05-21T18:00:00Z","value":0.51},{"timestamp":"2025-05-22T09:00:00Z","value":0.3},{"timestamp":"2025-05-22T10:00:00Z","value":0.35333333333333333},{"timestamp":"2025-05-22T11:00:00Z","value":0.30000000000000004},{"timestamp":"2025-05-22T12:00:00Z","value":0.27},{"timestamp":"2025-05-22T13:00:00Z","value":0.26},{"timestamp":"2025-05-22T14:00:00Z","value":0.28},{"timestamp":"2025-05-22T15:00:00Z","value":0.31},{"timestamp":"2025-05-22T16:00:00Z","value":0.30500000000000005},{"timestamp":"2025-05-23T09:00:00Z","value":0.4},{"timestamp":"2025-05-23T10:00:00Z","value":0.36},{"timestamp":"2025-05-23T11:00:00Z","value":0.3766666666666667},{"timestamp":"2025-05-23T12:00:00Z","value":0.325},{"timestamp":"2025-05-23T13:00:00Z","value":0.385},{"timestamp":"2025-05-23T14:00:00Z","value":0.345},{"timestamp":"2025-05-23T15:00:00Z","value":0.375},{"timestamp":"2025-05-23T16:00:00Z","value":0.18},{"timestamp":"2025-05-23T17:00:00Z","value":0.32}]},{"sentiment_label":"Anxious","trend_data":[{"timestamp":"2025-05-20T09:00:00Z","value":0.01},{"timestamp":"2025-05-20T10:00:00Z","value":0.08666666666666667},{"timestamp":"2025-05-20T11:00:00Z","value":0.12666666666666668},{"timestamp":"2025-05-20T12:00:00Z","value":0.14666666666666667},{"timestamp":"2025-05-20T13:00:00Z","value":0.19},{"timestamp":"2025-05-20T14:00:00Z","value":0.16},{"timestamp":"2025-05-20T15:00:00Z","value":0.146},{"timestamp":"2025-05-20T16:00:00Z","value":0.20666666666666667},{"timestamp":"2025-05-20T17:00:00Z","value":0.1466666666666667},{"timestamp":"2025-05-20T18:00:00Z","value":0.185},{"timestamp":"2025-05-20T19:00:00Z","value":0.17},{"timestamp":"2025-05-20T20:00:00Z","value":0.14},{"timestamp":"2025-05-20T21:00:00Z","value":0.16},{"timestamp":"2025-05-21T09:00:00Z","value":0.08},{"timestamp":"2025-05-21T10:00:00Z","value":0.085},{"timestamp":"2025-05-21T11:00:00Z","value":0.07500000000000001},{"timestamp":"2025-05-21T12:00:00Z","value":0.10333333333333333},{"timestamp":"2025-05-21T13:00:00Z","value":0.08000000000000002},{"timestamp":"2025-05-21T14:00:00Z","value":0.10333333333333333},{"timestamp":"2025-05-21T15:00:00Z","value":0.11},{"timestamp":"2025-05-21T16:00:00Z","value":0.33},{"timestamp":"2025-05-21T17:00:00Z","value":0.15},{"timestamp":"2025-05-21T18:00:00Z","value":0.13},{"timestamp":"2025-05-22T09:00:00Z","value":0.15},{"timestamp":"2025-05-22T10:00:00Z","value":0.13999999999999999},{"timestamp":"2025-05-22T11:00:00Z","value":0.115},{"timestamp":"2025-05-22T12:00:00Z","value":0.115},{"timestamp":"2025-05-22T13:00:00Z","value":0.095},{"timestamp":"2025-05-22T14:00:00Z","value":0.095},{"timestamp":"2025-05-22T15:00:00Z","value":0.095},{"timestamp":"2025-05-22T16:00:00Z","value":0.055},{"timestamp":"2025-05-23T09:00:00Z","value":0.285},{"timestamp":"2025-05-23T10:00:00Z","value":0.21},{"timestamp":"2025-05-23T11:00:00Z","value":0.18000000000000002},{"timestamp":"2025-05-23T12:00:00Z","value":0.215},{"timestamp":"2025-05-23T13:00:00Z","value":0.22999999999999998},{"timestamp":"2025-05-23T14:00:00Z","value":0.21000000000000002},{"timestamp":"2025-05-23T15:00:00Z","value":0.215},{"timestamp":"2025-05-23T16:00:00Z","value":0.33},{"timestamp":"2025-05-23T17:00:00Z","value":0.1}]}]

Endpoint: GET /signals/rankings/top_topics
EXAMPLE:
curl -u admin:changeme "http://34.155.97.220:8080/signals/rankings/top_topics?time_aggregation=hourly&start_time=2025-05-20T00:00:00Z&end_time=2025-05-23T23:59:59Z&rank_by=high_concern_score&limit=2"
[{"name":"3_vaccine_hesitancy_side_effects_rumors","id":"3","score":0.5642857142857143,"details":null},{"name":"Air Quality Respiratory Issues Alert","id":"604","score":0.5471428571428572,"details":null}]

Endpoint: GET /keywords/top_managed
EXAMPLE:
curl -u admin:changeme "http://34.155.97.220:8080/keywords/top_managed?lang=en&limit=2"
[{"term":"chlamydia","language":"en","concept_id":"6838218bc8c315590518155b","concept_display_name":"chlamydia"},{"term":"chlamydia symptoms","language":"en","concept_id":"6838218fc8c315590518155c","concept_display_name":"chlamydia symptoms"}]

Endpoint: GET /analysis/basicstats/{original_signal_name}
EXAMPLE:
curl -u admin:changeme "http://34.155.97.220:8080/analysis/basicstats/topic_3_document_count?start_time=2025-05-20T16:00:00Z&end_time=2025-05-20T18:00:00Z&latest_only=true"
{"count":7,"sum_val":123.0,"mean":17.5714,"median":18.0,"min_val":12.0,"max_val":22.0,"std_dev":3.2941,"variance":10.8516,"metadata":{"description":"Seeded Basic Stats for Vaccine Hesitancy topic 3 document count","source_table":"agg_signals_topic_hourly","analysis_source":"seed_data_script","metric_analyzed":"document_count","time_range_analyzed":"2025-05-20T10:00:00Z to 2025-05-20T16:00:00Z","topic_id_of_original_signal":"3"}}

Endpoint: GET /analysis/movingaverage/{original_signal_name}
EXAMPLE:
curl -u admin:changeme "http://34.155.97.220:8080/analysis/movingaverage/topic_3_document_count?start_time=2025-05-20T16:00:00Z&end_time=2025-05-20T18:00:00Z&latest_only=true"
{"points":[{"timestamp":"2025-05-20T12:00:00Z","value":15.0},{"timestamp":"2025-05-20T13:00:00Z","value":16.6667},{"timestamp":"2025-05-20T14:00:00Z","value":18.0},{"timestamp":"2025-05-20T15:00:00Z","value":19.6667},{"timestamp":"2025-05-20T16:00:00Z","value":19.3333}],"window":3,"type":"simple","metadata":{"description":"Seeded MA(3) for Vaccine Hesitancy topic 3 document count","source_table":"agg_signals_topic_hourly","analysis_source":"seed_data_script","metric_analyzed":"document_count","time_range_analyzed":"2025-05-20T10:00:00Z to 2025-05-20T16:00:00Z","topic_id_of_original_signal":"3"}}

Endpoint: GET /analysis/rateofchange/{original_signal_name}
EXAMPLE:
curl -u admin:changeme "http://34.155.97.220:8080/analysis/rateofchange/topic_3_document_count?start_time=2025-05-20T16:00:00Z&end_time=2025-05-20T18:00:00Z&latest_only=true"
[{"timestamp":"2025-05-20T11:00:00Z","value":3.0},{"timestamp":"2025-05-20T12:00:00Z","value":-6.0},{"timestamp":"2025-05-20T13:00:00Z","value":8.0},{"timestamp":"2025-05-20T14:00:00Z","value":2.0},{"timestamp":"2025-05-20T15:00:00Z","value":-5.0},{"timestamp":"2025-05-20T16:00:00Z","value":2.0}]

Endpoint: GET /analysis/percentchange/{original_signal_name}
EXAMPLE:
curl -u admin:changeme "http://34.155.97.220:8080/analysis/percentchange/topic_3_document_count?start_time=2025-05-20T16:00:00Z&end_time=2025-05-20T18:00:00Z&latest_only=true"
[{"timestamp":"2025-05-20T11:00:00Z","value":20.0},{"timestamp":"2025-05-20T12:00:00Z","value":-33.3333},{"timestamp":"2025-05-20T13:00:00Z","value":66.6667},{"timestamp":"2025-05-20T14:00:00Z","value":10.0},{"timestamp":"2025-05-20T15:00:00Z","value":-22.7273},{"timestamp":"2025-05-20T16:00:00Z","value":11.7647}]

Endpoint: GET /analysis/zscore/{original_signal_name}
EXAMPLE:
curl -u admin:changeme "http://34.155.97.220:8080/analysis/zscore/topic_3_document_count?start_time=2025-05-20T16:00:00Z&end_time=2025-05-20T18:00:00Z&latest_only=true"
{"points":[{"timestamp":"2025-05-20T10:00:00Z","original_value":15.0,"z_score":-0.7803},{"timestamp":"2025-05-20T11:00:00Z","original_value":18.0,"z_score":0.13},{"timestamp":"2025-05-20T12:00:00Z","original_value":12.0,"z_score":-1.6907},{"timestamp":"2025-05-20T13:00:00Z","original_value":20.0,"z_score":0.7369},{"timestamp":"2025-05-20T14:00:00Z","original_value":22.0,"z_score":1.3437},{"timestamp":"2025-05-20T15:00:00Z","original_value":17.0,"z_score":-0.1734},{"timestamp":"2025-05-20T16:00:00Z","original_value":19.0,"z_score":0.4334}],"window":null,"metadata":{"description":"Seeded Z-score (whole series) for Vaccine Hesitancy topic 3 document count","source_table":"agg_signals_topic_hourly","analysis_source":"seed_data_script","metric_analyzed":"document_count","time_range_analyzed":"2025-05-20T10:00:00Z to 2025-05-20T16:00:00Z","topic_id_of_original_signal":"3"}}

Endpoint: GET /analysis/stldecomposition/{original_signal_name}
EXAMPLE:
curl -u admin:changeme "http://34.155.97.220:8080/analysis/stldecomposition/topic_3_document_count?start_time=2025-05-20T16:00:00Z&end_time=2025-05-20T18:00:00Z&latest_only=true"
{"trend":[{"timestamp":"2025-05-20T10:00:00Z","value":15.5},{"timestamp":"2025-05-20T11:00:00Z","value":16.0},{"timestamp":"2025-05-20T12:00:00Z","value":16.5},{"timestamp":"2025-05-20T13:00:00Z","value":17.0},{"timestamp":"2025-05-20T14:00:00Z","value":17.5},{"timestamp":"2025-05-20T15:00:00Z","value":18.0},{"timestamp":"2025-05-20T16:00:00Z","value":18.5}],"seasonal":[{"timestamp":"2025-05-20T10:00:00Z","value":-0.2},{"timestamp":"2025-05-20T11:00:00Z","value":0.3},{"timestamp":"2025-05-20T12:00:00Z","value":-0.1},{"timestamp":"2025-05-20T13:00:00Z","value":0.2},{"timestamp":"2025-05-20T14:00:00Z","value":-0.3},{"timestamp":"2025-05-20T15:00:00Z","value":0.1},{"timestamp":"2025-05-20T16:00:00Z","value":-0.2}],"residual":[{"timestamp":"2025-05-20T10:00:00Z","value":-0.3},{"timestamp":"2025-05-20T11:00:00Z","value":1.7},{"timestamp":"2025-05-20T12:00:00Z","value":-4.4},{"timestamp":"2025-05-20T13:00:00Z","value":2.8},{"timestamp":"2025-05-20T14:00:00Z","value":4.8},{"timestamp":"2025-05-20T15:00:00Z","value":-1.1},{"timestamp":"2025-05-20T16:00:00Z","value":0.7}],"period_used":3,"metadata":{"description":"Seeded STL (p3) for Vaccine Hesitancy topic 3 document count (illustrative due to short series)","source_table":"agg_signals_topic_hourly","analysis_source":"seed_data_script","metric_analyzed":"document_count","time_range_analyzed":"2025-05-20T10:00:00Z to 2025-05-20T16:00:00Z","topic_id_of_original_signal":"3"}}
