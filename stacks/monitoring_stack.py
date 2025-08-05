from aws_cdk import (
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_logs as logs,
    aws_kinesis as kinesis,
    aws_kinesisfirehose as firehose,
    aws_lambda as lambda_,
    aws_glue as glue,
    Duration,
    CfnOutput
)
from constructs import Construct

class MonitoringStack(Stack):
    
    def __init__(self, scope: Construct, construct_id: str,
                 kinesis_stream: kinesis.Stream, firehose_stream,
                 lambda_function: lambda_.Function, glue_job, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Get context values
        project_config = self.node.try_get_context("project")
        cloudwatch_config = self.node.try_get_context("cloudwatch")
        notifications_config = self.node.try_get_context("notifications")
        
        # SNS Topic for alerts
        self.alert_topic = sns.Topic(
            self, "AlertTopic",
            topic_name=f"{project_config['prefix']}-alerts",
            display_name="AGESIC Data Lake PoC Alerts"
        )
        
        # Email subscription
        self.alert_topic.add_subscription(
            subscriptions.EmailSubscription(notifications_config["email"])
        )
        
        # CloudWatch Log Groups with retention
        self.error_log_group = logs.LogGroup(
            self, "ErrorLogGroup",
            log_group_name=f"/aws/lambda/{project_config['prefix']}-error-logs",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=self.removal_policy_for_poc()
        )
        
        self.firehose_log_group = logs.LogGroup(
            self, "FirehoseLogGroup",
            log_group_name=f"/aws/kinesisfirehose/{project_config['prefix']}-firehose-stream",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=self.removal_policy_for_poc()
        )
        
        # Kinesis Data Streams Alarms
        self.kinesis_incoming_records_alarm = cloudwatch.Alarm(
            self, "KinesisIncomingRecordsAlarm",
            alarm_name=f"{project_config['prefix']}-kinesis-no-incoming-records",
            alarm_description="No incoming records to Kinesis stream for 10 minutes",
            metric=kinesis_stream.metric_incoming_records(
                statistic="Sum",
                period=Duration.minutes(5)
            ),
            threshold=1,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING
        )
        
        self.kinesis_incoming_records_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self.alert_topic)
        )
        
        # Kinesis iterator age alarm
        self.kinesis_iterator_age_alarm = cloudwatch.Alarm(
            self, "KinesisIteratorAgeAlarm",
            alarm_name=f"{project_config['prefix']}-kinesis-high-iterator-age",
            alarm_description="Kinesis iterator age is too high",
            metric=kinesis_stream.metric_get_records_iterator_age_milliseconds(
                statistic="Maximum",
                period=Duration.minutes(5)
            ),
            threshold=60000,  # 1 minute in milliseconds
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluation_periods=2
        )
        
        self.kinesis_iterator_age_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self.alert_topic)
        )
        
        # Lambda Function Alarms
        self.lambda_error_alarm = cloudwatch.Alarm(
            self, "LambdaErrorAlarm",
            alarm_name=f"{project_config['prefix']}-lambda-errors",
            alarm_description="Lambda function error rate is high",
            metric=lambda_function.metric_errors(
                statistic="Sum",
                period=Duration.minutes(5)
            ),
            threshold=5,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            evaluation_periods=2
        )
        
        self.lambda_error_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self.alert_topic)
        )
        
        self.lambda_duration_alarm = cloudwatch.Alarm(
            self, "LambdaDurationAlarm",
            alarm_name=f"{project_config['prefix']}-lambda-duration",
            alarm_description="Lambda function duration is high",
            metric=lambda_function.metric_duration(
                statistic="Average",
                period=Duration.minutes(5)
            ),
            threshold=240000,  # 4 minutes (80% of 5 minute timeout)
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluation_periods=2
        )
        
        self.lambda_duration_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self.alert_topic)
        )
        
        # Glue Job Alarms
        self.glue_job_failure_alarm = cloudwatch.Alarm(
            self, "GlueJobFailureAlarm",
            alarm_name=f"{project_config['prefix']}-glue-job-failures",
            alarm_description="Glue ETL job failures",
            metric=cloudwatch.Metric(
                namespace="AWS/Glue",
                metric_name="glue.driver.aggregate.numFailedTasks",
                dimensions_map={
                    "JobName": glue_job.name,
                    "JobRunId": "ALL"
                },
                statistic="Sum",
                period=Duration.minutes(5)
            ),
            threshold=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            evaluation_periods=1
        )
        
        self.glue_job_failure_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self.alert_topic)
        )
        
        # Custom Metrics for Data Quality
        self.data_quality_metric = cloudwatch.Metric(
            namespace=f"{project_config['prefix']}/DataQuality",
            metric_name="ProcessedRecords",
            statistic="Sum",
            period=Duration.hours(1)
        )
        
        # Data processing alarm
        self.data_processing_alarm = cloudwatch.Alarm(
            self, "DataProcessingAlarm",
            alarm_name=f"{project_config['prefix']}-no-data-processed",
            alarm_description="No data processed in the last 2 hours",
            metric=self.data_quality_metric,
            threshold=1,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING
        )
        
        self.data_processing_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self.alert_topic)
        )
        
        # CloudWatch Insights Queries
        self.create_insights_queries()
        
        # Outputs
        CfnOutput(
            self, "SNSTopicArn",
            value=self.alert_topic.topic_arn,
            description="SNS topic ARN for alerts"
        )
        
        CfnOutput(
            self, "ErrorLogGroupName",
            value=self.error_log_group.log_group_name,
            description="CloudWatch log group for error logs"
        )
    
    def removal_policy_for_poc(self):
        """Return appropriate removal policy for PoC resources"""
        from aws_cdk import RemovalPolicy
        return RemovalPolicy.DESTROY
    
    def create_insights_queries(self):
        """Create CloudWatch Insights saved queries"""
        project_config = self.node.try_get_context("project")
        
        # Import queries from assets
        import os
        assets_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'configurations')
        queries_module_path = os.path.join(assets_path, 'cloudwatch_insights_queries.py')
        
        # Read queries from file
        queries = {}
        with open(queries_module_path, 'r') as f:
            exec(f.read(), queries)
        
        # Query 1: Error Analysis
        logs.CfnQueryDefinition(
            self, "ErrorAnalysisQuery",
            name=f"{project_config['prefix']}-error-analysis",
            log_group_names=[self.error_log_group.log_group_name],
            query_string=queries['ERROR_ANALYSIS_INSIGHTS_QUERY']
        )
        
        # Query 2: Top Error IPs
        logs.CfnQueryDefinition(
            self, "TopErrorIPsQuery",
            name=f"{project_config['prefix']}-top-error-ips",
            log_group_names=[self.error_log_group.log_group_name],
            query_string=queries['TOP_ERROR_IPS_INSIGHTS_QUERY']
        )
        
        # Query 3: Error Timeline
        logs.CfnQueryDefinition(
            self, "ErrorTimelineQuery",
            name=f"{project_config['prefix']}-error-timeline",
            log_group_names=[self.error_log_group.log_group_name],
            query_string=queries['ERROR_TIMELINE_INSIGHTS_QUERY']
        )
