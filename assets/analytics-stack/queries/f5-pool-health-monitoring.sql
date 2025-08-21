-- F5 Pool Health Monitoring
-- Monitoreo de salud de pools F5 con métricas de disponibilidad y performance

SELECT 
    ambiente_pool as f5_pool,
    entorno_nodo as f5_bigip,
    COUNT(*) as total_requests,
    AVG(tiempo_respuesta_ms) as avg_response_time_ms,
    PERCENTILE_APPROX(tiempo_respuesta_ms, 0.95) as p95_response_time_ms,
    MAX(tiempo_respuesta_ms) as max_response_time_ms,
    SUM(CASE WHEN is_error THEN 1 ELSE 0 END) as error_count,
    SUM(CASE WHEN codigo_respuesta >= 500 THEN 1 ELSE 0 END) as server_errors,
    SUM(CASE WHEN codigo_respuesta >= 400 AND codigo_respuesta < 500 THEN 1 ELSE 0 END) as client_errors,
    (SUM(CASE WHEN is_error THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as error_rate_percent,
    (SUM(CASE WHEN codigo_respuesta >= 500 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as server_error_rate_percent,
    COUNT(DISTINCT ip_cliente_externo) as unique_clients,
    SUM(tamano_respuesta) as total_bytes_served,
    -- Pool Health Score (0-100, higher is better)
    GREATEST(0, 100 - 
        (SUM(CASE WHEN is_error THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) - 
        (LEAST(AVG(tiempo_respuesta_ms) / 100, 50))
    ) as pool_health_score
FROM "DATABASE_NAME_PLACEHOLDER"."f5_logs"
WHERE year = '2025' AND month = '8'
    AND ambiente_pool IS NOT NULL
GROUP BY ambiente_pool, entorno_nodo
HAVING total_requests >= 10
ORDER BY pool_health_score ASC, error_rate_percent DESC, avg_response_time_ms DESC
LIMIT 50
