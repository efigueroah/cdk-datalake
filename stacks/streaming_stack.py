from aws_cdk import (
    Stack,
    aws_kinesis as kinesis,
    aws_kinesisfirehose as firehose,
    aws_iam as iam,
    aws_logs as logs,
    aws_s3 as s3,
    Duration,
    RemovalPolicy,
    CfnOutput
)
from constructs import Construct

class StreamingStack(Stack):
    
    def __init__(self, scope: Construct, construct_id: str, raw_bucket: s3.Bucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Obtener valores de contexto
        project_config = self.node.try_get_context("project")
        kinesis_config = self.node.try_get_context("kinesis")
        
        # Kinesis Data Stream
        self.data_stream = kinesis.Stream(
            self, "DataStream",
            stream_name=f"{project_config['prefix']}-streaming",
            shard_count=kinesis_config.get("shard_count", 1),
            retention_period=Duration.hours(kinesis_config.get("retention_hours", 24))
        )
        
        # Grupo de logs CloudWatch para Firehose
        firehose_log_group = logs.LogGroup(
            self, "FirehoseLogGroup",
            log_group_name=f"/aws/kinesisfirehose/{project_config['prefix']}-delivery",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # Rol IAM para Firehose
        firehose_role = iam.Role(
            self, "FirehoseDeliveryRole",
            assumed_by=iam.ServicePrincipal("firehose.amazonaws.com"),
            inline_policies={
                "FirehoseDeliveryPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:AbortMultipartUpload",
                                "s3:GetBucketLocation", 
                                "s3:GetObject",
                                "s3:ListBucket",
                                "s3:ListBucketMultipartUploads",
                                "s3:PutObject"
                            ],
                            resources=[
                                raw_bucket.bucket_arn,
                                f"{raw_bucket.bucket_arn}/*"
                            ]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "logs:PutLogEvents"
                            ],
                            resources=[
                                firehose_log_group.log_group_arn
                            ]
                        )
                    ]
                )
            }
        )
        
        # Otorgar permisos a Firehose para escribir en S3
        raw_bucket.grant_write(firehose_role)
        
        # Otorgar permisos a Firehose para leer desde Kinesis
        self.data_stream.grant_read(firehose_role)
        
        # Kinesis Data Firehose
        self.delivery_stream = firehose.CfnDeliveryStream(
            self, "DeliveryStream",
            delivery_stream_name=f"{project_config['prefix']}-delivery",
            delivery_stream_type="KinesisStreamAsSource",
            kinesis_stream_source_configuration=firehose.CfnDeliveryStream.KinesisStreamSourceConfigurationProperty(
                kinesis_stream_arn=self.data_stream.stream_arn,
                role_arn=firehose_role.role_arn
            ),
            s3_destination_configuration=firehose.CfnDeliveryStream.S3DestinationConfigurationProperty(
                bucket_arn=raw_bucket.bucket_arn,
                prefix=f"{project_config['solution']}/year=!{{timestamp:yyyy}}/month=!{{timestamp:MM}}/day=!{{timestamp:dd}}/hour=!{{timestamp:HH}}/",
                error_output_prefix="errors/",
                buffering_hints=firehose.CfnDeliveryStream.BufferingHintsProperty(
                    size_in_m_bs=kinesis_config.get("buffer_size_mb", 5),
                    interval_in_seconds=kinesis_config.get("buffer_interval_seconds", 300)
                ),
                compression_format="GZIP",
                role_arn=firehose_role.role_arn,
                cloud_watch_logging_options=firehose.CfnDeliveryStream.CloudWatchLoggingOptionsProperty(
                    enabled=True,
                    log_group_name=firehose_log_group.log_group_name
                )
            )
        )
        
        # Agregar política de eliminación
        self.delivery_stream.apply_removal_policy(RemovalPolicy.DESTROY)
        
        # Agregar dependencia para asegurar que el grupo de logs se cree antes del stream Firehose
        self.delivery_stream.add_dependency(firehose_log_group.node.default_child)
        
        # Salidas
        CfnOutput(
            self, "DataStreamName",
            value=self.data_stream.stream_name,
            description="Nombre del Kinesis Data Stream"
        )
        
        CfnOutput(
            self, "DataStreamArn", 
            value=self.data_stream.stream_arn,
            description="ARN del Kinesis Data Stream"
        )
        
        CfnOutput(
            self, "DeliveryStreamName",
            value=self.delivery_stream.delivery_stream_name,
            description="Nombre del Kinesis Data Firehose"
        )
        
        CfnOutput(
            self, "FirehoseLogGroupName",
            value=firehose_log_group.log_group_name,
            description="Nombre del grupo de logs CloudWatch de Firehose"
        )
        
        CfnOutput(
            self, "FirehoseRoleArn",
            value=firehose_role.role_arn,
            description="ARN del rol IAM de Firehose"
        )
