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

class AnalyticsStack(Stack):
    
    def __init__(self, scope: Construct, construct_id: str, 
                 processed_bucket: s3.Bucket, athena_results_bucket: s3.Bucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Get context values
        project_config = self.node.try_get_context("project")
        
        # Generate unique suffix to avoid conflicts
        timestamp = str(int(time.time()))
        unique_suffix = hashlib.md5(f"{construct_id}-{timestamp}".encode()).hexdigest()[:8]
        
        # Import queries from assets
        assets_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'configurations')
        queries_module_path = os.path.join(assets_path, 'athena_queries.py')
        
        # Read queries from file
        queries = {}
        with open(queries_module_path, 'r') as f:
            exec(f.read(), queries)
        
        # Athena Workgroup with unique name
        workgroup_name = f"{project_config['prefix']}-wg-{unique_suffix}"
        self.athena_workgroup = athena.CfnWorkGroup(
            self, "AthenaWorkGroup",
            name=workgroup_name,
            description="Workgroup for AGESIC Data Lake PoC queries",
            state="ENABLED",
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{athena_results_bucket.bucket_name}/query-results/",
                    encryption_configuration=athena.CfnWorkGroup.EncryptionConfigurationProperty(
                        encryption_option="SSE_S3"
                    )
                ),
                enforce_work_group_configuration=True,
                bytes_scanned_cutoff_per_query=1000000000,  # 1GB limit per query
                requester_pays_enabled=False
            )
        )
        
        # Add removal policy to ensure clean deletion
        self.athena_workgroup.apply_removal_policy(RemovalPolicy.DESTROY)
        
        # Named Queries for common analytics with unique names
        
        # Query 1: Error Analysis
        self.error_analysis_query = athena.CfnNamedQuery(
            self, "ErrorAnalysisQuery",
            name=f"{project_config['prefix']}-error-analysis-{unique_suffix}",
            description="Analyze error patterns in HTTP logs",
            database=f"{project_config['prefix'].replace('-', '_')}_database",
            query_string=queries['ERROR_ANALYSIS_QUERY'],
            work_group=workgroup_name
        )
        self.error_analysis_query.apply_removal_policy(RemovalPolicy.DESTROY)
        self.error_analysis_query.add_dependency(self.athena_workgroup)
        
        # Query 2: Traffic Analysis
        self.traffic_analysis_query = athena.CfnNamedQuery(
            self, "TrafficAnalysisQuery",
            name=f"{project_config['prefix']}-traffic-analysis-{unique_suffix}",
            description="Analyze traffic patterns by hour and path",
            database=f"{project_config['prefix'].replace('-', '_')}_database",
            query_string=queries['TRAFFIC_ANALYSIS_QUERY'],
            work_group=workgroup_name
        )
        self.traffic_analysis_query.apply_removal_policy(RemovalPolicy.DESTROY)
        self.traffic_analysis_query.add_dependency(self.athena_workgroup)
        
        # Query 3: Top IPs Analysis
        self.top_ips_query = athena.CfnNamedQuery(
            self, "TopIPsQuery",
            name=f"{project_config['prefix']}-top-ips-{unique_suffix}",
            description="Analyze top client IPs and their behavior",
            database=f"{project_config['prefix'].replace('-', '_')}_database",
            query_string=queries['TOP_IPS_QUERY'],
            work_group=workgroup_name
        )
        self.top_ips_query.apply_removal_policy(RemovalPolicy.DESTROY)
        self.top_ips_query.add_dependency(self.athena_workgroup)
        
        # Query 4: Performance Analysis
        self.performance_query = athena.CfnNamedQuery(
            self, "PerformanceQuery",
            name=f"{project_config['prefix']}-performance-{unique_suffix}",
            description="Analyze response sizes and performance patterns",
            database=f"{project_config['prefix'].replace('-', '_')}_database",
            query_string=queries['PERFORMANCE_QUERY'],
            work_group=workgroup_name
        )
        self.performance_query.apply_removal_policy(RemovalPolicy.DESTROY)
        self.performance_query.add_dependency(self.athena_workgroup)
        
        # Query 5: Hourly Summary
        self.hourly_summary_query = athena.CfnNamedQuery(
            self, "HourlySummaryQuery",
            name=f"{project_config['prefix']}-hourly-summary-{unique_suffix}",
            description="Hourly summary of traffic and errors",
            database=f"{project_config['prefix'].replace('-', '_')}_database",
            query_string=queries['HOURLY_SUMMARY_QUERY'],
            work_group=workgroup_name
        )
        self.hourly_summary_query.apply_removal_policy(RemovalPolicy.DESTROY)
        self.hourly_summary_query.add_dependency(self.athena_workgroup)
        
        # Outputs with actual resource references
        CfnOutput(
            self, "AthenaWorkGroupName",
            value=workgroup_name,
            description="Athena workgroup name for queries"
        )
        
        CfnOutput(
            self, "AthenaResultsLocation",
            value=f"s3://{athena_results_bucket.bucket_name}/query-results/",
            description="Athena query results location"
        )
        
        CfnOutput(
            self, "ErrorAnalysisQueryId",
            value=self.error_analysis_query.ref,
            description="Error Analysis Named Query ID"
        )
        
        CfnOutput(
            self, "TrafficAnalysisQueryId",
            value=self.traffic_analysis_query.ref,
            description="Traffic Analysis Named Query ID"
        )
