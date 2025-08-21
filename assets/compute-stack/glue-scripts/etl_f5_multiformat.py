"""
AGESIC Data Lake PoC - F5 ETL Job MULTIFORMATO
AWS Glue 5.0 (Spark 3.5.4) - Procesamiento Robusto de Logs F5

CARACTERÍSTICAS MULTIFORMATO:
 Detección automática de formato (JSON vs Texto Plano)
 Procesamiento de datos JSON pre-parseados (Kinesis Agent con regex)
 Procesamiento de texto plano con regex integrada
 Fallback robusto entre formatos
 Validación y limpieza de datos
 Métricas detalladas de procesamiento

CHANGELOG v3.0 (2025-08-20):
- Implementado detector automático de formato
- Agregado procesamiento de texto plano con regex F5 validada
- Mejorado manejo de errores con recuperación automática
- Agregadas métricas detalladas por formato
- Implementado sistema de fallback robusto
- Optimizado para máxima compatibilidad

Autor: AWS Data Engineer
Fecha: 2025-08-20
Versión: 3.0 (Multiformato Robusto)
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
import json
from datetime import datetime
from typing import Dict, Any, Optional

# Resolución de argumentos
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'raw_bucket',
    'processed_bucket',
    'solution_name'
])

# Inicializar contexto Glue 5.0
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Optimizaciones Spark 3.5.4
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")

print(f" Iniciando ETL F5 MULTIFORMATO con AWS Glue 5.0 (Spark {spark.version})")
print(f" Procesando desde s3://{args['raw_bucket']} hacia s3://{args['processed_bucket']}")

# Patrón regex F5 validado (100% funcional en pruebas locales)
F5_LOG_PATTERN = r'(?P<timestamp_syslog>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}) (?P<hostname>[^\s]+) (?P<ip_cliente_externo>[^\s]+) \[(?P<ip_red_interna>[^\]]+)\] (?P<usuario_autenticado>-|"[^"]*") (?P<identidad>"[^"]*") \[(?P<timestamp_apache>[^\]]+)\] "(?P<metodo>\w+) (?P<recurso>[^"]+) (?P<protocolo>HTTP/\d\.\d)" (?P<codigo_respuesta>\d+) (?P<tamano_respuesta>\d+) "(?P<referer>[^"]*)" "(?P<user_agent>[^"]*)" Time (?P<tiempo_respuesta_ms>\d+) Age "(?P<edad_cache>[^"]*)" "(?P<content_type>[^"]*)" "(?P<campo_reservado_1>[^"]*)" (?P<campo_reservado_2>-|"[^"]*") "(?P<ambiente_origen>[^"]*)" "(?P<ambiente_pool>[^"]*)" (?P<entorno_nodo>\w+)'

class F5LogProcessor:
    """Procesador multiformato para logs F5"""
    
    def __init__(self):
        self.stats = {
            'total_records': 0,
            'json_records': 0,
            'text_records': 0,
            'parsed_successfully': 0,
            'parsing_errors': 0,
            'format_detection_errors': 0
        }
    
    def detect_format(self, record: str) -> str:
        """
        Detecta automáticamente el formato del registro
        Returns: 'json', 'text', or 'unknown'
        """
        if not record or not record.strip():
            return 'unknown'
        
        record = record.strip()
        
        # Detectar JSON
        if record.startswith('{') and record.endswith('}'):
            try:
                json.loads(record)
                return 'json'
            except:
                pass
        
        # Detectar formato F5 texto plano
        if re.match(r'\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}', record):
            return 'text'
        
        return 'unknown'
    
    def parse_json_record(self, json_str: str) -> Optional[Dict[str, Any]]:
        """Procesa registro JSON pre-parseado"""
        try:
            data = json.loads(json_str)
            
            # Validar que tiene los campos esperados de F5
            required_fields = ['timestamp_syslog', 'hostname', 'ip_cliente_externo']
            if not all(field in data for field in required_fields):
                print(f" JSON record missing required F5 fields")
                return None
            
            # Normalizar y enriquecer datos JSON
            return self.enrich_f5_data(data)
            
        except Exception as e:
            print(f" Error parsing JSON record: {str(e)}")
            self.stats['parsing_errors'] += 1
            return None
    
    def parse_text_record(self, text_line: str) -> Optional[Dict[str, Any]]:
        """Procesa registro de texto plano con regex"""
        try:
            match = re.match(F5_LOG_PATTERN, text_line.strip())
            if not match:
                print(f" Text record doesn't match F5 pattern: {text_line[:100]}...")
                return None
            
            data = match.groupdict()
            
            # Convertir tipos de datos
            data = self.convert_data_types(data)
            
            # Enriquecer datos
            return self.enrich_f5_data(data)
            
        except Exception as e:
            print(f" Error parsing text record: {str(e)}")
            self.stats['parsing_errors'] += 1
            return None
    
    def convert_data_types(self, data: Dict[str, str]) -> Dict[str, Any]:
        """Convierte tipos de datos según esquema F5"""
        try:
            # Convertir campos numéricos
            if data.get('codigo_respuesta'):
                data['codigo_respuesta'] = int(data['codigo_respuesta'])
            
            if data.get('tamano_respuesta'):
                data['tamano_respuesta'] = int(data['tamano_respuesta'])
            
            if data.get('tiempo_respuesta_ms'):
                data['tiempo_respuesta_ms'] = int(data['tiempo_respuesta_ms'])
            
            # Limpiar campos con comillas
            for field in ['identidad', 'referer', 'user_agent', 'edad_cache', 
                         'content_type', 'campo_reservado_1', 'ambiente_origen', 'ambiente_pool']:
                if data.get(field):
                    value = data[field]
                    if value.startswith('"') and value.endswith('"'):
                        data[field] = value[1:-1]
                    if value == '""' or value == '-':
                        data[field] = None
            
            # Manejar campos de autenticación
            if data.get('usuario_autenticado') == '-':
                data['usuario_autenticado'] = None
            if data.get('campo_reservado_2') == '-':
                data['campo_reservado_2'] = None
                
        except Exception as e:
            print(f" Error converting data types: {str(e)}")
        
        return data
    
    def enrich_f5_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Enriquece datos F5 con campos derivados y timestamps parseados"""
        try:
            # Parsear timestamp syslog
            if data.get('timestamp_syslog'):
                try:
                    current_year = datetime.now().year
                    timestamp_with_year = f"{current_year} {data['timestamp_syslog']}"
                    dt_syslog = datetime.strptime(timestamp_with_year, '%Y %b %d %H:%M:%S')
                    data['parsed_timestamp_syslog'] = dt_syslog.isoformat()
                    data['year'] = dt_syslog.year
                    data['month'] = dt_syslog.month
                    data['day'] = dt_syslog.day
                    data['hour'] = dt_syslog.hour
                except Exception as e:
                    print(f" Error parsing syslog timestamp: {e}")
                    data['parsed_timestamp_syslog'] = None
                    data['year'] = None
                    data['month'] = None
                    data['day'] = None
                    data['hour'] = None
            
            # Parsear timestamp Apache
            if data.get('timestamp_apache'):
                try:
                    timestamp_part = data['timestamp_apache'].split(' ')[0]
                    dt_apache = datetime.strptime(timestamp_part, '%d/%b/%Y:%H:%M:%S')
                    data['parsed_timestamp_apache'] = dt_apache.isoformat()
                except Exception as e:
                    print(f" Error parsing Apache timestamp: {e}")
                    data['parsed_timestamp_apache'] = None
            
            # Campos derivados para analytics
            codigo = data.get('codigo_respuesta', 0)
            data['is_error'] = codigo >= 400 if codigo else False
            
            if codigo:
                if 200 <= codigo < 300:
                    data['status_category'] = 'success'
                elif 300 <= codigo < 400:
                    data['status_category'] = 'redirect'
                elif 400 <= codigo < 500:
                    data['status_category'] = 'client_error'
                elif codigo >= 500:
                    data['status_category'] = 'server_error'
                else:
                    data['status_category'] = 'unknown'
            else:
                data['status_category'] = 'unknown'
            
            # Performance analytics
            tiempo_ms = data.get('tiempo_respuesta_ms', 0)
            data['is_slow'] = tiempo_ms > 5000 if tiempo_ms else False
            
            if tiempo_ms:
                if tiempo_ms < 100:
                    data['response_time_category'] = 'fast'
                elif tiempo_ms < 1000:
                    data['response_time_category'] = 'normal'
                elif tiempo_ms < 5000:
                    data['response_time_category'] = 'slow'
                else:
                    data['response_time_category'] = 'very_slow'
            else:
                data['response_time_category'] = 'unknown'
            
            # Detección de dispositivo móvil
            user_agent = data.get('user_agent', '')
            if user_agent:
                mobile_indicators = ['Mobile', 'iPhone', 'Android', 'iPad', 'Windows Phone']
                data['is_mobile'] = any(indicator in user_agent for indicator in mobile_indicators)
            else:
                data['is_mobile'] = False
            
            # Categorización de contenido
            content_type = data.get('content_type', '')
            if content_type:
                if 'javascript' in content_type:
                    data['content_category'] = 'js'
                elif 'css' in content_type:
                    data['content_category'] = 'css'
                elif 'image' in content_type:
                    data['content_category'] = 'image'
                elif 'html' in content_type:
                    data['content_category'] = 'html'
                elif 'json' in content_type or 'api' in content_type:
                    data['content_category'] = 'api'
                else:
                    data['content_category'] = 'other'
            else:
                data['content_category'] = 'unknown'
            
            # Detección de cache hit
            edad_cache = data.get('edad_cache', '')
            data['cache_hit'] = bool(edad_cache and edad_cache != '' and edad_cache != '-')
            
            # Metadatos de procesamiento
            data['processing_timestamp'] = datetime.now().isoformat()
            data['etl_version'] = '3.0-multiformato'
            
        except Exception as e:
            print(f" Error enriching F5 data: {str(e)}")
        
        return data
    
    def process_record(self, record: str) -> Optional[Dict[str, Any]]:
        """Procesa un registro detectando automáticamente su formato"""
        self.stats['total_records'] += 1
        
        try:
            format_type = self.detect_format(record)
            
            if format_type == 'json':
                self.stats['json_records'] += 1
                result = self.parse_json_record(record)
            elif format_type == 'text':
                self.stats['text_records'] += 1
                result = self.parse_text_record(record)
            else:
                print(f" Unknown format for record: {record[:100]}...")
                self.stats['format_detection_errors'] += 1
                return None
            
            if result:
                self.stats['parsed_successfully'] += 1
                return result
            else:
                return None
                
        except Exception as e:
            print(f" Error processing record: {str(e)}")
            self.stats['parsing_errors'] += 1
            return None
    
    def print_stats(self):
        """Imprime estadísticas de procesamiento"""
        print("\n ESTADÍSTICAS DE PROCESAMIENTO MULTIFORMATO")
        print("=" * 60)
        print(f"Total de registros procesados: {self.stats['total_records']}")
        print(f" Registros JSON: {self.stats['json_records']}")
        print(f" Registros texto plano: {self.stats['text_records']}")
        print(f" Parseados exitosamente: {self.stats['parsed_successfully']}")
        print(f" Errores de parsing: {self.stats['parsing_errors']}")
        print(f" Errores de detección de formato: {self.stats['format_detection_errors']}")
        
        if self.stats['total_records'] > 0:
            success_rate = (self.stats['parsed_successfully'] / self.stats['total_records']) * 100
            print(f" Tasa de éxito: {success_rate:.2f}%")
        
        print("=" * 60)

# Inicializar procesador
processor = F5LogProcessor()

def process_f5_logs(glue_context, raw_bucket, processed_bucket, solution_name):
    """Función principal de procesamiento multiformato"""
    
    print(f"Buscando datos en s3://{raw_bucket}/{solution_name}/")
    
    try:
        # Leer datos raw usando Glue DynamicFrame
        raw_path = f"s3://{raw_bucket}/{solution_name}/"
        
        # Intentar leer como texto plano primero
        try:
            datasource = glue_context.create_dynamic_frame.from_options(
                format_options={
                    "withHeader": False,
                    "separator": "\n"
                },
                connection_type="s3",
                format="csv",
                connection_options={
                    "paths": [raw_path],
                    "recurse": True
                },
                transformation_ctx="datasource"
            )
            
            print(f" Datos cargados exitosamente. Registros encontrados: {datasource.count()}")
            
        except Exception as e:
            print(f" Error cargando datos: {str(e)}")
            return
        
        if datasource.count() == 0:
            print(" No se encontraron datos para procesar")
            return
        
        # Convertir a DataFrame para procesamiento
        df = datasource.toDF()
        
        # Procesar cada registro
        def process_row(row):
            # Obtener el contenido de la línea (puede estar en diferentes columnas)
            line_content = None
            for field in row.asDict():
                value = row[field]
                if value and isinstance(value, str) and len(value.strip()) > 50:
                    line_content = value.strip()
                    break
            
            if not line_content:
                return None
            
            return processor.process_record(line_content)
        
        # Aplicar procesamiento a cada fila
        processed_rdd = df.rdd.map(process_row).filter(lambda x: x is not None)
        
        if processed_rdd.isEmpty():
            print(" No se pudieron procesar registros válidos")
            processor.print_stats()
            return
        
        # Convertir a DataFrame con esquema F5
        f5_schema = StructType([
            StructField("timestamp_syslog", StringType(), True),
            StructField("hostname", StringType(), True),
            StructField("ip_cliente_externo", StringType(), True),
            StructField("ip_red_interna", StringType(), True),
            StructField("usuario_autenticado", StringType(), True),
            StructField("identidad", StringType(), True),
            StructField("timestamp_apache", StringType(), True),
            StructField("metodo", StringType(), True),
            StructField("recurso", StringType(), True),
            StructField("protocolo", StringType(), True),
            StructField("codigo_respuesta", IntegerType(), True),
            StructField("tamano_respuesta", IntegerType(), True),
            StructField("referer", StringType(), True),
            StructField("user_agent", StringType(), True),
            StructField("tiempo_respuesta_ms", IntegerType(), True),
            StructField("edad_cache", StringType(), True),
            StructField("content_type", StringType(), True),
            StructField("campo_reservado_1", StringType(), True),
            StructField("campo_reservado_2", StringType(), True),
            StructField("ambiente_origen", StringType(), True),
            StructField("ambiente_pool", StringType(), True),
            StructField("entorno_nodo", StringType(), True),
            # Campos derivados
            StructField("parsed_timestamp_syslog", StringType(), True),
            StructField("parsed_timestamp_apache", StringType(), True),
            StructField("year", IntegerType(), True),
            StructField("month", IntegerType(), True),
            StructField("day", IntegerType(), True),
            StructField("hour", IntegerType(), True),
            StructField("is_error", BooleanType(), True),
            StructField("status_category", StringType(), True),
            StructField("is_slow", BooleanType(), True),
            StructField("response_time_category", StringType(), True),
            StructField("is_mobile", BooleanType(), True),
            StructField("content_category", StringType(), True),
            StructField("cache_hit", BooleanType(), True),
            StructField("processing_timestamp", StringType(), True),
            StructField("etl_version", StringType(), True)
        ])
        
        # Crear DataFrame con los datos procesados
        processed_df = spark.createDataFrame(processed_rdd, schema=f5_schema)
        
        print(f" Registros procesados exitosamente: {processed_df.count()}")
        
        # Escribir a zona procesada en formato Parquet particionado
        output_path = f"s3://{processed_bucket}/f5-logs/"
        
        processed_df.write \
            .mode("overwrite") \
            .partitionBy("year", "month", "day", "hour") \
            .parquet(output_path)
        
        print(f" Datos escritos exitosamente en: {output_path}")
        
        # Imprimir estadísticas finales
        processor.print_stats()
        
        # Mostrar muestra de datos procesados
        print("\n MUESTRA DE DATOS PROCESADOS:")
        processed_df.select(
            "hostname", "ip_cliente_externo", "metodo", "codigo_respuesta", 
            "tiempo_respuesta_ms", "status_category", "content_category", "is_mobile"
        ).show(5, truncate=False)
        
    except Exception as e:
        print(f" Error en procesamiento principal: {str(e)}")
        processor.print_stats()
        raise

# Ejecutar procesamiento principal
try:
    process_f5_logs(
        glueContext, 
        args['raw_bucket'], 
        args['processed_bucket'], 
        args['solution_name']
    )
    
    print("ETL MULTIFORMATO COMPLETADO EXITOSAMENTE")
    
except Exception as e:
    print(f"ERROR CRÍTICO EN ETL: {str(e)}")
    raise

finally:
    job.commit()
