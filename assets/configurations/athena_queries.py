# ATHENA NAMED QUERIES FOR AGESIC DATA LAKE POC

# Query 1: Error Analysis
ERROR_ANALYSIS_QUERY = """
SELECT 
    status_category,
    status_code,
    COUNT(*) as error_count,
    COUNT(DISTINCT client_ip) as unique_ips,
    AVG(response_size) as avg_response_size,
    DATE_FORMAT(from_iso8601_timestamp(timestamp), '%Y-%m-%d %H:00:00') as hour_bucket
FROM processed_logs
WHERE is_error = true
    AND year = YEAR(CURRENT_DATE)
    AND month = MONTH(CURRENT_DATE)
    AND day >= DAY(CURRENT_DATE) - 7
GROUP BY status_category, status_code, DATE_FORMAT(from_iso8601_timestamp(timestamp), '%Y-%m-%d %H:00:00')
ORDER BY hour_bucket DESC, error_count DESC
LIMIT 100;
"""

# Query 2: Traffic Analysis
TRAFFIC_ANALYSIS_QUERY = """
SELECT 
    request_path,
    http_method,
    COUNT(*) as request_count,
    COUNT(DISTINCT client_ip) as unique_visitors,
    AVG(response_size) as avg_response_size,
    SUM(CASE WHEN is_error THEN 1 ELSE 0 END) as error_count,
    (SUM(CASE WHEN is_error THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as error_rate_percent,
    hour
FROM processed_logs
WHERE year = YEAR(CURRENT_DATE)
    AND month = MONTH(CURRENT_DATE)
    AND day = DAY(CURRENT_DATE)
GROUP BY request_path, http_method, hour
HAVING request_count > 10
ORDER BY request_count DESC, hour DESC
LIMIT 50;
"""

# Query 3: Top IPs Analysis
TOP_IPS_QUERY = """
SELECT 
    client_ip,
    COUNT(*) as total_requests,
    COUNT(DISTINCT request_path) as unique_paths,
    SUM(CASE WHEN is_error THEN 1 ELSE 0 END) as error_count,
    (SUM(CASE WHEN is_error THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as error_rate_percent,
    SUM(response_size) as total_bytes,
    MIN(timestamp) as first_seen,
    MAX(timestamp) as last_seen,
    COUNT(DISTINCT user_agent) as unique_user_agents
FROM processed_logs
WHERE year = YEAR(CURRENT_DATE)
    AND month = MONTH(CURRENT_DATE)
    AND day >= DAY(CURRENT_DATE) - 1
GROUP BY client_ip
HAVING total_requests > 50
ORDER BY total_requests DESC
LIMIT 20;
"""

# Query 4: Performance Analysis
PERFORMANCE_QUERY = """
SELECT 
    request_path,
    http_method,
    COUNT(*) as request_count,
    MIN(response_size) as min_size,
    MAX(response_size) as max_size,
    AVG(response_size) as avg_size,
    PERCENTILE_APPROX(response_size, 0.5) as median_size,
    PERCENTILE_APPROX(response_size, 0.95) as p95_size,
    SUM(response_size) as total_bytes
FROM processed_logs
WHERE year = YEAR(CURRENT_DATE)
    AND month = MONTH(CURRENT_DATE)
    AND day >= DAY(CURRENT_DATE) - 7
    AND response_size > 0
GROUP BY request_path, http_method
HAVING request_count > 20
ORDER BY total_bytes DESC
LIMIT 30;
"""

# Query 5: Hourly Summary
HOURLY_SUMMARY_QUERY = """
SELECT 
    year,
    month,
    day,
    hour,
    COUNT(*) as total_requests,
    COUNT(DISTINCT client_ip) as unique_visitors,
    SUM(CASE WHEN status_code >= 200 AND status_code < 300 THEN 1 ELSE 0 END) as success_count,
    SUM(CASE WHEN status_code >= 400 AND status_code < 500 THEN 1 ELSE 0 END) as client_error_count,
    SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) as server_error_count,
    SUM(response_size) as total_bytes,
    AVG(response_size) as avg_response_size
FROM processed_logs
WHERE year = YEAR(CURRENT_DATE)
    AND month = MONTH(CURRENT_DATE)
    AND day >= DAY(CURRENT_DATE) - 7
GROUP BY year, month, day, hour
ORDER BY year DESC, month DESC, day DESC, hour DESC
LIMIT 168;  -- 7 days * 24 hours
"""
