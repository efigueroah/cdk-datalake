from aws_cdk import (
    Stack,
    aws_athena as athena,
    aws_s3 as s3,
    CfnOutput,
    RemovalPolicy
)
from constructs import Construct
import os
import hashlib
import time
import yaml

class AnalyticsStack(Stack):
    
    def __init__(self, scope: Construct, construct_id: str, 
                 processed_bucket: s3.Bucket, athena_results_bucket: s3.Bucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Obtener valores de contexto
        project_config = self.node.try_get_context("project")
        
        # Generar sufijo único para evitar conflictos
        timestamp = str(int(time.time()))
        unique_suffix = hashlib.md5(f"{construct_id}-{timestamp}".encode()).hexdigest()[:8]
        
        # Cargar configuración de workgroup desde assets
        workgroup_config_path = os.path.join(
            os.path.dirname(__file__), 
            "..", 
            "assets", 
            "analytics-stack", 
            "workgroups", 
            "f5-analytics-workgroup.yaml"
        )
        
        try:
            with open(workgroup_config_path, 'r') as f:
                workgroup_config = yaml.safe_load(f)
        except FileNotFoundError:
            # Configuración de respaldo
            workgroup_config = {
                "workgroup": {
                    "name": "f5-analytics-wg",
                    "description": "Workgroup para análisis F5 (respaldo)"
                }
            }
        
        # Workgroup de Athena usando configuración de assets
        workgroup_name = f"{project_config['prefix']}-f5-analytics-wg-{unique_suffix}"
        self.athena_workgroup = athena.CfnWorkGroup(
            self, "AthenaWorkGroup",
            name=workgroup_name,
            description=workgroup_config["workgroup"]["description"],
            state="ENABLED",
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{athena_results_bucket.bucket_name}/f5-query-results/",
                    encryption_configuration=athena.CfnWorkGroup.EncryptionConfigurationProperty(
                        encryption_option="SSE_S3"
                    )
                ),
                enforce_work_group_configuration=True,
                bytes_scanned_cutoff_per_query=2000000000,  # Límite de 2GB para queries F5 complejas
                engine_version=athena.CfnWorkGroup.EngineVersionProperty(
                    selected_engine_version="Athena engine version 3"  # Versión más reciente
                )
            )
        )
        
        # Cargar queries F5 desde assets
        queries_dir = os.path.join(
            os.path.dirname(__file__), 
            "..", 
            "assets", 
            "analytics-stack", 
            "queries"
        )
        
        self.named_queries = {}
        database_name = f"{project_config['prefix'].replace('-', '_')}_database"
        
        # Procesar cada archivo SQL en el directorio de queries
        if os.path.exists(queries_dir):
            for query_file in os.listdir(queries_dir):
                if query_file.endswith('.sql'):
                    query_id = query_file.replace('.sql', '').replace('-', '_')
                    query_path = os.path.join(queries_dir, query_file)
                    
                    try:
                        with open(query_path, 'r') as f:
                            query_content = f.read()
                        
                        # Reemplazar marcadores de posición
                        query_content = query_content.replace(
                            "DATABASE_NAME_PLACEHOLDER", 
                            database_name
                        )
                        
                        # Crear query con nombre
                        query_name = f"{project_config['prefix']}-{query_id}-{unique_suffix}"
                        named_query = athena.CfnNamedQuery(
                            self, f"NamedQuery{query_id.title().replace('_', '')}",
                            name=query_name,
                            description=f"Query F5 desde assets: {query_file}",
                            database=database_name,
                            query_string=query_content,
                            work_group=self.athena_workgroup.name
                        )
                        # Agregar dependencia explícita
                        named_query.add_dependency(self.athena_workgroup)
                        self.named_queries[query_id] = named_query
                        
                    except Exception as e:
                        print(f"Error cargando query {query_file}: {e}")
        
        # Queries de respaldo si no se encuentran assets
        if not self.named_queries:
            fallback_query_string = f"""
            SELECT 
                entorno_nodo as f5_bigip,
                ambiente_pool as f5_pool,
                COUNT(*) as request_count,
                AVG(tiempo_respuesta_ms) as avg_response_time_ms
            FROM "{database_name}"."f5_logs"
            WHERE year = '2025' AND month = '8'
            GROUP BY entorno_nodo, ambiente_pool
            ORDER BY request_count DESC
            LIMIT 50
            """
            
            fallback_query = athena.CfnNamedQuery(
                self, "FallbackQuery",
                name=f"{project_config['prefix']}-fallback-query-{unique_suffix}",
                description="Query F5 básica de respaldo",
                database=database_name,
                query_string=fallback_query_string,
                work_group=self.athena_workgroup.name
            )
            # Agregar dependencia explícita
            fallback_query.add_dependency(self.athena_workgroup)
            self.named_queries["fallback"] = fallback_query
        
        # Salidas
        CfnOutput(
            self, "AthenaWorkGroupName",
            value=self.athena_workgroup.name,
            description="Workgroup de Athena optimizado para análisis F5"
        )
        
        CfnOutput(
            self, "F5AnalyticsQueriesCount",
            value=str(len(self.named_queries)),
            description="Número de queries F5 cargadas desde assets"
        )
        
        CfnOutput(
            self, "AnalyticsAssetsLocation",
            value="assets/analytics-stack/queries/",
            description="Ubicación de queries F5 en assets"
        )
        
        # Almacenar referencias
        self.workgroup_name = workgroup_name
        self.queries_count = len(self.named_queries)
