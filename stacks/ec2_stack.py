from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_kinesis as kinesis,
    aws_autoscaling as autoscaling,
    aws_lambda as lambda_,
    aws_events as events,
    aws_events_targets as targets,
    Duration,
    CfnOutput,
    RemovalPolicy
)
from constructs import Construct
import os

class EC2Stack(Stack):
    
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc, 
                 kinesis_stream: kinesis.Stream, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Get context values
        project_config = self.node.try_get_context("project")
        ec2_config = self.node.try_get_context("ec2") or {}
        
        # Configuration parameters
        enable_scheduling = ec2_config.get("enable_scheduling", False)
        
        # Read UserData script from assets (short version)
        assets_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'configurations')
        userdata_path = os.path.join(assets_path, 'ec2_userdata_short.sh')
        
        with open(userdata_path, 'r') as f:
            userdata_script = f.read()
        
        # IAM Role for EC2 instance
        self.ec2_role = iam.Role(
            self, "EC2InstanceRole",
            role_name=f"{project_config['prefix']}-ec2-role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
            ]
        )
        
        # Grant permissions to write to Kinesis
        kinesis_stream.grant_write(self.ec2_role)
        
        # Grant CloudWatch permissions for monitoring
        self.ec2_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudwatch:PutMetricData",
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogStreams"
                ],
                resources=["*"]
            )
        )
        
        # Get latest Amazon Linux 2 AMI
        amzn_linux = ec2.MachineImage.latest_amazon_linux2(
            edition=ec2.AmazonLinuxEdition.STANDARD,
            virtualization=ec2.AmazonLinuxVirt.HVM,
            storage=ec2.AmazonLinuxStorage.GENERAL_PURPOSE
        )
        
        # Security Group for EC2 instance
        self.ec2_security_group = ec2.SecurityGroup(
            self, "LogGeneratorSecurityGroup",
            vpc=vpc,
            security_group_name=f"{project_config['prefix']}-log-generator-sg",
            description="Security group for log generator EC2 instance",
            allow_all_outbound=False  # Set to False to avoid warning
        )
        
        # Allow HTTPS outbound for AWS API calls
        self.ec2_security_group.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS outbound for AWS APIs"
        )
        
        # Allow HTTP outbound for package downloads
        self.ec2_security_group.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP outbound for package downloads"
        )
        
        # UserData with dynamic values
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            f"export KINESIS_STREAM_NAME='{kinesis_stream.stream_name}'",
            f"export AWS_DEFAULT_REGION='{self.region}'",
            userdata_script
        )
        
        # Launch Template for Spot instances
        self.launch_template = ec2.LaunchTemplate(
            self, "LogGeneratorLaunchTemplate",
            launch_template_name=f"{project_config['prefix']}-log-generator-lt",
            machine_image=amzn_linux,
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3,
                ec2.InstanceSize.MICRO
            ),
            security_group=self.ec2_security_group,
            role=self.ec2_role,
            user_data=user_data,
            detailed_monitoring=True,
            require_imdsv2=True,
            spot_options=ec2.LaunchTemplateSpotOptions(
                max_price=0.005,  # Max $0.005 per hour
                request_type=ec2.SpotRequestType.ONE_TIME  # Changed from PERSISTENT
            )
        )
        
        # Auto Scaling Group with Spot instances
        self.auto_scaling_group = autoscaling.AutoScalingGroup(
            self, "LogGeneratorASG",
            auto_scaling_group_name=f"{project_config['prefix']}-log-generator-asg",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            launch_template=self.launch_template,
            min_capacity=1,
            max_capacity=1,
            # Remove desired_capacity to avoid warning about reset on every deployment
            health_checks=autoscaling.HealthChecks.ec2(
                grace_period=Duration.minutes(5)
            ),
            update_policy=autoscaling.UpdatePolicy.rolling_update(
                max_batch_size=1,
                min_instances_in_service=0,
                pause_time=Duration.minutes(5)
            )
        )
        
        # Add tags to ASG
        self.auto_scaling_group.node.add_metadata("Name", f"{project_config['prefix']}-log-generator")
        
        # Lambda functions for scheduling (optional)
        if enable_scheduling:
            # Start instances Lambda
            start_lambda = lambda_.Function(
                self, "StartLogGeneratorFunction",
                runtime=lambda_.Runtime.PYTHON_3_9,
                handler="index.lambda_handler",
                code=lambda_.Code.from_inline("""
import boto3
import json
import os

def lambda_handler(event, context):
    autoscaling = boto3.client('autoscaling')
    
    # Get ASG name from environment variable
    asg_name = os.environ['ASG_NAME']
    
    try:
        # Set desired capacity to 1
        autoscaling.set_desired_capacity(
            AutoScalingGroupName=asg_name,
            DesiredCapacity=1,
            HonorCooldown=False
        )
        
        print(f'Started Log Generator ASG: {asg_name}')
        
        return {
            'statusCode': 200,
            'body': json.dumps(f'Started Log Generator ASG: {asg_name}')
        }
    except Exception as e:
        print(f'Error: {str(e)}')
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error starting Log Generator: {str(e)}')
        }
                """),
                environment={
                    "ASG_NAME": self.auto_scaling_group.auto_scaling_group_name
                },
                timeout=Duration.minutes(1),
                description="Start Log Generator instances at 9:00 AM"
            )
            
            # Stop instances Lambda
            stop_lambda = lambda_.Function(
                self, "StopLogGeneratorFunction",
                runtime=lambda_.Runtime.PYTHON_3_9,
                handler="index.lambda_handler",
                code=lambda_.Code.from_inline("""
import boto3
import json
import os

def lambda_handler(event, context):
    autoscaling = boto3.client('autoscaling')
    
    # Get ASG name from environment variable
    asg_name = os.environ['ASG_NAME']
    
    try:
        # Set desired capacity to 0
        autoscaling.set_desired_capacity(
            AutoScalingGroupName=asg_name,
            DesiredCapacity=0,
            HonorCooldown=False
        )
        
        print(f'Stopped Log Generator ASG: {asg_name}')
        
        return {
            'statusCode': 200,
            'body': json.dumps(f'Stopped Log Generator ASG: {asg_name}')
        }
    except Exception as e:
        print(f'Error: {str(e)}')
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error stopping Log Generator: {str(e)}')
        }
                """),
                environment={
                    "ASG_NAME": self.auto_scaling_group.auto_scaling_group_name
                },
                timeout=Duration.minutes(1),
                description="Stop Log Generator instances at 5:00 PM"
            )
            
            # Grant permissions to Lambda functions
            start_lambda.add_to_role_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "autoscaling:SetDesiredCapacity",
                        "autoscaling:DescribeAutoScalingGroups"
                    ],
                    resources=[self.auto_scaling_group.auto_scaling_group_arn]
                )
            )
            
            stop_lambda.add_to_role_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "autoscaling:SetDesiredCapacity",
                        "autoscaling:DescribeAutoScalingGroups"
                    ],
                    resources=[self.auto_scaling_group.auto_scaling_group_arn]
                )
            )
            
            # EventBridge rules for scheduling
            schedule_config = ec2_config.get("schedule", {})
            start_time = schedule_config.get("start_time", "09:00")
            stop_time = schedule_config.get("stop_time", "17:00")
            
            start_hour, start_minute = start_time.split(":")
            stop_hour, stop_minute = stop_time.split(":")
            
            # Start rule (Monday to Friday at 9:00 AM)
            start_rule = events.Rule(
                self, "StartLogGeneratorRule",
                schedule=events.Schedule.cron(
                    minute=start_minute,
                    hour=start_hour,
                    week_day="MON-FRI"
                ),
                description=f"Start Log Generator instances at {start_time} (Mon-Fri)"
            )
            start_rule.add_target(targets.LambdaFunction(start_lambda))
            
            # Stop rule (Monday to Friday at 5:00 PM)
            stop_rule = events.Rule(
                self, "StopLogGeneratorRule",
                schedule=events.Schedule.cron(
                    minute=stop_minute,
                    hour=stop_hour,
                    week_day="MON-FRI"
                ),
                description=f"Stop Log Generator instances at {stop_time} (Mon-Fri)"
            )
            stop_rule.add_target(targets.LambdaFunction(stop_lambda))
        
        # Outputs
        CfnOutput(
            self, "LaunchTemplateId",
            value=self.launch_template.launch_template_id,
            description="Launch template ID for log generator"
        )
        
        CfnOutput(
            self, "AutoScalingGroupName",
            value=self.auto_scaling_group.auto_scaling_group_name,
            description="Auto Scaling Group name"
        )
        
        CfnOutput(
            self, "EC2RoleArn",
            value=self.ec2_role.role_arn,
            description="IAM role ARN for EC2 instances"
        )
        
        CfnOutput(
            self, "SSMSessionCommand",
            value=f"aws ssm start-session --target <instance-id> --profile <your-profile>",
            description="Command to connect via SSM Session Manager"
        )
        
        if enable_scheduling:
            schedule_config = ec2_config.get("schedule", {})
            start_time = schedule_config.get("start_time", "09:00")
            stop_time = schedule_config.get("stop_time", "17:00")
            
            CfnOutput(
                self, "SchedulingEnabled",
                value=f"Start: {start_time}, Stop: {stop_time} (Mon-Fri)",
                description="Log Generator scheduling configuration"
            )
            
            CfnOutput(
                self, "StartLambdaFunction",
                value=start_lambda.function_name,
                description="Lambda function name for starting instances"
            )
            
            CfnOutput(
                self, "StopLambdaFunction",
                value=stop_lambda.function_name,
                description="Lambda function name for stopping instances"
            )
        else:
            CfnOutput(
                self, "SchedulingStatus",
                value="Disabled - Instances run 24/7",
                description="Scheduling is disabled, instances run continuously"
            )
