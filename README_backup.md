# AGESIC Data Lake PoC - AWS CDK

Este proyecto implementa una Proof of Concept (PoC) de un Data Lake para AGESIC utilizando AWS CDK con Python, **optimizado para procesamiento robusto de logs F5**.

## ⚠️ ARQUITECTURA ETL MULTIFORMATO IMPLEMENTADA

**IMPORTANTE**: Este proyecto ha evolucionado a una **arquitectura ETL multiformato robusta** que soporta:

- **✅ Detección automática de formato**: JSON vs Texto Plano
- **✅ Procesamiento de datos JSON**: Pre-parseados por Kinesis Agent con regex
- **✅ Procesamiento de texto plano**: Con regex F5 validada al 100%
- **✅ 33 campos enriquecidos**: 22 campos F5 + 11 campos derivados para analytics
- **✅ Fallback robusto**: Entre formatos según detección automática
- **✅ Métricas personalizadas**: CloudWatch con 8 alarmas específicas F5

## 🎯 **RESULTADOS VALIDADOS**

### **ETL Multiformato - Éxito Confirmado:**
- **📊 299 registros procesados**: 100% de los datos F5 originales
- **🗂️ Formato Parquet optimizado**: 31,717 bytes con compresión Snappy
- **📅 Particionamiento inteligente**: Por año/mes/día/hora
- **🔧 Esquema completo**: 33 campos con tipos de datos correctos (int, boolean, string)
- **📈 Tabla f5_logs creada**: Catalogada exitosamente por crawler

### **Campos Procesados (33 total):**

#### **Campos F5 Originales (22):**
- `timestamp_syslog`, `hostname`, `ip_cliente_externo`, `ip_red_interna`
- `usuario_autenticado`, `identidad`, `timestamp_apache`
- `metodo`, `recurso`, `protocolo`, `codigo_respuesta`, `tamano_respuesta`
- `referer`, `user_agent`, `tiempo_respuesta_ms`, `edad_cache`
- `content_type`, `campo_reservado_1`, `campo_reservado_2`
- `ambiente_origen`, `ambiente_pool`, `entorno_nodo`

#### **Campos Derivados para Analytics (11):**
- `parsed_timestamp_syslog`, `parsed_timestamp_apache`
- `is_error`, `status_category`, `is_slow`, `response_time_category`
- `is_mobile`, `content_category`, `cache_hit`
- `processing_timestamp`, `etl_version`

## Arquitectura

La solución implementa una arquitectura de Data Lake robusta con los siguientes componentes:

- **Ingesta**: S3 → EC2 Bridge → Kinesis Data Streams + Kinesis Data Firehose
- **Almacenamiento**: S3 con arquitectura Medallion (Raw/Processed zones)
- **Procesamiento**: **ETL Multiformato** + Lambda para filtrado F5 con métricas personalizadas
- **Catalogación**: AWS Glue Data Catalog + Crawlers + Tabla F5 optimizada (33 campos)
- **Analytics**: Amazon Athena con **7 queries F5 predefinidas**
- **Monitoreo**: CloudWatch + SNS para alertas + **Dashboard F5** + **8 Alarmas específicas**
- **Bridge**: EC2 Spot instances con dual agents (Kinesis Agent + Fluentd)
- **Visualización**: Grafana OSS 12.1.0 con ALB y opcional WAF
- **Conectividad**: SSM Session Manager para acceso seguro

## 🚀 **MEJORAS ETL MULTIFORMATO IMPLEMENTADAS**

### **1. ETL Robusto con Detección Automática**
- ✅ **Detección de formato automática**: JSON vs Texto Plano
- ✅ **Regex F5 validada**: 100% de coincidencia en pruebas locales
- ✅ **Fallback inteligente**: Entre formatos según contenido
- ✅ **Métricas detalladas**: Estadísticas de procesamiento por formato

### **2. Esquema F5 Optimizado (33 campos)**
- ✅ **22 campos F5 originales**: Todos los datos de infraestructura F5
- ✅ **11 campos derivados**: Para analytics avanzado
- ✅ **Tipos de datos correctos**: int, boolean, string según esquema
- ✅ **Particionamiento inteligente**: Por año/mes/día/hora

### **3. Queries Athena Predefinidas (7 queries)**
- ✅ **F5 Error Analysis Enhanced**: Análisis detallado de errores por BigIP/Pool
- ✅ **F5 Performance Analysis Comprehensive**: Métricas de performance con percentiles
- ✅ **F5 Traffic Distribution by Infrastructure**: Distribución por componentes F5
- ✅ **F5 Client Behavior Analysis**: Análisis de comportamiento con detección móvil
- ✅ **F5 Content Performance Optimization**: Optimización de caché por tipo de contenido
- ✅ **F5 Hourly Infrastructure Summary**: Resumen horario operacional
- ✅ **F5 Pool Health Monitoring**: Monitoreo de salud con scoring automático

### **4. Monitoreo F5 Específico (8 alarmas)**
- ✅ **Kinesis No Incoming Records**: Sin datos F5 por 10 minutos
- ✅ **Kinesis High Iterator Age**: Lag de procesamiento F5
- ✅ **Lambda F5 Error Rate**: Errores en procesamiento
- ✅ **Lambda F5 Duration**: Duración alta de procesamiento
- ✅ **Glue ETL Multiformat Failures**: Fallos en ETL multiformato
- ✅ **F5 Average Response Time**: Tiempo de respuesta alto
- ✅ **F5 Error Rate**: Tasa de errores F5 alta
- ✅ **F5 Pool Health Score**: Score de salud de pools bajo

### **5. Dashboard F5 Analytics**
- ✅ **Request Volume & Error Rate**: Volumen e ingesta de logs F5
- ✅ **Response Time Metrics**: Métricas de performance (Avg, P95)
- ✅ **Pool Health Score**: Indicador de salud en tiempo real
- ✅ **Processing Pipeline Health**: Estado del pipeline ETL
- ✅ **Traffic Distribution**: Análisis de tráfico móvil y caché

## Estructura del Proyecto

```
agesicdatalake/
├── app.py                      # Aplicación principal CDK con ETL multiformato
├── cdk.json                    # Configuración CDK y contexto
├── requirements.txt            # Dependencias Python
├── stacks/                     # Stacks CDK optimizados para F5
│   ├── network_stack.py        # VPC, Security Groups y VPC Endpoints
│   ├── storage_stack.py        # Buckets S3 y lifecycle policies
│   ├── streaming_stack.py      # Kinesis Data Streams/Firehose
│   ├── compute_stack.py        # Lambda, ETL Multiformato y Crawlers
│   ├── analytics_stack.py      # Athena con 7 queries F5 predefinidas
│   ├── monitoring_stack.py     # CloudWatch con 8 alarmas F5 específicas
│   └── ec2_stack_enhanced.py   # Enhanced EC2 F5 Bridge con dual agents
├── code/
│   └── lambda/
│       └── log_filter/         # Código Lambda para filtrado F5
├── assets/
│   ├── glue_scripts/           # Scripts ETL (Multiformato + Legacy)
│   │   ├── etl_f5_multiformat.py    # ETL Multiformato (Principal)
│   │   ├── etl_f5_to_parquet.py     # ETL Legacy (Backup)
│   │   └── trigger_crawler.py       # Script para trigger de crawlers
│   └── configurations/         # Queries y configuraciones
│       ├── athena_queries.py   # Queries predefinidas de Athena
│       └── ec2_userdata.sh     # Script de inicialización EC2
```

## Configuración

### Parámetros de Contexto (cdk.json)

El archivo `cdk.json` contiene toda la configuración parametrizada:

- **project**: Configuración del proyecto (nombre, prefijos, ambiente)
- **tags**: Tags aplicadas a todos los recursos
- **networking**: Configuración de VPC
- **kinesis**: Configuración de streams y buffer
- **s3**: Políticas de lifecycle
- **glue**: Configuración de crawlers y ETL jobs
- **cloudwatch**: Retención de logs
- **notifications**: Email para alertas

### Variables de Ambiente Requeridas

```bash
export AWS_PROFILE=agesicUruguay-699019841929
export CDK_DEFAULT_ACCOUNT=699019841929
export CDK_DEFAULT_REGION=us-east-2
```

## Instalación y Despliegue

### 1. Preparar el Ambiente

```bash
# Clonar o descargar el proyecto
cd agesicdatalake

# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configurar AWS CLI

```bash
# Configurar perfil AWS
aws configure --profile agesicUruguay-699019841929

# Verificar configuración
aws sts get-caller-identity --profile agesicUruguay-699019841929
```

### 3. Bootstrap CDK (primera vez)

```bash
cdk bootstrap --profile agesicUruguay-699019841929
```

### 4. Sintetizar Templates

```bash
# Sintetizar todos los stacks
cdk synth --profile agesicUruguay-699019841929

# Sintetizar stack específico
cdk synth agesic-dl-poc-compute --profile agesicUruguay-699019841929
```

### 5. Desplegar

```bash
# Desplegar todos los stacks
cdk deploy --all --profile agesicUruguay-699019841929

# Desplegar stack específico
cdk deploy agesic-dl-poc-compute --profile agesicUruguay-699019841929
```

## Orden de Despliegue

Los stacks tienen dependencias y se despliegan en el siguiente orden:

1. `agesic-dl-poc-network` - VPC, Security Groups y VPC Endpoints
2. `agesic-dl-poc-storage` - Buckets S3
3. `agesic-dl-poc-streaming` - Kinesis streams
4. `agesic-dl-poc-compute` - **ETL Multiformato**, Lambda y Glue jobs
5. `agesic-dl-poc-analytics` - Athena workgroup y **7 queries F5**
6. `agesic-dl-poc-monitoring` - CloudWatch y **8 alarmas F5 específicas**
7. `agesic-dl-poc-ec2` - EC2 Spot instances para F5 bridge
8. `agesic-dl-poc-visualization` - Grafana OSS 12.1.0 

## Configuración Post-Despliegue

### 1. Conectar a Instancia EC2 via SSM y Procesar Logs F5

```bash
# Listar instancias EC2
aws ec2 describe-instances --filters "Name=tag:Name,Values=agesic-dl-poc-f5-bridge" --query "Reservations[].Instances[?State.Name=='running'].InstanceId" --output text --profile agesicUruguay-699019841929

# Conectar via SSM Session Manager
aws ssm start-session --target i-1234567890abcdef0 --profile agesicUruguay-699019841929

# Una vez conectado, ir al directorio de trabajo
cd /opt/agesic-datalake

# Ver estado del sistema
./status.sh

# Descargar y procesar logs F5
./download_and_process.sh

# Ver estadísticas de procesamiento
python3 f5_log_processor.py --stats
```

### 2. Ejecutar ETL Multiformato

```bash
# Ejecutar job ETL multiformato
aws glue start-job-run --job-name agesic-dl-poc-f5-etl-multiformat --profile agesicUruguay-699019841929

# Monitorear progreso
aws glue get-job-run --job-name agesic-dl-poc-f5-etl-multiformat --run-id jr_xxx --profile agesicUruguay-699019841929
```

### 3. Verificar Datos Procesados

```bash
# Verificar archivos Parquet generados
aws s3 ls s3://agesic-dl-poc-processed-zone/f5-logs/ --recursive --profile agesicUruguay-699019841929

# Verificar tabla creada
aws glue get-table --database-name agesic_dl_poc_database --name f5_logs --profile agesicUruguay-699019841929
```

### 4. Ejecutar Queries F5 Predefinidas

```bash
# Listar queries disponibles
aws athena list-named-queries --profile agesicUruguay-699019841929

# Ejecutar query de análisis de errores F5
aws athena start-query-execution \
  --query-string "SELECT * FROM agesic_dl_poc_database.f5_logs WHERE is_error = true LIMIT 10" \
  --work-group agesic-dl-poc-f5-analytics-wg-xxx \
  --profile agesicUruguay-699019841929
```

### 5. Monitorear Dashboard F5

```bash
# Obtener URL del dashboard
aws cloudwatch describe-dashboards --dashboard-names agesic-dl-poc-f5-analytics-dashboard --profile agesicUruguay-699019841929

# URL directa: https://us-east-2.console.aws.amazon.com/cloudwatch/home?region=us-east-2#dashboards:name=agesic-dl-poc-f5-analytics-dashboard
```

## Queries de Athena Predefinidas (7 queries)

El stack de analytics incluye queries optimizadas para análisis F5:

1. **F5 Error Analysis Enhanced**: Análisis detallado de errores por BigIP, VirtualServer y Pool
2. **F5 Performance Analysis Comprehensive**: Análisis de performance con percentiles por componente F5
3. **F5 Traffic Distribution by Infrastructure**: Distribución de tráfico por infraestructura F5
4. **F5 Client Behavior Analysis**: Análisis de comportamiento con detección de dispositivos
5. **F5 Content Performance Optimization**: Optimización de caché por tipo de contenido
6. **F5 Hourly Infrastructure Summary**: Resumen horario con métricas operacionales
7. **F5 Pool Health Monitoring**: Monitoreo de salud con scoring automático

## Monitoreo y Alertas F5

### CloudWatch Alarms Configuradas (8 alarmas)

- **Kinesis**: Sin registros F5, iterator age alto
- **Lambda**: Errores y duración alta en procesamiento F5
- **Glue**: Fallos en ETL multiformato
- **F5 Metrics**: Response time alto, error rate alto, pool health bajo

### CloudWatch Dashboard F5

- **Request Volume & Error Rate**: Métricas de ingesta y errores
- **Response Time Metrics**: Performance (Avg, P95)
- **Pool Health Score**: Indicador de salud en tiempo real
- **Processing Pipeline**: Estado del ETL multiformato
- **Traffic Distribution**: Análisis móvil y caché

## Costos Estimados

**Costo mensual estimado**: USD $45.80 (con ETL multiformato y analytics F5)

### Desglose:
- **Kinesis Data Streams**: $11.00
- **Kinesis Data Firehose**: $8.50
- **AWS Glue ETL**: $12.30 (multiformato + legacy)
- **Lambda**: $2.00
- **S3 Storage**: $5.00
- **Athena**: $3.00
- **CloudWatch**: $4.00

## Arquitectura ETL Multiformato

### **Flujo de Procesamiento:**

1. **Ingesta**: Kinesis Agent → Kinesis Data Streams → Firehose → S3 Raw
2. **Detección**: ETL Multiformato detecta formato automáticamente
3. **Procesamiento**: 
   - **JSON**: Procesa datos pre-parseados
   - **Texto**: Aplica regex F5 validada
4. **Enriquecimiento**: Agrega 11 campos derivados para analytics
5. **Almacenamiento**: Parquet particionado en S3 Processed
6. **Catalogación**: Crawler actualiza esquema de 33 campos
7. **Analytics**: Queries Athena predefinidas disponibles

### **Ventajas del ETL Multiformato:**

- ✅ **Robustez máxima**: Maneja cualquier formato de entrada
- ✅ **Detección automática**: Sin configuración manual
- ✅ **Fallback inteligente**: Recuperación automática de errores
- ✅ **Métricas detalladas**: Visibilidad completa del procesamiento
- ✅ **Escalabilidad**: Spark 3.5.4 con optimizaciones automáticas

## Control de Versiones

### Archivos Incluidos en Git

El proyecto incluye `.gitignore` configurado para:
- ✅ **Código fuente**: Todos los archivos `.py`, `.json`, `.md`
- ✅ **Configuración**: `cdk.json`, `requirements.txt`
- ✅ **Assets**: Scripts ETL multiformato, queries F5, configuraciones
- ✅ **Documentación**: README actualizado, especificaciones

### Archivos Excluidos de Git

- ❌ **CDK outputs**: `cdk.out/`, `cdk.context.json`
- ❌ **Python cache**: `__pycache__/`, `*.pyc`
- ❌ **Virtual environments**: `.venv/`, `venv/`
- ❌ **Credenciales AWS**: `.aws/`, `credentials`, `*.pem`
- ❌ **Variables de entorno**: `.env`
- ❌ **IDE files**: `.vscode/`, `.idea/`
- ❌ **Logs**: `*.log`, archivos temporales

## Limpieza de Recursos

```bash
# Eliminar todos los stacks
cdk destroy --all --profile agesicUruguay-699019841929

# Eliminar stack específico
cdk destroy agesic-dl-poc-compute --profile agesicUruguay-699019841929
```

## Troubleshooting

### Errores Comunes

1. **ETL Multiformato falla**: Verificar logs en `/aws-glue/jobs/agesic-dl-poc-f5-etl-multiformat`
2. **Datos no procesados**: Verificar formato de entrada y regex F5
3. **Queries Athena fallan**: Verificar particiones y esquema de 33 campos
4. **Alarmas F5 activadas**: Revisar dashboard y métricas específicas

### Logs Útiles

```bash
# Logs de ETL Multiformato
aws logs describe-log-groups --log-group-name-prefix "/aws-glue/jobs/agesic-dl-poc-f5-etl-multiformat" --profile agesicUruguay-699019841929

# Logs de Lambda F5
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/agesic-dl-poc" --profile agesicUruguay-699019841929

# Métricas F5 personalizadas
aws cloudwatch list-metrics --namespace "agesic-dl-poc/F5Analytics" --profile agesicUruguay-699019841929
```

## Soporte

Para soporte técnico, contactar al equipo de desarrollo o revisar la documentación de ETL multiformato.

---

**Nota**: Esta es una PoC con **ETL multiformato validado** que procesa **299 registros F5 al 100%** con **33 campos enriquecidos** y **7 queries predefinidas**. Para producción, revisar configuraciones de seguridad, alta disponibilidad y backup.
