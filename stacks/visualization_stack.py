from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_autoscaling as autoscaling,
    aws_elasticloadbalancingv2 as elbv2,
    aws_wafv2 as waf,
    aws_lambda as lambda_,
    aws_events as events,
    aws_events_targets as targets,
    Duration,
    CfnOutput,
    RemovalPolicy
)
from constructs import Construct
import hashlib
import time

class VisualizationStack(Stack):
    
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Get context values
        project_config = self.node.try_get_context("project")
        viz_config = self.node.try_get_context("visualization") or {}
        
        # Generate unique suffix to avoid conflicts
        timestamp = str(int(time.time()))
        unique_suffix = hashlib.md5(f"{construct_id}-{timestamp}".encode()).hexdigest()[:8]
        
        # Configuration parameters
        instance_type = viz_config.get("instance_type", "t3.small")
        enable_waf = viz_config.get("enable_waf", False)
        enable_scheduling = viz_config.get("enable_scheduling", False)
        grafana_version = viz_config.get("grafana_version", "12.1.0")
        
        # IAM Role for Grafana EC2 instance
        grafana_role = iam.Role(
            self, "GrafanaInstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
            ],
            inline_policies={
                "AthenaAccess": iam.PolicyDocument(
                    statements=[
                        # Athena permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "athena:BatchGetQueryExecution",
                                "athena:GetQueryExecution",
                                "athena:GetQueryResults",
                                "athena:GetWorkGroup",
                                "athena:ListQueryExecutions",
                                "athena:StartQueryExecution",
                                "athena:StopQueryExecution"
                            ],
                            resources=["*"]
                        ),
                        # S3 permissions for Athena results
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:GetBucketLocation",
                                "s3:GetObject",
                                "s3:ListBucket",
                                "s3:PutObject"
                            ],
                            resources=[
                                f"arn:aws:s3:::{project_config['prefix']}-athena-results",
                                f"arn:aws:s3:::{project_config['prefix']}-athena-results/*"
                            ]
                        ),
                        # Glue Data Catalog permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "glue:GetDatabase",
                                "glue:GetDatabases",
                                "glue:GetTable",
                                "glue:GetTables",
                                "glue:GetPartition",
                                "glue:GetPartitions"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )
        
        # Security Group for Grafana
        grafana_sg = ec2.SecurityGroup(
            self, "GrafanaSecurityGroup",
            vpc=vpc,
            description="Security group for Grafana instance",
            allow_all_outbound=False
        )
        
        # Allow HTTPS outbound for AWS API calls
        grafana_sg.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS outbound for AWS APIs"
        )
        
        # Security Group for ALB
        alb_sg = ec2.SecurityGroup(
            self, "ALBSecurityGroup",
            vpc=vpc,
            description="Security group for Application Load Balancer",
            allow_all_outbound=False
        )
        
        # Allow HTTP/HTTPS inbound from internet
        alb_sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP from internet"
        )
        
        alb_sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS from internet"
        )
        
        # Allow ALB to connect to Grafana
        alb_sg.add_egress_rule(
            peer=grafana_sg,
            connection=ec2.Port.tcp(3000),
            description="Allow ALB to connect to Grafana"
        )
        
        # Allow Grafana to receive connections from ALB
        grafana_sg.add_ingress_rule(
            peer=alb_sg,
            connection=ec2.Port.tcp(3000),
            description="Allow ALB to connect to Grafana"
        )
        
        # User Data script for Grafana installation
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "#!/bin/bash",
            "yum update -y",
            "yum install -y docker",
            "systemctl start docker",
            "systemctl enable docker",
            "usermod -a -G docker ec2-user",
            "",
            f"# Install Grafana OSS {grafana_version} via Docker",
            "docker run -d \\",
            "  --name=grafana \\",
            "  -p 3000:3000 \\",
            "  -e \"GF_INSTALL_PLUGINS=grafana-athena-datasource\" \\",
            "  -e \"GF_SECURITY_ADMIN_PASSWORD=admin123\" \\",
            "  -e \"GF_SECURITY_ALLOW_EMBEDDING=true\" \\",
            "  -e \"GF_SECURITY_COOKIE_SECURE=false\" \\",
            "  -e \"GF_SECURITY_COOKIE_SAMESITE=lax\" \\",
            "  -e \"GF_ANALYTICS_REPORTING_ENABLED=false\" \\",
            "  -e \"GF_ANALYTICS_CHECK_FOR_UPDATES=false\" \\",
            "  -e \"GF_USERS_ALLOW_SIGN_UP=false\" \\",
            "  -e \"GF_USERS_ALLOW_ORG_CREATE=false\" \\",
            "  -e \"GF_SNAPSHOTS_EXTERNAL_ENABLED=false\" \\",
            "  -e \"GF_LOG_LEVEL=info\" \\",
            "  -e \"GF_SERVER_ROOT_URL=%(protocol)s://%(domain)s/\" \\",
            "  -e \"GF_SERVER_SERVE_FROM_SUB_PATH=false\" \\",
            "  -v grafana-storage:/var/lib/grafana \\",
            "  -v grafana-logs:/var/log/grafana \\",
            "  --restart=unless-stopped \\",
            f"  grafana/grafana-oss:{grafana_version}",
            "",
            "# Wait for Grafana to start",
            "sleep 45",
            "",
            "# Verify Grafana is running",
            "docker logs grafana",
            "",
            "# Create health check endpoint",
            "echo 'Grafana OSS {grafana_version} is running' > /var/log/grafana-health.log",
            "",
            "# Set up log rotation for Grafana logs",
            "cat > /etc/logrotate.d/grafana << 'EOF'",
            "/var/log/grafana-health.log {",
            "    daily",
            "    rotate 7",
            "    compress",
            "    delaycompress",
            "    missingok",
            "    notifempty",
            "}",
            "EOF"
        )
        
        # Launch Template for Grafana
        launch_template = ec2.LaunchTemplate(
            self, "GrafanaLaunchTemplate",
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            instance_type=ec2.InstanceType(instance_type),
            security_group=grafana_sg,
            role=grafana_role,
            user_data=user_data,
            detailed_monitoring=True,
            require_imdsv2=True
        )
        
        # Auto Scaling Group for Grafana (single instance)
        asg = autoscaling.AutoScalingGroup(
            self, "GrafanaAutoScalingGroup",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            launch_template=launch_template,
            min_capacity=1,
            max_capacity=1,
            health_checks=autoscaling.HealthChecks.ec2(grace_period=Duration.minutes(5))
        )
        
        # Validate that VPC has subnets in at least 2 availability zones
        if len(vpc.public_subnets) < 2:
            raise ValueError(
                f"ALB requires subnets in at least 2 availability zones. "
                f"Current VPC has {len(vpc.public_subnets)} public subnets. "
                f"Please ensure the network stack creates subnets in at least 2 AZs."
            )
        
        # Application Load Balancer
        # Ensure ALB uses subnets from at least 2 availability zones
        alb = elbv2.ApplicationLoadBalancer(
            self, "GrafanaALB",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_sg,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC,
                availability_zones=vpc.availability_zones[:2]  # Explicitly use first 2 AZs
            )
        )
        
        # Target Group for Grafana
        target_group = elbv2.ApplicationTargetGroup(
            self, "GrafanaTargetGroup",
            vpc=vpc,
            port=3000,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.INSTANCE,
            health_check=elbv2.HealthCheck(
                enabled=True,
                healthy_http_codes="200",
                path="/api/health",
                port="3000",
                protocol=elbv2.Protocol.HTTP,
                timeout=Duration.seconds(15),
                interval=Duration.seconds(30),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3
            )
        )
        
        # Add ASG to target group
        target_group.add_target(asg)
        
        # HTTP Listener (for now, no HTTPS redirect since we don't have SSL cert)
        # alb.add_listener(
        #     "HTTPListener",
        #     port=80,
        #     protocol=elbv2.ApplicationProtocol.HTTP,
        #     default_action=elbv2.ListenerAction.redirect(
        #         protocol="HTTPS",
        #         port="443",
        #         permanent=True
        #     )
        # )
        
        # HTTPS Listener - for now, only HTTP since we don't have SSL certificate
        # In production, add proper SSL certificate
        # https_listener = alb.add_listener(
        #     "HTTPSListener",
        #     port=443,
        #     protocol=elbv2.ApplicationProtocol.HTTPS,
        #     certificates=[elbv2.ListenerCertificate.from_arn("certificate-arn")],
        #     default_action=elbv2.ListenerAction.forward([target_group])
        # )
        
        # For now, use HTTP listener
        http_listener = alb.add_listener(
            "HTTPListener",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            default_action=elbv2.ListenerAction.forward([target_group])
        )
        
        # WAF (optional)
        if enable_waf:
            web_acl = waf.CfnWebACL(
                self, "GrafanaWebACL",
                scope="REGIONAL",
                default_action=waf.CfnWebACL.DefaultActionProperty(allow={}),
                rules=[
                    # Rate limiting rule
                    waf.CfnWebACL.RuleProperty(
                        name="RateLimitRule",
                        priority=1,
                        statement=waf.CfnWebACL.StatementProperty(
                            rate_based_statement=waf.CfnWebACL.RateBasedStatementProperty(
                                limit=1000,
                                aggregate_key_type="IP"
                            )
                        ),
                        action=waf.CfnWebACL.RuleActionProperty(block={}),
                        visibility_config=waf.CfnWebACL.VisibilityConfigProperty(
                            sampled_requests_enabled=True,
                            cloud_watch_metrics_enabled=True,
                            metric_name="RateLimitRule"
                        )
                    ),
                    # Geographic restriction rule
                    waf.CfnWebACL.RuleProperty(
                        name="GeoRestrictionRule",
                        priority=2,
                        statement=waf.CfnWebACL.StatementProperty(
                            geo_match_statement=waf.CfnWebACL.GeoMatchStatementProperty(
                                country_codes=["UY"]  # Only allow Uruguay
                            )
                        ),
                        action=waf.CfnWebACL.RuleActionProperty(allow={}),
                        visibility_config=waf.CfnWebACL.VisibilityConfigProperty(
                            sampled_requests_enabled=True,
                            cloud_watch_metrics_enabled=True,
                            metric_name="GeoRestrictionRule"
                        )
                    )
                ],
                visibility_config=waf.CfnWebACL.VisibilityConfigProperty(
                    sampled_requests_enabled=True,
                    cloud_watch_metrics_enabled=True,
                    metric_name="GrafanaWebACL"
                )
            )
            
            # Associate WAF with ALB
            waf.CfnWebACLAssociation(
                self, "WebACLAssociation",
                resource_arn=alb.load_balancer_arn,
                web_acl_arn=web_acl.attr_arn
            )
        
        # Lambda functions for scheduling (optional)
        if enable_scheduling:
            # Start instance Lambda
            start_lambda = lambda_.Function(
                self, "StartGrafanaFunction",
                runtime=lambda_.Runtime.PYTHON_3_9,
                handler="index.lambda_handler",
                code=lambda_.Code.from_inline("""
import boto3
import json

def lambda_handler(event, context):
    ec2 = boto3.client('ec2')
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
        
        return {
            'statusCode': 200,
            'body': json.dumps(f'Started Grafana ASG: {asg_name}')
        }
    except Exception as e:
        print(f'Error: {str(e)}')
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error starting Grafana: {str(e)}')
        }
                """),
                environment={
                    "ASG_NAME": asg.auto_scaling_group_name
                },
                timeout=Duration.minutes(1)
            )
            
            # Stop instance Lambda
            stop_lambda = lambda_.Function(
                self, "StopGrafanaFunction",
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
        
        return {
            'statusCode': 200,
            'body': json.dumps(f'Stopped Grafana ASG: {asg_name}')
        }
    except Exception as e:
        print(f'Error: {str(e)}')
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error stopping Grafana: {str(e)}')
        }
                """),
                environment={
                    "ASG_NAME": asg.auto_scaling_group_name
                },
                timeout=Duration.minutes(1)
            )
            
            # Grant permissions to Lambda functions
            start_lambda.add_to_role_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "autoscaling:SetDesiredCapacity",
                        "autoscaling:DescribeAutoScalingGroups"
                    ],
                    resources=[asg.auto_scaling_group_arn]
                )
            )
            
            stop_lambda.add_to_role_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "autoscaling:SetDesiredCapacity",
                        "autoscaling:DescribeAutoScalingGroups"
                    ],
                    resources=[asg.auto_scaling_group_arn]
                )
            )
            
            # EventBridge rules for scheduling
            schedule_config = viz_config.get("schedule", {})
            start_time = schedule_config.get("start_time", "09:00")
            stop_time = schedule_config.get("stop_time", "17:00")
            
            start_hour, start_minute = start_time.split(":")
            stop_hour, stop_minute = stop_time.split(":")
            
            # Start rule (Monday to Friday at 9:00 AM)
            start_rule = events.Rule(
                self, "StartGrafanaRule",
                schedule=events.Schedule.cron(
                    minute=start_minute,
                    hour=start_hour,
                    day="*",
                    month="*",
                    week_day="MON-FRI"
                )
            )
            start_rule.add_target(targets.LambdaFunction(start_lambda))
            
            # Stop rule (Monday to Friday at 5:00 PM)
            stop_rule = events.Rule(
                self, "StopGrafanaRule",
                schedule=events.Schedule.cron(
                    minute=stop_minute,
                    hour=stop_hour,
                    day="*",
                    month="*",
                    week_day="MON-FRI"
                )
            )
            stop_rule.add_target(targets.LambdaFunction(stop_lambda))
        
        # Outputs
        CfnOutput(
            self, "GrafanaURL",
            value=f"http://{alb.load_balancer_dns_name}",
            description=f"Grafana OSS {grafana_version} dashboard URL (HTTP for now, add SSL certificate for HTTPS)"
        )
        
        CfnOutput(
            self, "GrafanaALBDNS",
            value=alb.load_balancer_dns_name,
            description="Application Load Balancer DNS name"
        )
        
        CfnOutput(
            self, "GrafanaVersion",
            value=grafana_version,
            description="Grafana OSS version deployed"
        )
        
        CfnOutput(
            self, "GrafanaDefaultCredentials",
            value="admin / admin123",
            description="Default Grafana credentials (change after first login)"
        )
        
        if enable_waf:
            CfnOutput(
                self, "WAFWebACLArn",
                value=web_acl.attr_arn,
                description="WAF Web ACL ARN"
            )
        
        if enable_scheduling:
            CfnOutput(
                self, "SchedulingEnabled",
                value=f"Start: {start_time}, Stop: {stop_time} (Mon-Fri)",
                description="Grafana scheduling configuration"
            )
