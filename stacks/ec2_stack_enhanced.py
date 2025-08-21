from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_kinesis as kinesis,
    aws_autoscaling as autoscaling,
    aws_ssm as ssm,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_lambda as lambda_,
    Duration,
    CfnOutput,
    Tags
)
from constructs import Construct
import json
import yaml
import os

class EC2StackEnhanced(Stack):
    """
    Enhanced EC2 Stack with F5 Bridge optimizado para ETL Multiformato
    Usa assets externos para SSM Documents, Lambda y Scripts
    """
    
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc, 
                 kinesis_stream: kinesis.Stream, raw_bucket: s3.Bucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Get context values
        project_config = self.node.try_get_context("project")
        f5_config = self.node.try_get_context("f5_logs") or {}
        
        # Configuration parameters
        source_bucket = f5_config.get("source_bucket", "rawdata-analytics-poc-voh9ai")
        source_file = f5_config.get("source_file", "extracto_logs_acceso_f5_portalgubuy.txt")
        
        # Enhanced IAM Role para EC2 con permisos completos
        self.ec2_role = iam.Role(
            self, "EC2InstanceRole",
            role_name=f"{project_config['prefix']}-ec2-f5-bridge-role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchAgentServerPolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonKinesisFullAccess")
            ]
        )
        
        # Permisos S3 y otros servicios
        self.ec2_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject", 
                    "s3:ListBucket",
                    "kinesis:PutRecord",
                    "kinesis:PutRecords",
                    "kinesis:DescribeStream",
                    "cloudwatch:PutMetricData",
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "ssm:SendCommand",
                    "ssm:GetCommandInvocation"
                ],
                resources=["*"]
            )
        )
        
        # Rol IAM específico para Lambda
        self.lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        # Agregar permisos específicos para Lambda
        self.lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:SendCommand",
                    "ssm:GetCommandInvocation",
                    "ssm:DescribeInstanceInformation",
                    "ec2:DescribeInstances"
                ],
                resources=["*"]
            )
        )
        
        # Security Group
        self.f5_bridge_sg = ec2.SecurityGroup(
            self, "F5BridgeSecurityGroup",
            vpc=vpc,
            description="Security Group para F5 Bridge con Kinesis Agent",
            allow_all_outbound=True
        )
        
        # Deploy EC2 assets to S3 for easy access
        self.ec2_assets_deployment = s3deploy.BucketDeployment(
            self, "EC2AssetsDeployment",
            sources=[s3deploy.Source.asset("assets/ec2-stack")],
            destination_bucket=raw_bucket,
            destination_key_prefix="ec2-assets/",
            retain_on_delete=False
        )
        
        # Load SSM Document from assets
        ssm_document_path = os.path.join(
            os.path.dirname(__file__), 
            "..", 
            "assets", 
            "ec2-stack", 
            "ssm-documents", 
            "complete-setup.yaml"
        )
        
        # Read and parse SSM Document
        try:
            with open(ssm_document_path, 'r') as f:
                ssm_content = yaml.safe_load(f)
            
            # Update parameters with actual values
            ssm_content["parameters"]["kinesisStreamName"]["default"] = kinesis_stream.stream_name
            ssm_content["parameters"]["sourceBucket"]["default"] = source_bucket
            ssm_content["parameters"]["sourceFile"]["default"] = source_file
            
        except FileNotFoundError:
            # Fallback to inline content if file not found
            ssm_content = {
                "schemaVersion": "2.2",
                "description": "AGESIC Data Lake - F5 Bridge Setup (Fallback)",
                "parameters": {
                    "kinesisStreamName": {
                        "type": "String",
                        "default": kinesis_stream.stream_name
                    }
                },
                "mainSteps": [
                    {
                        "action": "aws:runShellScript",
                        "name": "setupF5Bridge",
                        "inputs": {
                            "timeoutSeconds": "300",
                            "runCommand": [
                                "#!/bin/bash",
                                "echo 'F5 Bridge setup - Fallback mode'",
                                "mkdir -p /opt/agesic-datalake",
                                "echo 'Setup completed'"
                            ]
                        }
                    }
                ]
            }
        
        # SSM Document usando assets externos
        self.f5_bridge_setup_document = ssm.CfnDocument(
            self, "F5BridgeSetupDocument",
            document_type="Command",
            document_format="JSON",
            name=f"{project_config['prefix']}-f5-bridge-setup",
            content=ssm_content
        )
        
        # User Data con configuración inicial y referencia a assets
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "#!/bin/bash",
            "yum update -y",
            "yum install -y amazon-ssm-agent java-1.8.0-openjdk awscli",
            "systemctl enable amazon-ssm-agent",
            "systemctl start amazon-ssm-agent",
            "",
            "# Variables de entorno para F5 Bridge",
            f"echo 'KINESIS_STREAM_NAME={kinesis_stream.stream_name}' >> /etc/environment",
            f"echo 'SOURCE_BUCKET={source_bucket}' >> /etc/environment", 
            f"echo 'SOURCE_FILE={source_file}' >> /etc/environment",
            f"echo 'RAW_BUCKET={raw_bucket.bucket_name}' >> /etc/environment",
            "echo 'AWS_DEFAULT_REGION=us-east-2' >> /etc/environment",
            "",
            "# Crear directorio de trabajo",
            "mkdir -p /opt/agesic-datalake",
            "chown ec2-user:ec2-user /opt/agesic-datalake",
            "",
            "# Descargar assets desde S3",
            f"aws s3 sync s3://{raw_bucket.bucket_name}/ec2-assets/scripts/ /opt/agesic-datalake/ --region us-east-2",
            "chmod +x /opt/agesic-datalake/*.sh",
            "chmod +x /opt/agesic-datalake/*.py",
            "chown -R ec2-user:ec2-user /opt/agesic-datalake/",
            "",
            "# Instalar AWS Kinesis Agent",
            "cd /tmp",
            "wget https://s3.amazonaws.com/kinesis-agent-us-east-1/aws-kinesis-agent-latest.amzn2.noarch.rpm",
            "yum localinstall -y aws-kinesis-agent-latest.amzn2.noarch.rpm",
            "",
            "# Configurar Kinesis Agent para ETL Multiformato",
            "mkdir -p /etc/aws-kinesis",
            f"""cat > /etc/aws-kinesis/agent.json << 'EOF'
{{
  "cloudwatch.emitMetrics": true,
  "kinesis.endpoint": "https://kinesis.us-east-2.amazonaws.com",
  "flows": [
    {{
      "filePattern": "/opt/agesic-datalake/f5_logs_current.log",
      "kinesisStream": "{kinesis_stream.stream_name}",
      "partitionKeyOption": "RANDOM",
      "initialPosition": "START_OF_FILE"
    }}
  ]
}}
EOF""",
            "",
            "# Habilitar Kinesis Agent",
            "systemctl enable aws-kinesis-agent",
            "",
            "echo 'F5 Bridge initialized with assets - Ready for ETL Multiformato' > /var/log/f5-bridge-init.log"
        )
        
        # Lambda function para instalación de agentes (usando assets)
        self.install_agents_lambda = lambda_.Function(
            self, "InstallAgentsFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="install_agents.lambda_handler",
            code=lambda_.Code.from_asset("assets/ec2-stack/lambda"),
            role=self.lambda_role,
            timeout=Duration.minutes(5),
            environment={
                "SSM_DOCUMENT_NAME": self.f5_bridge_setup_document.name,
                "KINESIS_STREAM_NAME": kinesis_stream.stream_name
            },
            description="Lambda para instalación automática de agentes F5"
        )
        
        # Launch Template con configuración completa
        self.launch_template = ec2.LaunchTemplate(
            self, "F5BridgeLaunchTemplate",
            launch_template_name=f"{project_config['prefix']}-f5-bridge-lt",
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, 
                ec2.InstanceSize.MEDIUM
            ),
            machine_image=ec2.MachineImage.latest_amazon_linux2(),
            security_group=self.f5_bridge_sg,
            user_data=user_data,
            role=self.ec2_role,
            detailed_monitoring=True,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(
                        volume_size=20,
                        volume_type=ec2.EbsDeviceVolumeType.GP3,
                        encrypted=True,
                        delete_on_termination=True
                    )
                )
            ]
        )
        
        # Auto Scaling Group - CORREGIDO: Sin desired_capacity
        self.asg = autoscaling.AutoScalingGroup(
            self, "F5BridgeAutoScalingGroup",
            vpc=vpc,
            launch_template=self.launch_template,
            min_capacity=1,
            max_capacity=1
            # desired_capacity ELIMINADO - AWS manejará el valor inicial
        )
        
        # Tags
        Tags.of(self.asg).add("Name", f"{project_config['prefix']}-f5-bridge")
        Tags.of(self.asg).add("Purpose", "F5-ETL-Multiformato")
        Tags.of(self.asg).add("KinesisAgent", "Configured")
        Tags.of(self.asg).add("AssetsSource", "S3-External")
        
        # Outputs
        CfnOutput(
            self, "F5BridgeAutoScalingGroupName",
            value=self.asg.auto_scaling_group_name,
            description="Auto Scaling Group para F5 Bridge con assets externos"
        )
        
        CfnOutput(
            self, "F5BridgeSSMDocumentName",
            value=self.f5_bridge_setup_document.name,
            description="SSM Document para setup F5 Bridge (desde assets)"
        )
        
        CfnOutput(
            self, "InstallAgentsLambdaName",
            value=self.install_agents_lambda.function_name,
            description="Lambda function para instalación de agentes (desde assets)"
        )
        
        CfnOutput(
            self, "EC2AssetsLocation",
            value=f"s3://{raw_bucket.bucket_name}/ec2-assets/",
            description="Ubicación de assets EC2 en S3"
        )
        
        # Store references
        self.security_group = self.f5_bridge_sg
        self.instance_role = self.ec2_role
        self.ssm_document = self.f5_bridge_setup_document
        self.lambda_function = self.install_agents_lambda
