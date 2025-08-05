#!/usr/bin/env python3
import os
import aws_cdk as cdk
from cdk_nag import AwsSolutionsChecks

from stacks.network_stack import NetworkStack
from stacks.storage_stack import StorageStack
from stacks.streaming_stack import StreamingStack
from stacks.compute_stack import ComputeStack
from stacks.analytics_stack import AnalyticsStack
from stacks.monitoring_stack import MonitoringStack
from stacks.visualization_stack import VisualizationStack
from stacks.ec2_stack import EC2Stack

app = cdk.App()

# Get context values
project_config = app.node.try_get_context("project")
tags_config = app.node.try_get_context("tags")

# Environment configuration
env = cdk.Environment(
    account=os.getenv('CDK_DEFAULT_ACCOUNT'),
    region=os.getenv('CDK_DEFAULT_REGION', 'us-east-2')
)

# Apply global tags
for key, value in tags_config.items():
    cdk.Tags.of(app).add(key, value)

# Create stacks with dependencies
network_stack = NetworkStack(
    app, 
    f"{project_config['prefix']}-network",
    env=env,
    description="Network infrastructure for AGESIC Data Lake PoC"
)

storage_stack = StorageStack(
    app, 
    f"{project_config['prefix']}-storage",
    env=env,
    description="S3 storage infrastructure for AGESIC Data Lake PoC"
)

streaming_stack = StreamingStack(
    app, 
    f"{project_config['prefix']}-streaming",
    vpc=network_stack.vpc,
    raw_bucket=storage_stack.raw_bucket,
    env=env,
    description="Kinesis streaming infrastructure for AGESIC Data Lake PoC"
)

compute_stack = ComputeStack(
    app, 
    f"{project_config['prefix']}-compute",
    vpc=network_stack.vpc,
    lambda_sg=network_stack.lambda_security_group,
    glue_sg=network_stack.glue_security_group,
    kinesis_stream=streaming_stack.kinesis_stream,
    raw_bucket=storage_stack.raw_bucket,
    processed_bucket=storage_stack.processed_bucket,
    env=env,
    description="Compute infrastructure for AGESIC Data Lake PoC"
)

analytics_stack = AnalyticsStack(
    app, 
    f"{project_config['prefix']}-analytics",
    processed_bucket=storage_stack.processed_bucket,
    athena_results_bucket=storage_stack.athena_results_bucket,
    env=env,
    description="Analytics infrastructure for AGESIC Data Lake PoC"
)

monitoring_stack = MonitoringStack(
    app, 
    f"{project_config['prefix']}-monitoring",
    kinesis_stream=streaming_stack.kinesis_stream,
    firehose_stream=streaming_stack.firehose_stream,
    lambda_function=compute_stack.log_filter_lambda,
    glue_job=compute_stack.glue_etl_job,
    env=env,
    description="Monitoring infrastructure for AGESIC Data Lake PoC"
)

ec2_stack = EC2Stack(
    app,
    f"{project_config['prefix']}-ec2",
    vpc=network_stack.vpc,
    kinesis_stream=streaming_stack.kinesis_stream,
    env=env,
    description="EC2 log generator for AGESIC Data Lake PoC"
)

# Visualization Stack (8th stack - last one)
visualization_stack = VisualizationStack(
    app, 
    f"{project_config['prefix']}-visualization",
    vpc=network_stack.vpc,
    env=env,
    description="Visualization infrastructure for AGESIC Data Lake PoC"
)

# Apply CDK Nag checks
## cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

app.synth()
