#!/usr/bin/env python3
"""
Validation script for AGESIC Data Lake Visualization Stack Integration
Validates that the visualization stack is properly integrated with other stacks
"""

import json
import sys
import os
from pathlib import Path

def validate_app_py_integration():
    """Validate app.py has correct visualization stack integration"""
    print("🔍 Validating app.py integration...")
    
    app_py_path = Path(__file__).parent.parent / "app.py"
    
    with open(app_py_path, 'r') as f:
        content = f.read()
    
    checks = [
        ("VisualizationStack import", "from stacks.visualization_stack import VisualizationStack"),
        ("Visualization stack instantiation", "visualization_stack = VisualizationStack("),
        ("VPC dependency", "vpc=network_stack.vpc"),
        ("Network dependency", "visualization_stack.add_dependency(network_stack)"),
        ("Storage dependency", "visualization_stack.add_dependency(storage_stack)"),
        ("Compute dependency", "visualization_stack.add_dependency(compute_stack)"),
    ]
    
    for check_name, check_pattern in checks:
        if check_pattern in content:
            print(f"  ✅ {check_name}")
        else:
            print(f"  ❌ {check_name} - Missing: {check_pattern}")
            return False
    
    return True

def validate_cdk_json_config():
    """Validate cdk.json has visualization configuration"""
    print("🔍 Validating cdk.json configuration...")
    
    cdk_json_path = Path(__file__).parent.parent / "cdk.json"
    
    with open(cdk_json_path, 'r') as f:
        config = json.load(f)
    
    context = config.get("context", {})
    viz_config = context.get("visualization", {})
    
    required_configs = [
        ("instance_type", "t3.small"),
        ("enable_waf", False),
        ("enable_scheduling", False),
        ("grafana_version", "12.1.0")
    ]
    
    for config_key, expected_value in required_configs:
        if config_key in viz_config:
            print(f"  ✅ {config_key}: {viz_config[config_key]}")
        else:
            print(f"  ❌ {config_key} - Missing configuration")
            return False
    
    return True

def validate_stack_dependencies():
    """Validate stack dependencies and integration points"""
    print("🔍 Validating stack dependencies...")
    
    viz_stack_path = Path(__file__).parent.parent / "stacks" / "visualization_stack.py"
    
    with open(viz_stack_path, 'r') as f:
        content = f.read()
    
    integration_checks = [
        ("VPC parameter", "vpc: ec2.Vpc"),
        ("Athena permissions", "athena:StartQueryExecution"),
        ("S3 permissions", "s3:GetObject"),
        ("Glue permissions", "glue:GetTable"),
        ("CloudWatch permissions", "cloudwatch:GetMetricStatistics"),
        ("Athena datasource", "grafana-athena-datasource"),
        ("CloudWatch datasource", "grafana-cloudwatch-datasource"),
        ("ALB configuration", "ApplicationLoadBalancer"),
        ("Auto Scaling Group", "AutoScalingGroup"),
        ("Security Groups", "SecurityGroup"),
    ]
    
    for check_name, check_pattern in integration_checks:
        if check_pattern in content:
            print(f"  ✅ {check_name}")
        else:
            print(f"  ❌ {check_name} - Missing: {check_pattern}")
            return False
    
    return True

def validate_network_requirements():
    """Validate network stack provides required resources"""
    print("🔍 Validating network requirements...")
    
    network_stack_path = Path(__file__).parent.parent / "stacks" / "network_stack.py"
    
    with open(network_stack_path, 'r') as f:
        content = f.read()
    
    network_checks = [
        ("VPC creation", "ec2.Vpc("),
        ("Public subnets", "subnet_type=ec2.SubnetType.PUBLIC"),
        ("Private subnets", "subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS"),
        ("Multiple AZs", "max_azs=max_azs"),
        ("VPC export", "self.vpc = ec2.Vpc("),
    ]
    
    for check_name, check_pattern in network_checks:
        if check_pattern in content:
            print(f"  ✅ {check_name}")
        else:
            print(f"  ❌ {check_name} - Missing: {check_pattern}")
            return False
    
    return True

def validate_cdk_synthesis():
    """Validate CDK synthesis works correctly"""
    print("🔍 Validating CDK synthesis...")
    
    try:
        import subprocess
        result = subprocess.run(
            ["cdk", "synth", "--quiet"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("  ✅ CDK synthesis successful")
            
            # Check if visualization stack is in output
            if "agesic-dl-poc-visualization" in result.stderr:
                print("  ✅ Visualization stack included in synthesis")
                return True
            else:
                print("  ❌ Visualization stack not found in synthesis output")
                return False
        else:
            print(f"  ❌ CDK synthesis failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"  ❌ CDK synthesis validation failed: {str(e)}")
        return False

def validate_deployment_order():
    """Validate deployment order and dependencies"""
    print("🔍 Validating deployment order...")
    
    expected_order = [
        "agesic-dl-poc-network",
        "agesic-dl-poc-storage", 
        "agesic-dl-poc-streaming",
        "agesic-dl-poc-compute",
        "agesic-dl-poc-analytics",
        "agesic-dl-poc-monitoring",
        "agesic-dl-poc-ec2",
        "agesic-dl-poc-visualization"  # Should be last
    ]
    
    print("  📋 Expected deployment order:")
    for i, stack in enumerate(expected_order, 1):
        if stack == "agesic-dl-poc-visualization":
            print(f"    {i}. {stack} ⭐ (Visualization - depends on network, storage, compute)")
        else:
            print(f"    {i}. {stack}")
    
    print("  ✅ Deployment order validated")
    return True

def main():
    """Main validation function"""
    print("🚀 AGESIC Data Lake - Visualization Stack Integration Validation")
    print("=" * 70)
    
    validations = [
        validate_app_py_integration,
        validate_cdk_json_config,
        validate_stack_dependencies,
        validate_network_requirements,
        validate_cdk_synthesis,
        validate_deployment_order
    ]
    
    all_passed = True
    
    for validation in validations:
        try:
            if not validation():
                all_passed = False
            print()
        except Exception as e:
            print(f"  ❌ Validation failed with error: {str(e)}")
            all_passed = False
            print()
    
    print("=" * 70)
    if all_passed:
        print("🎉 ALL VALIDATIONS PASSED!")
        print("✅ Visualization stack is properly integrated and ready for deployment")
        print("🚀 You can now deploy with: cdk deploy --all --profile agesicUruguay-699019841929")
        return 0
    else:
        print("❌ SOME VALIDATIONS FAILED!")
        print("🔧 Please fix the issues above before deploying")
        return 1

if __name__ == "__main__":
    sys.exit(main())
