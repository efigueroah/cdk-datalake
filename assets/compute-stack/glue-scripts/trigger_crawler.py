"""
Script para triggear el crawler procesado después del ETL
AWS Glue Python Shell Job
"""

import boto3
import sys
from awsglue.utils import getResolvedOptions

# Obtener argumentos
args = getResolvedOptions(sys.argv, ['crawler_name'])

# Cliente de Glue
glue_client = boto3.client('glue')

def trigger_crawler(crawler_name):
    """Triggear el crawler especificado"""
    try:
        print(f"Iniciando crawler: {crawler_name}")
        
        response = glue_client.start_crawler(Name=crawler_name)
        
        print(f"Crawler {crawler_name} iniciado exitosamente")
        return True
        
    except glue_client.exceptions.CrawlerRunningException:
        print(f"Crawler {crawler_name} ya está ejecutándose")
        return True
        
    except Exception as e:
        print(f"Error iniciando crawler {crawler_name}: {str(e)}")
        return False

# Ejecutar
if __name__ == "__main__":
    success = trigger_crawler(args['crawler_name'])
    
    if not success:
        sys.exit(1)
    
    print("Script completado exitosamente")
