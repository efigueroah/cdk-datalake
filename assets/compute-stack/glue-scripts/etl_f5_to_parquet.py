"""
AGESIC Data Lake PoC - F5 ETL Job
AWS Glue 5.0 (Spark 3.5.4) - Optimizado para Procesamiento de Logs F5

Características habilitadas en Glue 5.0:
- Spark 3.5.4 con rendimiento mejorado
- Bloom filter joins habilitados por defecto
- Mejor gestión de memoria y escalabilidad de UI
- Runtime Java 17
- Logging mejorado a /aws-glue/jobs/error

CHANGELOG v2.1 (2025-08-19):
- Agregado soporte para formato pre-parseado de Firehose
- Corregido ZeroDivisionError en cálculo de estadísticas
- Agregado soporte para archivos comprimidos (.gz)
- Mejorado manejo de errores y debugging
- Compatibilidad dual de formatos (logs crudos + JSON pre-parseado)

Autor: AWS Data Engineer
Fecha: 2025-08-19
Versión: 2.1 (Compatible con Formato Firehose)
"""

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.sql import functions as F
from pyspark.sql.types import *
import re
from datetime import datetime

# GLUE 5.0: Resolución mejorada de argumentos con mejor manejo de errores
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'raw_bucket',
    'processed_bucket',
    'solution_name'
])

# GLUE 5.0: Inicializar con contexto Spark 3.5.4
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# GLUE 5.0: Habilitar optimizaciones para mejor rendimiento
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")

print(f"Iniciando Job ETL F5 con AWS Glue 5.0 (Spark {spark.version})")
print(f"Procesando logs F5 desde s3://{args['raw_bucket']} hacia s3://{args['processed_bucket']}")

# F5 Log Format regex pattern (from espec_portales_2.re)
F5_LOG_PATTERN = r'(?P<timestamp_syslog>\w{3} \s+\d{1,2} \d{2}:\d{2}:\d{2}) (?P<hostname>[^\s]+) (?P<ip_cliente_externo>[^\s]+) \[(?P<ip_backend_interno>[^\]]+)\] (?P<usuario_autenticado>-|"[^"]*") (?P<identidad>"[^"]*") \[(?P<timestamp_rp>[^\]]+)\] "(?P<metodo>\w+) (?P<request>[^"]+) (?P<protocolo>HTTP/\d\.\d)" (?P<codigo_respuesta>\d+) (?P<tamano_respuesta>\d+) "(?P<referer>[^"]*)" "(?P<user_agent>[^"]*)" Time (?P<tiempo_respuesta_ms>\d+) Age "(?P<edad_cache>[^"]*)" "(?P<content_type>[^"]*)" "(?P<jsession_id>[^"]*)" (?P<campo_reservado_2>-|"[^"]*") "(?P<f5_virtualserver>[^"]*)" "(?P<f5_pool>[^"]*)" (?P<f5_bigip_name>\w+)'

def parse_f5_log(log_line):
    """
    Parse F5 Log Format according to AVRO schema
    """
    if not log_line:
        return None
    
    try:
        match = re.match(F5_LOG_PATTERN, log_line)
        if match:
            data = match.groupdict()
            
            # Parse syslog timestamp (Aug  8 03:33:33)
            try:
                # Convert syslog timestamp to proper format
                timestamp_syslog = data['timestamp_syslog']
                # Add current year since syslog doesn't include it
                current_year = datetime.now().year
                timestamp_with_year = f"{current_year} {timestamp_syslog}"
                dt_syslog = datetime.strptime(timestamp_with_year, '%Y %b %d %H:%M:%S')
                data['parsed_timestamp_syslog'] = dt_syslog.isoformat()
                data['year'] = dt_syslog.year
                data['month'] = dt_syslog.month
                data['day'] = dt_syslog.day
                data['hour'] = dt_syslog.hour
            except Exception as e:
                print(f"Error parseando timestamp syslog: {e}")
                data['parsed_timestamp_syslog'] = None
                data['year'] = None
                data['month'] = None
                data['day'] = None
                data['hour'] = None
            
            # Parsear timestamp HTTP (08/Aug/2025:03:33:33 -0300)
            try:
                timestamp_rp = data['timestamp_rp']
                # Remover información de zona horaria para parseo
                timestamp_part = timestamp_rp.split(' ')[0]
                dt_rp = datetime.strptime(timestamp_part, '%d/%b/%Y:%H:%M:%S')
                data['parsed_timestamp_rp'] = dt_rp.isoformat()
            except Exception as e:
                print(f"Error parseando timestamp HTTP: {e}")
                data['parsed_timestamp_rp'] = None
            
            # Convert numeric fields according to AVRO schema
            try:
                data['codigo_respuesta'] = int(data['codigo_respuesta'])
            except:
                data['codigo_respuesta'] = None
            
            try:
                data['tamano_respuesta'] = int(data['tamano_respuesta'])
            except:
                data['tamano_respuesta'] = 0
            
            try:
                data['tiempo_respuesta_ms'] = int(data['tiempo_respuesta_ms'])
            except:
                data['tiempo_respuesta_ms'] = None
            
            # Handle null/empty fields according to AVRO schema
            nullable_fields = [
                'usuario_autenticado', 'identidad', 'referer', 'user_agent',
                'edad_cache', 'content_type', 'jsession_id', 'campo_reservado_2'
            ]
            
            for field in nullable_fields:
                if data[field] == '-' or data[field] == '""' or not data[field]:
                    data[field] = None
                elif data[field].startswith('"') and data[field].endswith('"'):
                    # Remove quotes
                    data[field] = data[field][1:-1]
            
            # Add derived fields for analytics
            data['is_error'] = data['codigo_respuesta'] >= 400 if data['codigo_respuesta'] else False
            data['status_category'] = (
                'success' if data['codigo_respuesta'] and 200 <= data['codigo_respuesta'] < 300 else
                'redirect' if data['codigo_respuesta'] and 300 <= data['codigo_respuesta'] < 400 else
                'client_error' if data['codigo_respuesta'] and 400 <= data['codigo_respuesta'] < 500 else
                'server_error' if data['codigo_respuesta'] and data['codigo_respuesta'] >= 500 else
                'unknown'
            )
            
            # Performance categorization
            data['is_slow'] = data['tiempo_respuesta_ms'] > 5000 if data['tiempo_respuesta_ms'] else False
            data['is_large'] = data['tamano_respuesta'] > 10485760 if data['tamano_respuesta'] else False  # 10MB
            
            # Extract domain from request
            try:
                request_path = data['request']
                if request_path and request_path != '-':
                    # Extract path components for analytics
                    path_parts = request_path.split('/')
                    data['request_domain'] = path_parts[0] if len(path_parts) > 0 else None
                    data['request_path_depth'] = len([p for p in path_parts if p])
                else:
                    data['request_domain'] = None
                    data['request_path_depth'] = 0
            except:
                data['request_domain'] = None
                data['request_path_depth'] = 0
            
            # Extract file extension
            try:
                request_path = data['request']
                if request_path and '.' in request_path:
                    data['file_extension'] = request_path.split('.')[-1].split('?')[0].lower()
                else:
                    data['file_extension'] = None
            except:
                data['file_extension'] = None
            
            # Enhanced analytics fields
            # Content category
            content_type = data.get('content_type', '') or ''
            data['content_category'] = categorize_content_type(content_type)
            
            # Mobile detection
            user_agent = data.get('user_agent', '') or ''
            data['is_mobile'] = detect_mobile_device(user_agent)
            
            # Cache hit detection
            cache_age = data.get('edad_cache', '') or ''
            data['cache_hit'] = cache_age not in ('', None, '""', '"')
            
            # Response time category
            if data['tiempo_respuesta_ms']:
                if data['tiempo_respuesta_ms'] < 100:
                    data['response_time_category'] = 'fast'
                elif data['tiempo_respuesta_ms'] < 500:
                    data['response_time_category'] = 'normal'
                elif data['tiempo_respuesta_ms'] < 2000:
                    data['response_time_category'] = 'slow'
                else:
                    data['response_time_category'] = 'critical'
            else:
                data['response_time_category'] = 'unknown'
            
            # F5 environment from BigIP name
            data['f5_environment'] = data.get('f5_bigip_name', 'UNKNOWN')
            
            # Processing metadata
            data['processing_timestamp'] = datetime.now().isoformat()
            data['etl_version'] = '2.1.0'
            
            return data
    except Exception as e:
        print(f"Error parseando línea de log F5: {str(e)}")
    
    return None

def categorize_content_type(content_type):
    """Categorizar tipo de contenido para análisis"""
    if not content_type:
        return 'unknown'
    
    content_type = content_type.lower()
    
    if 'text/html' in content_type:
        return 'html'
    elif 'application/javascript' in content_type or 'text/javascript' in content_type:
        return 'javascript'
    elif 'text/css' in content_type:
        return 'css'
    elif 'image/' in content_type:
        return 'image'
    elif 'font/' in content_type or 'woff' in content_type:
        return 'font'
    elif 'application/json' in content_type or 'application/xml' in content_type:
        return 'api'
    elif 'video/' in content_type:
        return 'video'
    elif 'audio/' in content_type:
        return 'audio'
    elif 'application/pdf' in content_type:
        return 'document'
    else:
        return 'other'

def detect_mobile_device(user_agent):
    """Detectar si el request viene de dispositivo móvil"""
    if not user_agent:
        return False
    
    user_agent = user_agent.lower()
    mobile_indicators = [
        'mobile', 'android', 'iphone', 'ipad', 'ipod', 
        'blackberry', 'windows phone', 'opera mini'
    ]
    
    return any(indicator in user_agent for indicator in mobile_indicators)

def process_raw_data():
    """
    Procesar datos crudos F5 desde S3 y convertir a formato Parquet estructurado
    Soporta tanto formato de logs crudos como formato pre-parseado de Firehose
    """
    
    # Configurar Spark para manejar archivos comprimidos
    spark.conf.set("spark.sql.files.ignoreCorruptFiles", "false")
    spark.conf.set("spark.sql.files.ignoreMissingFiles", "false")
    
    # Leer datos crudos desde S3
    raw_path = f"s3://{args['raw_bucket']}/{args['solution_name']}/"
    
    try:
        # Crear dynamic frame desde datos crudos
        raw_dynamic_frame = glueContext.create_dynamic_frame.from_options(
            format_options={
                "multiline": False,
                "withHeader": False
            },
            connection_type="s3",
            format="json",
            connection_options={
                "paths": [raw_path],
                "recurse": True
            },
            transformation_ctx="raw_dynamic_frame"
        )
        
        print(f"Conteo de registros crudos: {raw_dynamic_frame.count()}")
        
        if raw_dynamic_frame.count() == 0:
            print("No se encontraron datos en el bucket origen")
            return
        
        # Convertir a DataFrame para procesamiento
        raw_df = raw_dynamic_frame.toDF()
        
        # Detectar formato de datos: JSON pre-parseado vs logs crudos
        if 'timestamp_syslog' in raw_df.columns and 'ip_cliente_externo' in raw_df.columns:
            # Formato nuevo: datos ya están parseados
            print("Detectado formato F5 pre-parseado - omitiendo parseo con regex")
            use_preparsed_format = True
        elif 'message' in raw_df.columns:
            log_column = 'message'
            use_preparsed_format = False
        elif 'log' in raw_df.columns:
            log_column = 'log'
            use_preparsed_format = False
        else:
            # Tomar la primera columna string
            string_columns = [field.name for field in raw_df.schema.fields if field.dataType == StringType()]
            if string_columns:
                log_column = string_columns[0]
                use_preparsed_format = False
            else:
                print("No se encontró columna de log adecuada")
                return
        
        if use_preparsed_format:
            # Los datos ya están parseados - mapear directamente
            print("Procesando formato pre-parseado...")
            
            # Parsear timestamp_rp para extraer campos de particionado
            structured_df = raw_df.withColumn(
                "parsed_timestamp_rp",
                F.to_timestamp(F.regexp_replace(F.col("timestamp_rp"), r" [-+]\d{4}$", ""), "dd/MMM/yyyy:HH:mm:ss")
            ).withColumn(
                "year", F.year(F.col("parsed_timestamp_rp"))
            ).withColumn(
                "month", F.month(F.col("parsed_timestamp_rp"))
            ).withColumn(
                "day", F.dayofmonth(F.col("parsed_timestamp_rp"))
            ).withColumn(
                "hour", F.hour(F.col("parsed_timestamp_rp"))
            ).select(
                # Crear campo raw_log para compatibilidad
                F.concat_ws(" ", 
                    F.col("timestamp_syslog"),
                    F.col("hostname"),
                    F.col("ip_cliente_externo"),
                    F.col("metodo"),
                    F.col("request"),
                    F.col("protocolo"),
                    F.col("codigo_respuesta"),
                    F.col("tamano_respuesta")
                ).alias("raw_log"),
                
                # Mapear campos existentes directamente
                F.col("timestamp_syslog"),
                F.col("hostname"),
                F.col("ip_cliente_externo"),
                F.col("ip_backend_interno"),
                F.col("usuario_autenticado"),
                F.col("identidad"),
                F.col("timestamp_rp"),
                F.col("metodo"),
                F.col("request"),
                F.col("protocolo"),
                F.col("codigo_respuesta").cast(IntegerType()),
                F.col("tamano_respuesta").cast(IntegerType()),
                F.col("referer"),
                F.col("user_agent"),
                F.col("tiempo_respuesta_ms").cast(IntegerType()),
                F.col("edad_cache"),
                F.col("content_type"),
                F.col("jsession_id"),
                F.col("campo_reservado_2"),
                F.col("f5_virtualserver"),
                F.col("f5_pool"),
                F.col("f5_bigip_name"),
                F.col("processed_at"),
                F.col("log_type"),
                
                # Timestamps parseados y campos de particionado
                F.col("parsed_timestamp_rp"),
                F.col("year"),
                F.col("month"),
                F.col("day"),
                F.col("hour")
            )
            
        else:
            # Lógica de parseo original para logs crudos
            print("Procesando formato de logs crudos...")
            
            # Procesar líneas de log
            def parse_log_udf(log_line):
                return parse_f5_log(log_line)
            
            # Registrar UDF
            from pyspark.sql.functions import udf
            parse_udf = udf(parse_log_udf, MapType(StringType(), StringType()))
            
            # Parsear logs y crear datos estructurados
            parsed_df = raw_df.select(
                F.col(log_column).alias("raw_log"),
                parse_udf(F.col(log_column)).alias("parsed_data")
            ).filter(
                F.col("parsed_data").isNotNull()
            )
            
            # Expandir datos parseados en columnas según esquema AVRO
            structured_df = parsed_df.select(
                F.col("raw_log"),
                # Campos core F5
                F.col("parsed_data.timestamp_syslog").alias("timestamp_syslog"),
                F.col("parsed_data.hostname").alias("hostname"),
                F.col("parsed_data.ip_cliente_externo").alias("ip_cliente_externo"),
                F.col("parsed_data.ip_backend_interno").alias("ip_backend_interno"),
                F.col("parsed_data.usuario_autenticado").alias("usuario_autenticado"),
                F.col("parsed_data.identidad").alias("identidad"),
                F.col("parsed_data.timestamp_rp").alias("timestamp_rp"),
                F.col("parsed_data.metodo").alias("metodo"),
                F.col("parsed_data.request").alias("request"),
                F.col("parsed_data.protocolo").alias("protocolo"),
                F.col("parsed_data.codigo_respuesta").cast(IntegerType()).alias("codigo_respuesta"),
                F.col("parsed_data.tamano_respuesta").cast(LongType()).alias("tamano_respuesta"),
                F.col("parsed_data.referer").alias("referer"),
                F.col("parsed_data.user_agent").alias("user_agent"),
                F.col("parsed_data.tiempo_respuesta_ms").cast(IntegerType()).alias("tiempo_respuesta_ms"),
                F.col("parsed_data.edad_cache").alias("edad_cache"),
                F.col("parsed_data.content_type").alias("content_type"),
                F.col("parsed_data.jsession_id").alias("jsession_id"),
                F.col("parsed_data.campo_reservado_2").alias("campo_reservado_2"),
                F.col("parsed_data.f5_virtualserver").alias("f5_virtualserver"),
                F.col("parsed_data.f5_pool").alias("f5_pool"),
                F.col("parsed_data.f5_bigip_name").alias("f5_bigip_name"),
                # Timestamps parseados
                F.col("parsed_data.parsed_timestamp_syslog").alias("parsed_timestamp_syslog"),
                F.col("parsed_data.parsed_timestamp_rp").alias("parsed_timestamp_rp"),
                # Campos de particionado
                F.col("parsed_data.year").cast(IntegerType()).alias("year"),
                F.col("parsed_data.month").cast(IntegerType()).alias("month"),
                F.col("parsed_data.day").cast(IntegerType()).alias("day"),
                F.col("parsed_data.hour").cast(IntegerType()).alias("hour")
            )
        
        # Agregar campos de enriquecimiento (compatible con ambos formatos)
        enriched_df = structured_df.withColumn(
            "status_category",
            F.when(F.col("codigo_respuesta") < 300, "Success")
             .when(F.col("codigo_respuesta") < 400, "Redirect")
             .when(F.col("codigo_respuesta") < 500, "Client Error")
             .otherwise("Server Error")
        ).withColumn(
            "response_time_category",
            F.when(F.col("tiempo_respuesta_ms") < 1000, "Fast")
             .when(F.col("tiempo_respuesta_ms") < 5000, "Normal")
             .otherwise("Slow")
        ).withColumn(
            "is_error",
            F.col("codigo_respuesta") >= 400
        ).withColumn(
            "is_slow",
            F.col("tiempo_respuesta_ms") > 5000
        ).withColumn(
            "processing_date",
            F.current_date()
        ).withColumn(
            "processing_timestamp",
            F.current_timestamp()
        ).withColumn(
            "etl_version",
            F.lit("2.1.0")
        )
        
        # Calcular estadísticas de forma segura
        total_records = enriched_df.count()
        print(f"Conteo de registros estructurados: {total_records}")
        
        if total_records > 0:
            # Calcular estadísticas de errores y respuestas lentas
            error_records = enriched_df.filter(F.col("codigo_respuesta") >= 400).count()
            slow_records = enriched_df.filter(F.col("tiempo_respuesta_ms") > 5000).count()
            
            print("Estadísticas de Procesamiento:")
            print(f"  Total de registros: {total_records}")
            print(f"  Registros con error (4xx/5xx): {error_records}")
            print(f"  Registros lentos (>5s): {slow_records}")
            print(f"  Tasa de error: {(error_records/total_records)*100:.2f}%")
            print(f"  Tasa de respuesta lenta: {(slow_records/total_records)*100:.2f}%")
            
            # Mostrar datos de muestra para verificación
            print("\nRegistros procesados de muestra:")
            enriched_df.select("hostname", "metodo", "codigo_respuesta", "tiempo_respuesta_ms", "status_category").show(5, truncate=False)
            
        else:
            print("Advertencia: No se procesaron registros exitosamente")
            print("Información de debug:")
            print(f"  Conteo de registros crudos: {raw_dynamic_frame.count()}")
            print(f"  Columnas del DataFrame crudo: {raw_df.columns}")
            print("  Datos crudos de muestra:")
            raw_df.show(2, truncate=False)
            return
        
        # Convertir de vuelta a DynamicFrame
        structured_dynamic_frame = DynamicFrame.fromDF(
            enriched_df,
            glueContext,
            "structured_dynamic_frame"
        )
        
        # Escribir al bucket procesado en formato Parquet con particionado
        processed_path = f"s3://{args['processed_bucket']}/{args['solution_name']}/"
        
        glueContext.write_dynamic_frame.from_options(
            frame=structured_dynamic_frame,
            connection_type="s3",
            format="glueparquet",
            connection_options={
                "path": processed_path,
                "partitionKeys": ["year", "month", "day", "hour"]
            },
            format_options={
                "compression": "snappy"
            },
            transformation_ctx="write_processed_data"
        )
        
        print(f"Procesamiento exitoso y escritura de datos F5 a {processed_path}")
        
    except Exception as e:
        print(f"Error procesando datos F5: {str(e)}")
        raise

# Ejecución principal
if __name__ == "__main__":
    process_raw_data()
    job.commit()
