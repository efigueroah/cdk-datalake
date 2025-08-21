#!/usr/bin/env python3
import os
import aws_cdk as cdk
from aws_cdk import Environment

# Importar stacks
from stacks.network_stack import NetworkStack
from stacks.storage_stack import StorageStack
from stacks.streaming_stack import StreamingStack
from stacks.compute_stack import ComputeStack
from stacks.analytics_stack import AnalyticsStack
from stacks.monitoring_stack import MonitoringStack
from stacks.ec2_stack_enhanced import EC2StackEnhanced
from stacks.visualization_stack import VisualizationStack

app = cdk.App()

# Obtener configuración del contexto
project_config = app.node.try_get_context("project")

# Configurar entorno
env = Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "us-east-2")
)

print("Creando AGESIC Data Lake PoC con análisis F5...")

# 1. Network Stack
network_stack = NetworkStack(
    app, 
    f"{project_config['prefix']}-network",
    env=env,
    description="Infraestructura de red para AGESIC Data Lake PoC"
)

# 2. Storage Stack
storage_stack = StorageStack(
    app, 
    f"{project_config['prefix']}-storage",
    env=env,
    description="Infraestructura de almacenamiento S3 para AGESIC Data Lake PoC"
)

# 3. Streaming Stack
streaming_stack = StreamingStack(
    app, 
    f"{project_config['prefix']}-streaming",
    raw_bucket=storage_stack.raw_bucket,
    env=env,
    description="Infraestructura de streaming Kinesis para logs F5"
)

# 4. Compute Stack
compute_stack = ComputeStack(
    app, 
    f"{project_config['prefix']}-compute",
    vpc=network_stack.vpc,
    lambda_sg=network_stack.lambda_security_group,
    glue_sg=network_stack.glue_security_group,
    kinesis_stream=streaming_stack.data_stream,
    raw_bucket=storage_stack.raw_bucket,
    processed_bucket=storage_stack.processed_bucket,
    env=env,
    description="Infraestructura de cómputo con ETL Multiformato"
)

# 5. Analytics Stack
analytics_stack = AnalyticsStack(
    app, 
    f"{project_config['prefix']}-analytics",
    processed_bucket=storage_stack.processed_bucket,
    athena_results_bucket=storage_stack.athena_results_bucket,
    env=env,
    description="Infraestructura de análisis con queries F5 predefinidas"
)

# 6. Monitoring Stack
monitoring_stack = MonitoringStack(
    app, 
    f"{project_config['prefix']}-monitoring",
    env=env,
    description="Infraestructura de monitoreo y alertas F5"
)

# 7. EC2 Stack Enhanced
ec2_stack = EC2StackEnhanced(
    app, 
    f"{project_config['prefix']}-ec2",
    vpc=network_stack.vpc,
    kinesis_stream=streaming_stack.data_stream,
    raw_bucket=storage_stack.raw_bucket,
    env=env,
    description="Infraestructura EC2 mejorada para F5 Bridge con assets"
)

# 8. Visualization Stack
visualization_stack = VisualizationStack(
    app, 
    f"{project_config['prefix']}-visualization",
    vpc=network_stack.vpc,
    env=env,
    description="Infraestructura de visualización con Grafana"
)

# Dependencias de stacks
streaming_stack.add_dependency(storage_stack)
compute_stack.add_dependency(network_stack)
compute_stack.add_dependency(storage_stack)
compute_stack.add_dependency(streaming_stack)
analytics_stack.add_dependency(storage_stack)
analytics_stack.add_dependency(compute_stack)
monitoring_stack.add_dependency(compute_stack)
ec2_stack.add_dependency(network_stack)
ec2_stack.add_dependency(streaming_stack)
ec2_stack.add_dependency(storage_stack)
visualization_stack.add_dependency(network_stack)

print("Aplicación CDK de AGESIC Data Lake PoC configurada")

app.synth()
