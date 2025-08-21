# AGESIC Data Lake - Analytics Stack Assets

## Estructura de Assets

```
assets/analytics-stack/
├── queries/                # Queries SQL predefinidas
│   ├── f5-error-analysis.sql          # Análisis de errores F5
│   ├── f5-performance-analysis.sql    # Análisis de performance
│   └── f5-pool-health-monitoring.sql  # Monitoreo de salud pools
├── workgroups/             # Configuraciones Athena Workgroups
│   └── f5-analytics-workgroup.yaml    # Workgroup F5 optimizado
├── schemas/                # Esquemas de tablas
│   └── f5-logs-table-schema.yaml      # Esquema tabla F5 (33 campos)
└── dashboards/             # Configuraciones de dashboards
```

## Queries F5 Predefinidas

### **1. F5 Error Analysis Enhanced**
- **Archivo**: `queries/f5-error-analysis.sql`
- **Propósito**: Análisis detallado de errores por BigIP/Pool/VirtualServer
- **Métricas**: Error count, response time, unique clients, bytes served

### **2. F5 Performance Analysis Comprehensive**
- **Archivo**: `queries/f5-performance-analysis.sql`
- **Propósito**: Análisis de performance con percentiles y categorización
- **Métricas**: P50/P95/P99 response time, error rates, device detection

### **3. F5 Pool Health Monitoring**
- **Archivo**: `queries/f5-pool-health-monitoring.sql`
- **Propósito**: Monitoreo de salud con scoring automático
- **Métricas**: Pool health score (0-100), error rates, availability

## Configuración de Workgroup

### **F5 Analytics Workgroup**
- **Configuración**: `workgroups/f5-analytics-workgroup.yaml`
- **Características**:
  - Engine Version 3 (latest)
  - 2GB query limit para queries complejas
  - Resultados encriptados (SSE-S3)
  - Configuración enforced

## Esquema F5 (33 Campos)

### **Campos Originales F5 (22)**
- Timestamps, network info, HTTP details
- Performance metrics, F5-specific fields

### **Campos Derivados (11)**
- `is_error`, `is_slow`, `is_mobile`
- `status_category`, `response_time_category`
- `content_category`, `cache_hit`
- Processing metadata

## Uso en CDK Stack

```python
# En analytics_stack.py
# Cargar queries desde assets
queries_dir = "assets/analytics-stack/queries"
for query_file in os.listdir(queries_dir):
    with open(os.path.join(queries_dir, query_file), 'r') as f:
        query_content = f.read()
        # Reemplazar placeholders
        query_content = query_content.replace(
            "DATABASE_NAME_PLACEHOLDER", 
            database_name
        )
```

## Optimizaciones de Queries

- **Particionamiento**: Filtros por year/month para performance
- **Límites**: LIMIT aplicado para evitar queries costosas
- **Agregaciones**: HAVING clauses para filtrar resultados relevantes
- **Percentiles**: PERCENTILE_APPROX para métricas de performance

## Métricas Clave

- **Error Rate**: Porcentaje de errores 4xx/5xx
- **Response Time**: P50, P95, P99 percentiles
- **Pool Health Score**: Algoritmo personalizado (0-100)
- **Traffic Distribution**: Por BigIP, Pool, VirtualServer
- **Device Detection**: Mobile vs Desktop traffic
