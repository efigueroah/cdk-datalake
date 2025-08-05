# AGESIC Data Lake PoC - AWS CDK

Este proyecto implementa una Proof of Concept (PoC) de un Data Lake para AGESIC utilizando AWS CDK con Python.

## Arquitectura

La solución implementa una arquitectura de Data Lake con los siguientes componentes:

- **Ingesta**: Kinesis Data Streams + Kinesis Data Firehose
- **Almacenamiento**: S3 con arquitectura Medallion (Raw/Processed zones)
- **Procesamiento**: AWS Glue ETL + Lambda para filtrado
- **Catalogación**: AWS Glue Data Catalog + Crawlers
- **Analytics**: Amazon Athena con queries predefinidas
- **Monitoreo**: CloudWatch + SNS para alertas
- **Simulación**: EC2 Spot instances con generador de logs Apache
- **Visualización**: Grafana OSS 12.1.0 con ALB y opcional WAF
- **Conectividad**: SSM Session Manager para acceso seguro

## Estructura del Proyecto

```
agesicdatalake/
├── app.py                      # Aplicación principal CDK
├── cdk.json                    # Configuración CDK y contexto
├── requirements.txt            # Dependencias Python
├── stacks/                     # Stacks CDK organizados por funcionalidad
│   ├── network_stack.py        # VPC, Security Groups y VPC Endpoints
│   ├── storage_stack.py        # Buckets S3 y lifecycle policies
│   ├── streaming_stack.py      # Kinesis Data Streams/Firehose
│   ├── compute_stack.py        # Lambda y Glue jobs
│   ├── analytics_stack.py      # Athena y queries
│   ├── monitoring_stack.py     # CloudWatch y SNS
│   └── ec2_stack.py           # EC2 Spot instances para simulación
├── code/
│   └── lambda/
│       └── log_filter/         # Código Lambda para filtrado
├── assets/
│   ├── glue_scripts/           # Scripts ETL de Glue
│   └── configurations/         # Queries y configuraciones
│       ├── athena_queries.py   # Queries predefinidas de Athena
│       ├── cloudwatch_insights_queries.py  # Queries de CloudWatch Insights
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
export AWS_PROFILE=your-profile
export CDK_DEFAULT_ACCOUNT=123456789012
export CDK_DEFAULT_REGION=us-east-1
```

## Instalación y Despliegue

### 1. Preparar el Ambiente

```bash
# Clonar o descargar el proyecto
cd agesicdatalake

# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate.bat  # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno (opcional)
cp .env.example .env
# Editar .env con tus valores específicos
```

### 2. Configurar AWS CLI

```bash
# Configurar perfil AWS
aws configure --profile your-profile

# Verificar configuración
aws sts get-caller-identity --profile your-profile
```

### 3. Bootstrap CDK (primera vez)

```bash
cdk bootstrap --profile your-profile
```

### 4. Sintetizar Templates

```bash
# Sintetizar todos los stacks
cdk synth --profile your-profile

# Sintetizar stack específico
cdk synth agesic-dl-poc-network --profile your-profile
```

### 5. Validar con CDK Nag

El proyecto incluye validaciones automáticas con CDK Nag que se ejecutan durante `cdk synth`.

### 6. Desplegar (cuando esté listo)

```bash
# Desplegar todos los stacks
cdk deploy --all --profile your-profile

# Desplegar stack específico
cdk deploy agesic-dl-poc-storage --profile your-profile
```

## Orden de Despliegue

Los stacks tienen dependencias y se despliegan en el siguiente orden:

1. `agesic-dl-poc-network` - VPC, Security Groups y VPC Endpoints
2. `agesic-dl-poc-storage` - Buckets S3
3. `agesic-dl-poc-streaming` - Kinesis streams
4. `agesic-dl-poc-compute` - Lambda y Glue jobs
5. `agesic-dl-poc-analytics` - Athena workgroup y queries
6. `agesic-dl-poc-monitoring` - CloudWatch y SNS
7. `agesic-dl-poc-ec2` - EC2 Spot instances para simulación
8. `agesic-dl-poc-visualization` - Grafana OSS 12.1.0 

## Configuración Post-Despliegue

### 1. Verificar Recursos

```bash
# Listar stacks desplegados
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE --profile your-profile

# Verificar buckets S3
aws s3 ls --profile your-profile
```

### 2. Probar Ingesta de Datos

```bash
# Enviar datos de prueba a Kinesis
aws kinesis put-record \
  --stream-name agesic-dl-poc-data-stream \
  --data '{"message": "127.0.0.1 - - [10/Oct/2000:13:55:36 -0700] \"GET /apache_pb.gif HTTP/1.0\" 200 2326 \"http://www.example.com/start.html\" \"Mozilla/4.08 [en] (Win98; I ;Nav)\""}' \
  --partition-key test \
  --profile your-profile
```

### 3. Ejecutar Crawlers

```bash
# Ejecutar crawler de raw zone
aws glue start-crawler --name agesic-dl-poc-raw-crawler --profile your-profile

# Ejecutar crawler de processed zone
aws glue start-crawler --name agesic-dl-poc-processed-crawler --profile your-profile
```

### 4. Conectar a Instancia EC2 via SSM y Controlar Generación

```bash
# Listar instancias EC2
aws ec2 describe-instances --filters "Name=tag:Name,Values=agesic-dl-poc-log-generator" --query "Reservations[].Instances[?State.Name=='running'].InstanceId" --output text --profile your-profile

# Conectar via SSM Session Manager
aws ssm start-session --target i-1234567890abcdef0 --profile your-profile

# Una vez conectado, ir al directorio de trabajo
cd /opt/agesic-datalake

# Ver estado del sistema
./status.sh

# Iniciar generación interactiva (recomendado)
./start_generator.sh

# O usar comandos directos:
# Generar 500 logs
python3 log_generator.py --max-logs 500

# Ejecutar por 30 minutos
python3 log_generator.py --duration 30

# Ver estadísticas
python3 log_generator.py --stats

# Editar configuración
./edit_config.sh
```

### 5. Configurar Parámetros de Generación

El generador usa el archivo `/opt/agesic-datalake/config.json` para configuración:

```json
{
  "generation": {
    "max_logs": 1000,           // Máximo número de logs
    "duration_minutes": 60,     // Duración máxima en minutos
    "interval_min_seconds": 1,  // Intervalo mínimo entre logs
    "interval_max_seconds": 5,  // Intervalo máximo entre logs
  },
  "simulation": {
    "error_rate_percent": 15,   // Porcentaje de logs de error
    "paths": [...],             // Rutas HTTP a simular
    "status_codes": {...}       // Códigos de estado y pesos
  }
}
```

### 6. Monitorear el Sistema

```bash
# Verificar métricas de Kinesis
aws cloudwatch get-metric-statistics \
  --namespace AWS/Kinesis \
  --metric-name IncomingRecords \
  --dimensions Name=StreamName,Value=agesic-dl-poc-data-stream \
  --start-time 2025-01-01T00:00:00Z \
  --end-time 2025-01-01T01:00:00Z \
  --period 300 \
  --statistics Sum \
  --profile your-profile
```

## Queries de Athena Predefinidas

El stack de analytics incluye queries predefinidas:

1. **Error Analysis**: Análisis de patrones de error
2. **Traffic Analysis**: Análisis de tráfico por hora y path
3. **Top IPs**: Análisis de IPs principales
4. **Performance Analysis**: Análisis de tamaños de respuesta
5. **Hourly Summary**: Resumen horario de tráfico

## Monitoreo y Alertas

### CloudWatch Alarms Configuradas

- Kinesis: Sin registros entrantes, iterator age alto
- Lambda: Errores y duración alta
- Glue: Fallos en jobs ETL
- Data Quality: Sin datos procesados

### CloudWatch Insights Queries

- Análisis de errores por código de estado
- Top IPs con errores
- Timeline de errores

## Costos Estimados

**Costo mensual estimado**: USD $35.64 (con optimizaciones)


## Control de Versiones

### Archivos Incluidos en Git

El proyecto incluye `.gitignore` configurado para:
- ✅ **Código fuente**: Todos los archivos `.py`, `.json`, `.md`
- ✅ **Configuración**: `cdk.json`, `requirements.txt`
- ✅ **Assets**: Scripts de Glue, queries, configuraciones
- ✅ **Documentación**: README, especificaciones de seguridad

### Archivos Excluidos de Git

- ❌ **CDK outputs**: `cdk.out/`, `cdk.context.json`
- ❌ **Python cache**: `__pycache__/`, `*.pyc`
- ❌ **Virtual environments**: `.venv/`, `venv/`
- ❌ **Credenciales AWS**: `.aws/`, `credentials`, `*.pem`
- ❌ **Variables de entorno**: `.env` (usar `.env.example`)
- ❌ **IDE files**: `.vscode/`, `.idea/`
- ❌ **Logs**: `*.log`, archivos temporales

### Configuración de Variables de Entorno

```bash
# Copiar template de variables de entorno
cp .env.example .env

# Editar con tus valores
nano .env  # o tu editor preferido
```

**Importante**: Nunca commitear el archivo `.env` ya que puede contener información sensible.

---

## Limpieza de Recursos

```bash
# Eliminar todos los stacks
cdk destroy --all --profile your-profile

# Eliminar stack específico
cdk destroy agesic-dl-poc-monitoring --profile your-profile
```

## Troubleshooting

### Errores Comunes

1. **Bootstrap requerido**: Ejecutar `cdk bootstrap`
2. **Permisos insuficientes**: Verificar políticas IAM
3. **Límites de servicio**: Verificar quotas de AWS
4. **Dependencias de stack**: Desplegar en orden correcto

### Logs Útiles

```bash
# Logs de Lambda
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/agesic-dl-poc" --profile your-profile

# Logs de Glue
aws logs describe-log-groups --log-group-name-prefix "/aws-glue" --profile your-profile

# Logs de Firehose
aws logs describe-log-groups --log-group-name-prefix "/aws/kinesisfirehose" --profile your-profile
```

## Soporte

Para soporte técnico, contactar al equipo de desarrollo o revisar la documentación en `documentos/`.

---

**Nota**: Esta es una PoC diseñada para validación técnica. Para producción, revisar configuraciones de seguridad, alta disponibilidad y backup.
