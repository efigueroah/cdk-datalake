from aws_cdk import (
    Stack,
    aws_kinesis as kinesis,
    aws_kinesisfirehose as firehose,
    aws_iam as iam,
    aws_s3 as s3,
    aws_ec2 as ec2,
    aws_logs as logs,
    Duration,
    CfnOutput,
    RemovalPolicy
)
from constructs import Construct

class StreamingStack(Stack):
    
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc, raw_bucket: s3.Bucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Get context values
        project_config = self.node.try_get_context("project")
        kinesis_config = self.node.try_get_context("kinesis")
        
        # Kinesis Data Stream - let CDK generate unique name
        self.kinesis_stream = kinesis.Stream(
            self, "DataStream",
            shard_count=kinesis_config["shard_count"],
            retention_period=Duration.hours(kinesis_config["retention_hours"]),
            stream_mode=kinesis.StreamMode.PROVISIONED
        )
        
        # CloudWatch Log Group for Firehose - let CDK generate unique name
        firehose_log_group = logs.LogGroup(
            self, "FirehoseLogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # IAM Role for Firehose - let CDK generate unique name
        firehose_role = iam.Role(
            self, "FirehoseDeliveryRole",
            assumed_by=iam.ServicePrincipal("firehose.amazonaws.com"),
            inline_policies={
                "FirehoseDeliveryPolicy": iam.PolicyDocument(
                    statements=[
                        # CloudWatch Logs permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "logs:PutLogEvents",
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream"
                            ],
                            resources=[
                                firehose_log_group.log_group_arn,
                                f"{firehose_log_group.log_group_arn}:*"
                            ]
                        ),
                        # Kinesis permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "kinesis:DescribeStream",
                                "kinesis:GetShardIterator",
                                "kinesis:GetRecords",
                                "kinesis:ListShards"
                            ],
                            resources=[self.kinesis_stream.stream_arn]
                        )
                    ]
                )
            }
        )
        
        # Grant Firehose permissions to write to S3
        raw_bucket.grant_write(firehose_role)
        
        # Grant Firehose permissions to read from Kinesis
        self.kinesis_stream.grant_read(firehose_role)
        
        # Kinesis Data Firehose - let CDK generate unique name
        self.firehose_stream = firehose.CfnDeliveryStream(
            self, "FirehoseDeliveryStream",
            delivery_stream_type="KinesisStreamAsSource",
            kinesis_stream_source_configuration=firehose.CfnDeliveryStream.KinesisStreamSourceConfigurationProperty(
                kinesis_stream_arn=self.kinesis_stream.stream_arn,
                role_arn=firehose_role.role_arn
            ),
            extended_s3_destination_configuration=firehose.CfnDeliveryStream.ExtendedS3DestinationConfigurationProperty(
                bucket_arn=raw_bucket.bucket_arn,
                role_arn=firehose_role.role_arn,
                prefix=f"{project_config['solution']}/year=!{{timestamp:yyyy}}/month=!{{timestamp:MM}}/day=!{{timestamp:dd}}/hour=!{{timestamp:HH}}/",
                error_output_prefix="errors/",
                buffering_hints=firehose.CfnDeliveryStream.BufferingHintsProperty(
                    size_in_m_bs=kinesis_config["firehose_buffer_size"],
                    interval_in_seconds=kinesis_config["firehose_buffer_interval"]
                ),
                compression_format=kinesis_config["compression"],
                data_format_conversion_configuration=firehose.CfnDeliveryStream.DataFormatConversionConfigurationProperty(
                    enabled=False
                ),
                cloud_watch_logging_options=firehose.CfnDeliveryStream.CloudWatchLoggingOptionsProperty(
                    enabled=True,
                    log_group_name=firehose_log_group.log_group_name,
                    log_stream_name="S3Delivery"
                ),
                processing_configuration=firehose.CfnDeliveryStream.ProcessingConfigurationProperty(
                    enabled=False
                )
            )
        )
        
        # Add removal policy
        self.firehose_stream.apply_removal_policy(RemovalPolicy.DESTROY)
        
        # Add dependency to ensure log group is created before Firehose stream
        self.firehose_stream.add_dependency(firehose_log_group.node.default_child)
        
        # Outputs with actual resource names (not hardcoded)
        CfnOutput(
            self, "KinesisStreamName",
            value=self.kinesis_stream.stream_name,
            description="Kinesis Data Stream name"
        )
        
        CfnOutput(
            self, "KinesisStreamArn",
            value=self.kinesis_stream.stream_arn,
            description="Kinesis Data Stream ARN"
        )
        
        CfnOutput(
            self, "FirehoseStreamName",
            value=self.firehose_stream.ref,
            description="Kinesis Firehose delivery stream name"
        )
        
        CfnOutput(
            self, "FirehoseLogGroupName",
            value=firehose_log_group.log_group_name,
            description="Firehose CloudWatch Log Group name"
        )
        
        CfnOutput(
            self, "FirehoseRoleArn",
            value=firehose_role.role_arn,
            description="Firehose IAM Role ARN"
        )
