from aws_cdk import (
    Stack,
    aws_s3 as s3,
    Duration,
    RemovalPolicy,
    CfnOutput
)
from constructs import Construct

class StorageStack(Stack):
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Obtener valores de contexto
        project_config = self.node.try_get_context("project")
        s3_config = self.node.try_get_context("s3")
        
        # Common bucket properties
        common_bucket_props = {
            "versioned": True,
            "encryption": s3.BucketEncryption.S3_MANAGED,
            "enforce_ssl": True,
            "public_read_access": False,
            "block_public_access": s3.BlockPublicAccess.BLOCK_ALL,
            "removal_policy": RemovalPolicy.DESTROY,  # For PoC only
            "auto_delete_objects": True  # For PoC only
        }
        
        # Lifecycle rule for data buckets
        data_lifecycle_rule = s3.LifecycleRule(
            id="DataLifecycleRule",
            enabled=True,
            transitions=[
                s3.Transition(
                    storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                    transition_after=Duration.days(s3_config["lifecycle"]["transition_to_ia_days"])
                ),
                s3.Transition(
                    storage_class=s3.StorageClass.GLACIER,
                    transition_after=Duration.days(s3_config["lifecycle"]["transition_to_glacier_days"])
                )
            ],
            expiration=Duration.days(s3_config["lifecycle"]["expiration_days"])
        )
        
        # Raw Zone Bucket (Bronze Layer)
        self.raw_bucket = s3.Bucket(
            self, "RawZoneBucket",
            bucket_name=f"{project_config['prefix']}-raw-zone",
            lifecycle_rules=[data_lifecycle_rule],
            **common_bucket_props
        )
        
        # Processed Zone Bucket (Silver Layer)
        self.processed_bucket = s3.Bucket(
            self, "ProcessedZoneBucket",
            bucket_name=f"{project_config['prefix']}-processed-zone",
            lifecycle_rules=[data_lifecycle_rule],
            **common_bucket_props
        )
        
        # Athena Results Bucket
        self.athena_results_bucket = s3.Bucket(
            self, "AthenaResultsBucket",
            bucket_name=f"{project_config['prefix']}-athena-results",
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="AthenaResultsLifecycle",
                    enabled=True,
                    expiration=Duration.days(30)  # Shorter retention for query results
                )
            ],
            **common_bucket_props
        )
        
        # Glue Scripts Bucket
        self.glue_scripts_bucket = s3.Bucket(
            self, "GlueScriptsBucket",
            bucket_name=f"{project_config['prefix']}-glue-scripts",
            **common_bucket_props
        )
        
        # Outputs
        CfnOutput(
            self, "RawBucketName",
            value=self.raw_bucket.bucket_name,
            description="Raw zone S3 bucket name"
        )
        
        CfnOutput(
            self, "ProcessedBucketName",
            value=self.processed_bucket.bucket_name,
            description="Processed zone S3 bucket name"
        )
        
        CfnOutput(
            self, "AthenaResultsBucketName",
            value=self.athena_results_bucket.bucket_name,
            description="Athena results S3 bucket name"
        )
        
        CfnOutput(
            self, "GlueScriptsBucketName",
            value=self.glue_scripts_bucket.bucket_name,
            description="Glue scripts S3 bucket name"
        )
