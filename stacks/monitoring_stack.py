from aws_cdk import (
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_sns as sns,
    CfnOutput
)
from constructs import Construct

class MonitoringStack(Stack):
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Obtener valores de contexto
        project_config = self.node.try_get_context("project")
        notifications_config = self.node.try_get_context("notifications")
        
        # Tema SNS para alertas F5
        self.sns_topic = sns.Topic(
            self, "F5AlertsTopic",
            topic_name=f"{project_config['prefix']}-f5-alerts",
            display_name="Alertas de análisis F5 AGESIC"
        )
        
        # Suscripción de email si está configurada
        if notifications_config and notifications_config.get("email"):
            sns.Subscription(
                self, "EmailSubscription",
                topic=self.sns_topic,
                protocol=sns.SubscriptionProtocol.EMAIL,
                endpoint=notifications_config["email"]
            )
        
        # Dashboard básico de CloudWatch para F5
        self.dashboard = cloudwatch.Dashboard(
            self, "F5AnalyticsDashboard",
            dashboard_name=f"{project_config['prefix']}-f5-analytics"
        )
        
        # Salidas
        CfnOutput(
            self, "SNSTopicArn",
            value=self.sns_topic.topic_arn,
            description="ARN del tema SNS para alertas de análisis F5"
        )
        
        CfnOutput(
            self, "DashboardName",
            value=self.dashboard.dashboard_name,
            description="Nombre del dashboard CloudWatch para análisis F5"
        )
