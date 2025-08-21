#!/usr/bin/env python3
"""
AGESIC Data Lake - Enhanced EC2 Stack Validation Script
Validates all components of the enhanced F5 Bridge setup
"""

import boto3
import json
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

class EnhancedStackValidator:
    def __init__(self, profile_name: str = "agesicUruguay-699019841929", region: str = "us-east-2"):
        self.profile_name = profile_name
        self.region = region
        self.session = boto3.Session(profile_name=profile_name, region_name=region)
        
        # Initialize clients
        self.cfn = self.session.client('cloudformation')
        self.ec2 = self.session.client('ec2')
        self.ssm = self.session.client('ssm')
        self.autoscaling = self.session.client('autoscaling')
        self.lambda_client = self.session.client('lambda')
        self.events = self.session.client('events')
        
        self.stack_name = "agesic-dl-poc-ec2-enhanced"
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "stack_name": self.stack_name,
            "profile": profile_name,
            "region": region,
            "validations": {},
            "summary": {
                "total_checks": 0,
                "passed": 0,
                "failed": 0,
                "warnings": 0
            }
        }
    
    def log_info(self, message: str):
        print(f"[INFO] {message}")
    
    def log_success(self, message: str):
        print(f"[SUCCESS] {message}")
    
    def log_warning(self, message: str):
        print(f"[WARNING] {message}")
    
    def log_error(self, message: str):
        print(f"[ERROR] {message}")
    
    def add_result(self, check_name: str, status: str, message: str, details: Optional[Dict] = None):
        self.results["validations"][check_name] = {
            "status": status,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        
        self.results["summary"]["total_checks"] += 1
        if status == "PASS":
            self.results["summary"]["passed"] += 1
        elif status == "FAIL":
            self.results["summary"]["failed"] += 1
        elif status == "WARNING":
            self.results["summary"]["warnings"] += 1
    
    def validate_cloudformation_stack(self) -> bool:
        """Validate CloudFormation stack exists and is in good state"""
        self.log_info("Validating CloudFormation stack...")
        
        try:
            response = self.cfn.describe_stacks(StackName=self.stack_name)
            stack = response['Stacks'][0]
            
            status = stack['StackStatus']
            if status in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
                self.add_result(
                    "cloudformation_stack",
                    "PASS",
                    f"Stack is in good state: {status}",
                    {"stack_status": status, "creation_time": str(stack.get('CreationTime'))}
                )
                self.log_success(f"CloudFormation stack status: {status}")
                return True
            else:
                self.add_result(
                    "cloudformation_stack",
                    "FAIL",
                    f"Stack in unexpected state: {status}",
                    {"stack_status": status}
                )
                self.log_error(f"CloudFormation stack in unexpected state: {status}")
                return False
                
        except Exception as e:
            self.add_result(
                "cloudformation_stack",
                "FAIL",
                f"Stack not found or error: {str(e)}",
                {"error": str(e)}
            )
            self.log_error(f"CloudFormation stack validation failed: {e}")
            return False
    
    def validate_ssm_documents(self) -> bool:
        """Validate SSM Documents exist and are accessible"""
        self.log_info("Validating SSM Documents...")
        
        documents = [
            "agesic-dl-poc-complete-setup",
            "agesic-dl-poc-install-agents"
        ]
        
        all_valid = True
        document_details = {}
        
        for doc_name in documents:
            try:
                response = self.ssm.describe_document(Name=doc_name)
                doc_info = response['Document']
                
                document_details[doc_name] = {
                    "status": doc_info['Status'],
                    "document_type": doc_info['DocumentType'],
                    "document_format": doc_info['DocumentFormat'],
                    "created_date": str(doc_info.get('CreatedDate')),
                    "owner": doc_info.get('Owner')
                }
                
                if doc_info['Status'] == 'Active':
                    self.log_success(f"SSM Document {doc_name} is active")
                else:
                    self.log_warning(f"SSM Document {doc_name} status: {doc_info['Status']}")
                    all_valid = False
                    
            except Exception as e:
                self.log_error(f"SSM Document {doc_name} not found: {e}")
                document_details[doc_name] = {"error": str(e)}
                all_valid = False
        
        status = "PASS" if all_valid else "FAIL"
        self.add_result(
            "ssm_documents",
            status,
            f"SSM Documents validation: {len([d for d in document_details.values() if 'error' not in d])}/{len(documents)} found",
            document_details
        )
        
        return all_valid
    
    def validate_ec2_infrastructure(self) -> bool:
        """Validate EC2 infrastructure components"""
        self.log_info("Validating EC2 infrastructure...")
        
        # Get Auto Scaling Group
        try:
            asg_response = self.autoscaling.describe_auto_scaling_groups(
                AutoScalingGroupNames=[f"agesic-dl-poc-f5-bridge-asg-enhanced"]
            )
            
            if not asg_response['AutoScalingGroups']:
                self.add_result(
                    "ec2_infrastructure",
                    "FAIL",
                    "Auto Scaling Group not found",
                    {}
                )
                return False
            
            asg = asg_response['AutoScalingGroups'][0]
            instances = asg['Instances']
            
            # Check for running instances
            running_instances = [i for i in instances if i['LifecycleState'] == 'InService']
            
            infrastructure_details = {
                "asg_name": asg['AutoScalingGroupName'],
                "desired_capacity": asg['DesiredCapacity'],
                "min_size": asg['MinSize'],
                "max_size": asg['MaxSize'],
                "total_instances": len(instances),
                "running_instances": len(running_instances),
                "instance_ids": [i['InstanceId'] for i in running_instances]
            }
            
            if running_instances:
                self.add_result(
                    "ec2_infrastructure",
                    "PASS",
                    f"EC2 infrastructure healthy: {len(running_instances)} running instances",
                    infrastructure_details
                )
                self.log_success(f"Found {len(running_instances)} running F5 Bridge instances")
                return True
            else:
                self.add_result(
                    "ec2_infrastructure",
                    "WARNING",
                    "No running instances found in Auto Scaling Group",
                    infrastructure_details
                )
                self.log_warning("No running instances found")
                return False
                
        except Exception as e:
            self.add_result(
                "ec2_infrastructure",
                "FAIL",
                f"Error validating EC2 infrastructure: {str(e)}",
                {"error": str(e)}
            )
            self.log_error(f"EC2 infrastructure validation failed: {e}")
            return False
    
    def validate_lambda_function(self) -> bool:
        """Validate Lambda function for automated agent installation"""
        self.log_info("Validating Lambda function...")
        
        try:
            # Find Lambda function (name pattern may vary)
            functions = self.lambda_client.list_functions()['Functions']
            install_lambda = None
            
            for func in functions:
                if 'InstallAgents' in func['FunctionName'] and 'agesic-dl-poc' in func['FunctionName']:
                    install_lambda = func
                    break
            
            if not install_lambda:
                self.add_result(
                    "lambda_function",
                    "WARNING",
                    "Install agents Lambda function not found",
                    {}
                )
                self.log_warning("Install agents Lambda function not found")
                return False
            
            lambda_details = {
                "function_name": install_lambda['FunctionName'],
                "runtime": install_lambda['Runtime'],
                "state": install_lambda['State'],
                "last_modified": install_lambda['LastModified'],
                "timeout": install_lambda['Timeout'],
                "memory_size": install_lambda['MemorySize']
            }
            
            if install_lambda['State'] == 'Active':
                self.add_result(
                    "lambda_function",
                    "PASS",
                    f"Lambda function is active: {install_lambda['FunctionName']}",
                    lambda_details
                )
                self.log_success(f"Lambda function {install_lambda['FunctionName']} is active")
                return True
            else:
                self.add_result(
                    "lambda_function",
                    "FAIL",
                    f"Lambda function in unexpected state: {install_lambda['State']}",
                    lambda_details
                )
                self.log_error(f"Lambda function state: {install_lambda['State']}")
                return False
                
        except Exception as e:
            self.add_result(
                "lambda_function",
                "FAIL",
                f"Error validating Lambda function: {str(e)}",
                {"error": str(e)}
            )
            self.log_error(f"Lambda function validation failed: {e}")
            return False
    
    def validate_eventbridge_rules(self) -> bool:
        """Validate EventBridge rules for automated installation"""
        self.log_info("Validating EventBridge rules...")
        
        try:
            rules = self.events.list_rules()['Rules']
            install_rule = None
            
            for rule in rules:
                if 'InstallOnLaunch' in rule['Name'] and 'agesic-dl-poc' in rule['Name']:
                    install_rule = rule
                    break
            
            if not install_rule:
                self.add_result(
                    "eventbridge_rules",
                    "WARNING",
                    "Install on launch EventBridge rule not found",
                    {}
                )
                self.log_warning("Install on launch EventBridge rule not found")
                return False
            
            rule_details = {
                "rule_name": install_rule['Name'],
                "state": install_rule['State'],
                "description": install_rule.get('Description', ''),
                "event_pattern": install_rule.get('EventPattern')
            }
            
            if install_rule['State'] == 'ENABLED':
                self.add_result(
                    "eventbridge_rules",
                    "PASS",
                    f"EventBridge rule is enabled: {install_rule['Name']}",
                    rule_details
                )
                self.log_success(f"EventBridge rule {install_rule['Name']} is enabled")
                return True
            else:
                self.add_result(
                    "eventbridge_rules",
                    "WARNING",
                    f"EventBridge rule is disabled: {install_rule['Name']}",
                    rule_details
                )
                self.log_warning(f"EventBridge rule is disabled")
                return False
                
        except Exception as e:
            self.add_result(
                "eventbridge_rules",
                "FAIL",
                f"Error validating EventBridge rules: {str(e)}",
                {"error": str(e)}
            )
            self.log_error(f"EventBridge rules validation failed: {e}")
            return False
    
    def test_ssm_connectivity(self) -> bool:
        """Test SSM connectivity to running instances"""
        self.log_info("Testing SSM connectivity...")
        
        try:
            # Get running instances
            instances = self.ec2.describe_instances(
                Filters=[
                    {'Name': 'tag:Name', 'Values': ['*f5-bridge*']},
                    {'Name': 'instance-state-name', 'Values': ['running']}
                ]
            )
            
            instance_ids = []
            for reservation in instances['Reservations']:
                for instance in reservation['Instances']:
                    instance_ids.append(instance['InstanceId'])
            
            if not instance_ids:
                self.add_result(
                    "ssm_connectivity",
                    "WARNING",
                    "No running instances found for SSM connectivity test",
                    {}
                )
                self.log_warning("No running instances for SSM test")
                return False
            
            # Test SSM connectivity
            connectivity_results = {}
            for instance_id in instance_ids:
                try:
                    # Send a simple command to test connectivity
                    response = self.ssm.send_command(
                        InstanceIds=[instance_id],
                        DocumentName="AWS-RunShellScript",
                        Parameters={
                            'commands': ['echo "SSM connectivity test successful"']
                        },
                        Comment="Enhanced stack validation - SSM connectivity test"
                    )
                    
                    command_id = response['Command']['CommandId']
                    
                    # Wait a bit and check status
                    time.sleep(5)
                    
                    invocation = self.ssm.get_command_invocation(
                        CommandId=command_id,
                        InstanceId=instance_id
                    )
                    
                    connectivity_results[instance_id] = {
                        "status": invocation['Status'],
                        "command_id": command_id
                    }
                    
                    if invocation['Status'] in ['Success', 'InProgress']:
                        self.log_success(f"SSM connectivity OK for {instance_id}")
                    else:
                        self.log_warning(f"SSM connectivity issue for {instance_id}: {invocation['Status']}")
                        
                except Exception as e:
                    connectivity_results[instance_id] = {"error": str(e)}
                    self.log_error(f"SSM connectivity failed for {instance_id}: {e}")
            
            successful_connections = len([r for r in connectivity_results.values() if r.get('status') in ['Success', 'InProgress']])
            
            if successful_connections > 0:
                self.add_result(
                    "ssm_connectivity",
                    "PASS",
                    f"SSM connectivity successful: {successful_connections}/{len(instance_ids)} instances",
                    connectivity_results
                )
                return True
            else:
                self.add_result(
                    "ssm_connectivity",
                    "FAIL",
                    "SSM connectivity failed for all instances",
                    connectivity_results
                )
                return False
                
        except Exception as e:
            self.add_result(
                "ssm_connectivity",
                "FAIL",
                f"Error testing SSM connectivity: {str(e)}",
                {"error": str(e)}
            )
            self.log_error(f"SSM connectivity test failed: {e}")
            return False
    
    def run_all_validations(self) -> Dict:
        """Run all validation checks"""
        self.log_info("Starting enhanced EC2 stack validation...")
        
        # Run all validation checks
        validations = [
            self.validate_cloudformation_stack,
            self.validate_ssm_documents,
            self.validate_ec2_infrastructure,
            self.validate_lambda_function,
            self.validate_eventbridge_rules,
            self.test_ssm_connectivity
        ]
        
        for validation in validations:
            try:
                validation()
            except Exception as e:
                self.log_error(f"Validation error: {e}")
        
        # Generate summary
        summary = self.results["summary"]
        self.log_info(f"Validation completed: {summary['passed']} passed, {summary['failed']} failed, {summary['warnings']} warnings")
        
        if summary['failed'] == 0:
            self.log_success("All critical validations passed!")
        else:
            self.log_error(f"{summary['failed']} critical validations failed")
        
        return self.results
    
    def save_results(self, output_file: str):
        """Save validation results to file"""
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        self.log_info(f"Validation results saved to {output_file}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate AGESIC Enhanced EC2 Stack')
    parser.add_argument('--profile', default='agesicUruguay-699019841929', help='AWS profile name')
    parser.add_argument('--region', default='us-east-2', help='AWS region')
    parser.add_argument('--output', help='Output file for results (JSON format)')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    try:
        validator = EnhancedStackValidator(args.profile, args.region)
        results = validator.run_all_validations()
        
        if args.output:
            validator.save_results(args.output)
        
        # Exit with error code if any critical validations failed
        if results["summary"]["failed"] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        print(f"[ERROR] Validation script failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
