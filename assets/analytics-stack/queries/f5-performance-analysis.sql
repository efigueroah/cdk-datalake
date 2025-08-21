-- F5 Performance Analysis Comprehensive
-- Análisis comprehensivo de performance F5 con métricas de dispositivos y contenido

SELECT 
    entorno_nodo as f5_bigip,
    ambiente_pool as f5_pool,
    response_time_category,
    content_category,
    is_mobile,
    cache_hit,
    COUNT(*) as request_count,
    AVG(tiempo_respuesta_ms) as avg_response_time_ms,
    PERCENTILE_APPROX(tiempo_respuesta_ms, 0.50) as p50_response_time_ms,
    PERCENTILE_APPROX(tiempo_respuesta_ms, 0.95) as p95_response_time_ms,
    PERCENTILE_APPROX(tiempo_respuesta_ms, 0.99) as p99_response_time_ms,
    AVG(tamano_respuesta) as avg_response_size_bytes,
    SUM(CASE WHEN is_error THEN 1 ELSE 0 END) as error_count,
    (SUM(CASE WHEN is_error THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as error_rate_percent
FROM "DATABASE_NAME_PLACEHOLDER"."f5_logs"
WHERE year = '2025' AND month = '8'
GROUP BY entorno_nodo, ambiente_pool, response_time_category, content_category, is_mobile, cache_hit
HAVING request_count >= 10
ORDER BY avg_response_time_ms DESC, error_rate_percent DESC
LIMIT 100
