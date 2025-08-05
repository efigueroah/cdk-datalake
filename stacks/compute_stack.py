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
    aws_events as events,
    aws_events_targets as targets,
    Duration,
    CfnOutput
)
from constructs import Construct

class ComputeStack(Stack):
    
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc, 
                 lambda_sg: ec2.SecurityGroup, glue_sg: ec2.SecurityGroup,
                 kinesis_stream: kinesis.Stream, raw_bucket: s3.Bucket, 
                 processed_bucket: s3.Bucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Get context values
        project_config = self.node.try_get_context("project")
        glue_config = self.node.try_get_context("glue")
        cloudwatch_config = self.node.try_get_context("cloudwatch")
        
        # Lambda execution role
        lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaKinesisExecutionRole")
            ]
        )
        
        # Grant Lambda permissions to write to CloudWatch Logs
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams"
                ],
                resources=["*"]
            )
        )
        
        # Lambda function for log filtering
        self.log_filter_lambda = lambda_.Function(
            self, "LogFilterFunction",
            function_name=f"{project_config['prefix']}-log-filter",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset("code/lambda/log_filter"),
            role=lambda_role,
            timeout=Duration.minutes(5),
            memory_size=512,
            reserved_concurrent_executions=10,
            environment={
                "LOG_LEVEL": "INFO",
                "PROJECT_PREFIX": project_config['prefix']
            },
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[lambda_sg]
        )
        
        # Add Kinesis as event source for Lambda
        self.log_filter_lambda.add_event_source(
            lambda_events.KinesisEventSource(
                stream=kinesis_stream,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=100,
                max_batching_window=Duration.seconds(5),
                retry_attempts=3
            )
        )
        
        # Glue service role
        glue_role = iam.Role(
            self, "GlueServiceRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSGlueServiceRole")
            ]
        )
        
        # Grant Glue permissions to access S3 buckets
        raw_bucket.grant_read(glue_role)
        processed_bucket.grant_read_write(glue_role)
        
        # Create Glue database
        self.glue_database = glue.CfnDatabase(
            self, "GlueDatabase",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=f"{project_config['prefix'].replace('-', '_')}_database",
                description="Database for AGESIC Data Lake PoC"
            )
        )
        
        # Deploy Glue script to S3 (using raw bucket for simplicity in PoC)
        script_deployment = s3deploy.BucketDeployment(
            self, "GlueScriptDeployment",
            sources=[s3deploy.Source.asset("assets/glue_scripts")],
            destination_bucket=raw_bucket,
            destination_key_prefix="scripts/"
        )
        
        # Glue ETL Job
        self.glue_etl_job = glue.CfnJob(
            self, "GlueETLJob",
            name=f"{project_config['prefix']}-etl-job",
            role=glue_role.role_arn,
            command=glue.CfnJob.JobCommandProperty(
                name="glueetl",
                python_version="3",
                script_location=f"s3://{raw_bucket.bucket_name}/scripts/etl_json_to_parquet.py"
            ),
            default_arguments={
                "--job-bookmark-option": "job-bookmark-enable",
                "--enable-metrics": "true",
                "--enable-continuous-cloudwatch-log": "true",
                "--raw_bucket": raw_bucket.bucket_name,
                "--processed_bucket": processed_bucket.bucket_name,
                "--solution_name": project_config['solution']
            },
            glue_version="4.0",
            worker_type=glue_config["etl_worker_type"],
            number_of_workers=glue_config["etl_number_of_workers"],
            timeout=60,  # 60 minutes timeout
            max_retries=1
        )
        
        # Glue Crawler for Raw Zone
        self.raw_crawler = glue.CfnCrawler(
            self, "RawZoneCrawler",
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
            schedule=glue.CfnCrawler.ScheduleProperty(
                schedule_expression=glue_config["crawler_schedule"]
            ),
            schema_change_policy=glue.CfnCrawler.SchemaChangePolicyProperty(
                update_behavior="UPDATE_IN_DATABASE",
                delete_behavior="LOG"
            )
        )
        
        # Glue Crawler for Processed Zone
        self.processed_crawler = glue.CfnCrawler(
            self, "ProcessedZoneCrawler",
            name=f"{project_config['prefix']}-processed-crawler",
            role=glue_role.role_arn,
            database_name=self.glue_database.ref,
            targets=glue.CfnCrawler.TargetsProperty(
                s3_targets=[
                    glue.CfnCrawler.S3TargetProperty(
                        path=f"s3://{processed_bucket.bucket_name}/{project_config['solution']}/"
                    )
                ]
            ),
            schedule=glue.CfnCrawler.ScheduleProperty(
                schedule_expression=glue_config["crawler_schedule"]
            ),
            schema_change_policy=glue.CfnCrawler.SchemaChangePolicyProperty(
                update_behavior="UPDATE_IN_DATABASE",
                delete_behavior="LOG"
            )
        )
        
        # EventBridge rule to trigger ETL job daily
        etl_schedule_rule = events.Rule(
            self, "ETLScheduleRule",
            rule_name=f"{project_config['prefix']}-etl-schedule",
            schedule=events.Schedule.cron(
                minute="30",
                hour="2",  # Run at 2:30 AM (after crawlers)
                day="*",
                month="*",
                year="*"
            )
        )
        
        # Add Glue job as target using AwsApi
        etl_schedule_rule.add_target(
            targets.AwsApi(
                service="glue",
                action="startJobRun",
                parameters={
                    "JobName": self.glue_etl_job.name
                }
            )
        )
        
        # Outputs
        CfnOutput(
            self, "LambdaFunctionName",
            value=self.log_filter_lambda.function_name,
            description="Log filter Lambda function name"
        )
        
        CfnOutput(
            self, "GlueDatabaseName",
            value=self.glue_database.ref,
            description="Glue database name"
        )
        
        CfnOutput(
            self, "GlueETLJobName",
            value=self.glue_etl_job.name,
            description="Glue ETL job name"
        )
