from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_events,
    aws_iam as iam,
    aws_glue as glue,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_kinesis as kinesis,
    aws_ec2 as ec2,
    aws_logs as logs,
    Duration,
    RemovalPolicy,
    CfnOutput
)
from constructs import Construct
import yaml
import os

class ComputeStack(Stack):
    
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc, 
                 lambda_sg: ec2.SecurityGroup, glue_sg: ec2.SecurityGroup,
                 kinesis_stream: kinesis.Stream, raw_bucket: s3.Bucket, 
                 processed_bucket: s3.Bucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Obtener valores de contexto
        project_config = self.node.try_get_context("project")
        
        # Cargar configuración de Glue desde assets
        config_path = os.path.join(
            os.path.dirname(__file__), 
            "..", 
            "assets", 
            "compute-stack", 
            "configurations", 
            "glue-jobs-config.yaml"
        )
        
        try:
            with open(config_path, 'r') as f:
                glue_config = yaml.safe_load(f)
        except FileNotFoundError:
            # Configuración de respaldo
            glue_config = {
                "glue_jobs": {
                    "f5_etl_multiformat": {
                        "glue_version": "5.0",
                        "worker_type": "G.1X",
                        "number_of_workers": 2
                    }
                }
            }
        
        # Rol de ejecución de Lambda
        lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaKinesisExecutionRole")
            ]
        )
        
        # Otorgar permisos a Lambda
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "cloudwatch:PutMetricData"
                ],
                resources=["*"]
            )
        )
        
        # Función Lambda para filtrado de logs F5
        self.log_filter_lambda = lambda_.Function(
            self, "F5LogFilterFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset("code/lambda/log_filter"),
            role=lambda_role,
            vpc=vpc,
            security_groups=[lambda_sg],
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                "LOG_LEVEL": "INFO",
                "ENABLE_F5_METRICS": "true",
                "CUSTOM_NAMESPACE": f"{project_config['prefix']}/F5Analytics"
            },
            description="Filtrado mejorado de logs F5 con métricas personalizadas de CloudWatch"
        )
        
        # Agregar fuente de eventos Kinesis
        self.log_filter_lambda.add_event_source(
            lambda_events.KinesisEventSource(
                stream=kinesis_stream,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=100,
                max_batching_window=Duration.seconds(5),
                retry_attempts=3
            )
        )
        
        # Rol de servicio de Glue
        glue_role = iam.Role(
            self, "GlueServiceRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSGlueServiceRole")
            ]
        )
        
        # Otorgar permisos a Glue
        raw_bucket.grant_read(glue_role)
        processed_bucket.grant_read_write(glue_role)
        
        glue_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream", 
                    "logs:PutLogEvents",
                    "cloudwatch:PutMetricData"
                ],
                resources=["*"]
            )
        )
        
        # Crear base de datos de Glue
        self.glue_database = glue.CfnDatabase(
            self, "GlueDatabase",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=f"{project_config['prefix'].replace('-', '_')}_database",
                description="Base de datos para AGESIC Data Lake PoC con análisis F5"
            )
        )
        
        # Desplegar scripts de Glue desde assets organizados
        glue_scripts_deployment = s3deploy.BucketDeployment(
            self, "GlueScriptsDeployment",
            sources=[s3deploy.Source.asset("assets/compute-stack/glue-scripts")],
            destination_bucket=raw_bucket,
            destination_key_prefix="scripts/",
            retain_on_delete=False
        )
        
        # Desplegar configuraciones de Kinesis Agent
        kinesis_configs_deployment = s3deploy.BucketDeployment(
            self, "KinesisConfigsDeployment",
            sources=[s3deploy.Source.asset("assets/compute-stack/kinesis-agent")],
            destination_bucket=raw_bucket,
            destination_key_prefix="kinesis-configs/",
            retain_on_delete=False
        )
        
        # Job ETL F5 - MULTIFORMATO (Principal)
        multiformat_config = glue_config.get("glue_jobs", {}).get("f5_etl_multiformat", {})
        self.f5_etl_job_multiformat = glue.CfnJob(
            self, "F5ETLJobMultiformat",
            name=f"{project_config['prefix']}-f5-etl-multiformat",
            role=glue_role.role_arn,
            command=glue.CfnJob.JobCommandProperty(
                name="glueetl",
                script_location=f"s3://{raw_bucket.bucket_name}/scripts/etl_f5_multiformat.py",
                python_version="3"
            ),
            default_arguments={
                "--solution_name": project_config['solution'],
                "--enable-metrics": "true",
                "--custom-logStream-prefix": "f5-multiformat-processing",
                "--custom-logGroup-prefix": f"{project_config['prefix']}-etl-multiformat",
                "--conf": f"spark.hadoop.fs.s3a.endpoint.region={self.region}",
                "--processed_bucket": processed_bucket.bucket_name,
                "--raw_bucket": raw_bucket.bucket_name,
                "--job-bookmark-option": "job-bookmark-disable",
                "--enable-spark-ui": "true",
                "--spark-event-logs-path": f"s3://{processed_bucket.bucket_name}/spark-logs/",
                "--enable-continuous-cloudwatch-log": "true"
            },
            description="ETL multiformato robusto para logs F5 - Soporta JSON y texto plano",
            glue_version=multiformat_config.get("glue_version", "5.0"),
            worker_type=multiformat_config.get("worker_type", "G.1X"),
            number_of_workers=multiformat_config.get("number_of_workers", 2),
            timeout=multiformat_config.get("timeout", 60),
            max_retries=multiformat_config.get("max_retries", 1),
            execution_property=glue.CfnJob.ExecutionPropertyProperty(
                max_concurrent_runs=multiformat_config.get("max_concurrent_runs", 1)
            )
        )
        
        # Job ETL F5 - Legacy (Respaldo)
        legacy_config = glue_config.get("glue_jobs", {}).get("f5_etl_legacy", {})
        self.f5_etl_job_legacy = glue.CfnJob(
            self, "F5ETLJobLegacy", 
            name=f"{project_config['prefix']}-f5-etl-legacy",
            role=glue_role.role_arn,
            command=glue.CfnJob.JobCommandProperty(
                name="glueetl",
                script_location=f"s3://{raw_bucket.bucket_name}/scripts/etl_f5_to_parquet.py",
                python_version="3"
            ),
            default_arguments={
                "--solution_name": project_config['solution'],
                "--enable-metrics": "true",
                "--custom-logStream-prefix": "f5-legacy-processing",
                "--custom-logGroup-prefix": f"{project_config['prefix']}-etl-legacy",
                "--conf": f"spark.hadoop.fs.s3a.endpoint.region={self.region}",
                "--processed_bucket": processed_bucket.bucket_name,
                "--raw_bucket": raw_bucket.bucket_name,
                "--job-bookmark-option": "job-bookmark-enable"
            },
            description="ETL legacy para logs F5 - Respaldo del job multiformato",
            glue_version=legacy_config.get("glue_version", "5.0"),
            worker_type=legacy_config.get("worker_type", "G.1X"), 
            number_of_workers=legacy_config.get("number_of_workers", 2),
            timeout=legacy_config.get("timeout", 60),
            max_retries=legacy_config.get("max_retries", 1),
            execution_property=glue.CfnJob.ExecutionPropertyProperty(
                max_concurrent_runs=legacy_config.get("max_concurrent_runs", 1)
            )
        )
        
        # Configuración de crawlers desde assets
        crawlers_config = glue_config.get("crawlers", {})
        
        # Crawler para datos raw
        raw_crawler_config = crawlers_config.get("raw_data", {})
        self.raw_crawler = glue.CfnCrawler(
            self, "RawDataCrawler",
            name=f"{project_config['prefix']}-raw-crawler",
            role=glue_role.role_arn,
            database_name=self.glue_database.ref,
            targets=glue.CfnCrawler.TargetsProperty(
                s3_targets=[
                    glue.CfnCrawler.S3TargetProperty(
                        path=f"s3://{raw_bucket.bucket_name}/{project_config['solution']}/"
                    )
                ]
            ),
            recrawl_policy=glue.CfnCrawler.RecrawlPolicyProperty(
                recrawl_behavior=raw_crawler_config.get("recrawl_behavior", "CRAWL_EVERYTHING")
            ),
            schema_change_policy=glue.CfnCrawler.SchemaChangePolicyProperty(
                update_behavior=raw_crawler_config.get("update_behavior", "UPDATE_IN_DATABASE"),
                delete_behavior=raw_crawler_config.get("delete_behavior", "LOG")
            ),
            schedule=glue.CfnCrawler.ScheduleProperty(
                schedule_expression=raw_crawler_config.get("schedule", "cron(0 2 * * ? *)")
            ),
            description=raw_crawler_config.get("description", "Crawler para datos raw con soporte F5")
        )
        
        # Crawler para datos procesados
        processed_crawler_config = crawlers_config.get("processed_data", {})
        self.processed_crawler = glue.CfnCrawler(
            self, "ProcessedDataCrawler",
            name=f"{project_config['prefix']}-processed-crawler",
            role=glue_role.role_arn,
            database_name=self.glue_database.ref,
            targets=glue.CfnCrawler.TargetsProperty(
                s3_targets=[
                    glue.CfnCrawler.S3TargetProperty(
                        path=f"s3://{processed_bucket.bucket_name}/f5-logs/"
                    )
                ]
            ),
            recrawl_policy=glue.CfnCrawler.RecrawlPolicyProperty(
                recrawl_behavior=processed_crawler_config.get("recrawl_behavior", "CRAWL_NEW_FOLDERS_ONLY")
            ),
            schema_change_policy=glue.CfnCrawler.SchemaChangePolicyProperty(
                update_behavior="LOG",  # Requerido para CRAWL_NEW_FOLDERS_ONLY
                delete_behavior="LOG"   # Requerido para CRAWL_NEW_FOLDERS_ONLY
            ),
            schedule=glue.CfnCrawler.ScheduleProperty(
                schedule_expression=processed_crawler_config.get("schedule", "cron(0 3 * * ? *)")
            ),
            description=processed_crawler_config.get("description", "Crawler para datos procesados F5 en formato Parquet")
        )
        
        # Salidas
        CfnOutput(
            self, "GlueDatabaseName",
            value=self.glue_database.ref,
            description="Nombre de base de datos Glue para análisis F5"
        )
        
        CfnOutput(
            self, "F5ETLJobMultiformatName",
            value=self.f5_etl_job_multiformat.name,
            description="Nombre del job ETL Multiformato F5 (Principal)"
        )
        
        CfnOutput(
            self, "F5ETLJobLegacyName", 
            value=self.f5_etl_job_legacy.name,
            description="Nombre del job ETL Legacy F5 (Respaldo)"
        )
        
        CfnOutput(
            self, "ComputeAssetsLocation",
            value=f"s3://{raw_bucket.bucket_name}/scripts/",
            description="Ubicación de assets compute en S3"
        )
        
        # Almacenar referencias para otros stacks
        self.glue_role = glue_role
        self.lambda_role = lambda_role
