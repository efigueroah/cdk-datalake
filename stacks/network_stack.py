from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda as lambda_,
    custom_resources as cr,
    Duration,
    CfnOutput,
    RemovalPolicy
)
from constructs import Construct
import json

class NetworkStack(Stack):
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Obtener valores de contexto
        project_config = self.node.try_get_context("project")
        networking_config = self.node.try_get_context("networking")
        
        # Crear VPC
        # Ensure we have exactly the number of AZs specified in configuration
        max_azs = networking_config["availability_zones"]
        if max_azs < 2:
            raise ValueError(
                f"ALB requires at least 2 availability zones. "
                f"Current configuration specifies {max_azs} AZs. "
                f"Please set 'availability_zones' to at least 2 in cdk.json."
            )
        
        self.vpc = ec2.Vpc(
            self, "DataLakeVPC",
            vpc_name=f"{project_config['prefix']}-vpc",
            ip_addresses=ec2.IpAddresses.cidr(networking_config["vpc_cidr"]),
            max_azs=max_azs,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name=f"{project_config['prefix']}-public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name=f"{project_config['prefix']}-private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                )
            ],
            enable_dns_hostnames=True,
            enable_dns_support=True
        )
        
        # Security Group for Lambda functions
        self.lambda_security_group = ec2.SecurityGroup(
            self, "LambdaSecurityGroup",
            vpc=self.vpc,
            security_group_name=f"{project_config['prefix']}-lambda-sg",
            description="Security group for Lambda functions",
            allow_all_outbound=False  # Set to False to avoid warning
        )
        
        # Security Group for Glue jobs
        self.glue_security_group = ec2.SecurityGroup(
            self, "GlueSecurityGroup",
            vpc=self.vpc,
            security_group_name=f"{project_config['prefix']}-glue-sg",
            description="Security group for Glue jobs",
            allow_all_outbound=False  # Set to False to avoid warning
        )
        
        # Security Group for EC2 instances (log generation)
        self.ec2_security_group = ec2.SecurityGroup(
            self, "EC2SecurityGroup",
            vpc=self.vpc,
            security_group_name=f"{project_config['prefix']}-ec2-sg",
            description="Security group for EC2 instances",
            allow_all_outbound=False  # Set to False to avoid warning
        )
        
        # Security Group for SSM VPC Endpoints
        self.ssm_endpoint_security_group = ec2.SecurityGroup(
            self, "SSMEndpointSecurityGroup",
            vpc=self.vpc,
            security_group_name=f"{project_config['prefix']}-ssm-endpoint-sg",
            description="Security group for SSM VPC endpoints",
            allow_all_outbound=False
        )
        
        # Allow HTTPS inbound from EC2 instances to SSM endpoints
        self.ssm_endpoint_security_group.add_ingress_rule(
            peer=self.ec2_security_group,
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS from EC2 instances for SSM"
        )
        
        # Allow HTTPS outbound for Lambda functions
        self.lambda_security_group.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS outbound for AWS APIs"
        )
        
        # Allow HTTPS outbound for Glue jobs
        self.glue_security_group.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS outbound for AWS APIs"
        )
        
        # Allow Glue self-communication for distributed processing
        self.glue_security_group.add_ingress_rule(
            peer=self.glue_security_group,
            connection=ec2.Port.all_traffic(),
            description="Allow Glue self-communication"
        )
        
        self.glue_security_group.add_egress_rule(
            peer=self.glue_security_group,
            connection=ec2.Port.all_traffic(),
            description="Allow Glue self-communication"
        )
        
        # Allow HTTPS outbound for EC2 instances
        self.ec2_security_group.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS outbound for AWS APIs"
        )
        
        # Allow HTTP outbound for EC2 instances (package downloads)
        self.ec2_security_group.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP outbound for package downloads"
        )
        
        # VPC Endpoints for AWS services (cost optimization)
        self.s3_endpoint = self.vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)]
        )
        
        # SSM VPC Endpoints for Session Manager
        self.ssm_endpoint = self.vpc.add_interface_endpoint(
            "SSMEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SSM,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[self.ssm_endpoint_security_group]
        )
        
        self.ssm_messages_endpoint = self.vpc.add_interface_endpoint(
            "SSMMessagesEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[self.ssm_endpoint_security_group]
        )
        
        self.ec2_messages_endpoint = self.vpc.add_interface_endpoint(
            "EC2MessagesEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.EC2_MESSAGES,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[self.ssm_endpoint_security_group]
        )
        
        # Custom Resource to clean up GuardDuty VPC Endpoints before stack deletion
        cleanup_lambda = lambda_.Function(
            self, "GuardDutyCleanupFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_inline("""
import boto3
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    try:
        ec2 = boto3.client('ec2')
        vpc_id = event['ResourceProperties']['VpcId']
        
        logger.info(f"Processing {event['RequestType']} for VPC {vpc_id}")
        
        if event['RequestType'] == 'Delete':
            # Find GuardDuty VPC Endpoints in this VPC
            response = ec2.describe_vpc_endpoints(
                Filters=[
                    {'Name': 'vpc-id', 'Values': [vpc_id]},
                    {'Name': 'vpc-endpoint-type', 'Values': ['Interface']},
                    {'Name': 'state', 'Values': ['available']}
                ]
            )
            
            guardduty_endpoints = []
            for endpoint in response['VpcEndpoints']:
                # Check if this is a GuardDuty managed endpoint
                if 'GuardDutyManagedSecurityGroup' in str(endpoint.get('Groups', [])):
                    guardduty_endpoints.append(endpoint['VpcEndpointId'])
                    logger.info(f"Found GuardDuty endpoint: {endpoint['VpcEndpointId']}")
            
            # Delete GuardDuty endpoints
            for endpoint_id in guardduty_endpoints:
                try:
                    logger.info(f"Attempting to delete GuardDuty endpoint: {endpoint_id}")
                    ec2.delete_vpc_endpoints(VpcEndpointIds=[endpoint_id])
                    logger.info(f"Successfully deleted GuardDuty endpoint: {endpoint_id}")
                except Exception as e:
                    logger.warning(f"Could not delete GuardDuty endpoint {endpoint_id}: {str(e)}")
                    # Continue with other endpoints
            
            if guardduty_endpoints:
                logger.info(f"Cleaned up {len(guardduty_endpoints)} GuardDuty VPC endpoints")
            else:
                logger.info("No GuardDuty VPC endpoints found to clean up")
        
        return {
            'Status': 'SUCCESS',
            'PhysicalResourceId': f"guardduty-cleanup-{vpc_id}",
            'Data': {
                'Message': f'GuardDuty cleanup completed for VPC {vpc_id}'
            }
        }
        
    except Exception as e:
        logger.error(f"Error in GuardDuty cleanup: {str(e)}")
        return {
            'Status': 'FAILED',
            'Reason': str(e),
            'PhysicalResourceId': f"guardduty-cleanup-{event.get('ResourceProperties', {}).get('VpcId', 'unknown')}"
        }
            """),
            timeout=Duration.minutes(5),
            initial_policy=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "ec2:DescribeVpcEndpoints",
                        "ec2:DeleteVpcEndpoints",
                        "ec2:DescribeNetworkInterfaces"
                    ],
                    resources=["*"]
                )
            ]
        )
        
        # Custom Resource that triggers the cleanup
        guardduty_cleanup = cr.AwsCustomResource(
            self, "GuardDutyCleanup",
            on_delete=cr.AwsSdkCall(
                service="Lambda",
                action="invoke",
                parameters={
                    "FunctionName": cleanup_lambda.function_name,
                    "Payload": json.dumps({
                        "RequestType": "Delete",
                        "ResourceProperties": {
                            "VpcId": self.vpc.vpc_id
                        }
                    })
                },
                physical_resource_id=cr.PhysicalResourceId.of(f"guardduty-cleanup-{self.vpc.vpc_id}")
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["lambda:InvokeFunction"],
                    resources=[cleanup_lambda.function_arn]
                )
            ])
        )
        
        # Outputs
        CfnOutput(
            self, "VPCId",
            value=self.vpc.vpc_id,
            description="VPC ID for the Data Lake"
        )
        
        CfnOutput(
            self, "PrivateSubnetIds",
            value=",".join([subnet.subnet_id for subnet in self.vpc.private_subnets]),
            description="Private subnet IDs"
        )
        
        CfnOutput(
            self, "PublicSubnetIds",
            value=",".join([subnet.subnet_id for subnet in self.vpc.public_subnets]),
            description="Public subnet IDs"
        )
        
        CfnOutput(
            self, "AvailabilityZones",
            value=",".join(self.vpc.availability_zones),
            description="Availability zones used by the VPC"
        )
        
        CfnOutput(
            self, "PublicSubnetCount",
            value=str(len(self.vpc.public_subnets)),
            description="Number of public subnets (should be >= 2 for ALB)"
        )
