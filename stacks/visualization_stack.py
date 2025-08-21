from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_s3 as s3,
    CfnOutput
)
from constructs import Construct

class VisualizationStack(Stack):
    """
    Visualization Stack simplificado para Grafana
    """
    
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc, **kwargs) -> None:
        # Filtrar kwargs para evitar parámetros no esperados
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in ['env', 'description']}
        super().__init__(scope, construct_id, **filtered_kwargs)
        
        # Obtener valores de contexto
        project_config = self.node.try_get_context("project")
        
        # Security Group para Grafana
        self.grafana_sg = ec2.SecurityGroup(
            self, "GrafanaSecurityGroup",
            vpc=vpc,
            description="Security Group para Grafana",
            allow_all_outbound=True
        )
        
        # Outputs
        CfnOutput(
            self, "GrafanaSecurityGroupId",
            value=self.grafana_sg.security_group_id,
            description="Security Group ID para Grafana"
        )
        
        # Store references
        self.security_group = self.grafana_sg
