# AGESIC Data Lake - Compute Stack Assets

## Estructura de Assets

```
assets/compute-stack/
├── glue-scripts/           # Scripts ETL para AWS Glue
│   ├── etl_f5_multiformat.py  # ETL principal con detección automática
│   ├── etl_f5_to_parquet.py   # ETL legacy (backup)
│   └── trigger_crawler.py     # Script para triggear crawlers
├── lambda/                 # Funciones Lambda
├── kinesis-agent/          # Configuraciones Kinesis Agent
│   ├── agent-config-text-plain.json    # Modo texto plano (recomendado)
│   └── agent-config-json-regex.json    # Modo JSON con regex
├── configurations/         # Configuraciones de Glue Jobs y Crawlers
│   └── glue-jobs-config.yaml  # Configuración completa de jobs
└── crawlers/               # Configuraciones de crawlers
```

## Componentes Principales

### **ETL Multiformato (Principal)**
- **Archivo**: `glue-scripts/etl_f5_multiformat.py`
- **Función**: Detección automática de formato (JSON vs Texto Plano)
- **Características**: 
  - Regex F5 validada al 100%
  - 33 campos enriquecidos (22 F5 + 11 derivados)
  - Fallback robusto entre formatos
  - Métricas CloudWatch personalizadas

### **Kinesis Agent Configuraciones**
- **Texto Plano**: `kinesis-agent/agent-config-text-plain.json` ✅ **Recomendado**
- **JSON con Regex**: `kinesis-agent/agent-config-json-regex.json` (experimental)

### **Configuración de Jobs**
- **Archivo**: `configurations/glue-jobs-config.yaml`
- **Contenido**: Configuración completa de Glue Jobs y Crawlers
- **Uso**: Referencia para parámetros de CDK

## Uso en CDK Stack

```python
# En compute_stack.py
glue_scripts_deployment = s3deploy.BucketDeployment(
    self, "GlueScriptsDeployment",
    sources=[s3deploy.Source.asset("assets/compute-stack/glue-scripts")],
    destination_bucket=raw_bucket,
    destination_key_prefix="scripts/",
    retain_on_delete=False
)
```

## Métricas y Monitoreo

- **CloudWatch Logs**: Habilitado en todos los jobs
- **Spark UI**: Disponible para debugging
- **Métricas personalizadas**: Namespace `agesic-dl-poc/F5Analytics`
- **Job Bookmarks**: Deshabilitado en multiformato para reprocessing

## Optimizaciones

- **Glue Version**: 5.0 (Spark 3.5.4)
- **Worker Type**: G.1X (optimizado para costo/performance)
- **Particionamiento**: Por año/mes/día/hora para queries eficientes
- **Compresión**: Snappy para balance tamaño/velocidad
