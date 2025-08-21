-- F5 Error Analysis Enhanced
-- Análisis detallado de errores F5 con métricas de infraestructura y categorización avanzada

SELECT 
    entorno_nodo as f5_bigip,
    ambiente_pool as f5_pool,
    ambiente_origen as f5_virtualserver,
    status_category,
    codigo_respuesta,
    COUNT(*) as error_count,
    AVG(tiempo_respuesta_ms) as avg_response_time_ms,
    PERCENTILE_APPROX(tiempo_respuesta_ms, 0.95) as p95_response_time_ms,
    COUNT(DISTINCT ip_cliente_externo) as unique_clients,
    SUM(tamano_respuesta) as total_bytes_served,
    MIN(parsed_timestamp_syslog) as first_error,
    MAX(parsed_timestamp_syslog) as last_error
FROM "DATABASE_NAME_PLACEHOLDER"."f5_logs"
WHERE is_error = true
    AND year = '2025' AND month = '8'
GROUP BY entorno_nodo, ambiente_pool, ambiente_origen, status_category, codigo_respuesta
ORDER BY error_count DESC, avg_response_time_ms DESC
LIMIT 50
