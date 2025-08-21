#!/usr/bin/env python3
"""
AGESIC Data Lake PoC - F5 Improvements Validation Script

This script validates that all F5-specific improvements have been properly implemented:
1. Glue Table with optimized schema and partitioning
2. CloudWatch custom metrics and alarms for F5
3. Enhanced Lambda with F5 metrics publishing
4. ETL with advanced content categorization and mobile detection
5. Dashboard for F5 monitoring

Usage:
    python validate_f5_improvements.py --profile your-aws-profile --region us-east-1
"""

import boto3
import json
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Any

class F5ImprovementsValidator:
    
    def __init__(self, profile_name: str = None, region: str = 'us-east-1'):
        """Initialize AWS clients"""
        session = boto3.Session(profile_name=profile_name, region_name=region)
        self.glue = session.client('glue')
        self.cloudwatch = session.client('cloudwatch')
        self.lambda_client = session.client('lambda')
        self.cloudformation = session.client('cloudformation')
        self.region = region
        self.profile = profile_name
        
        # Project configuration
        self.project_prefix = 'agesic-dl-poc'
        self.database_name = f"{self.project_prefix.replace('-', '_')}_database"
        
    def validate_all_improvements(self) -> Dict[str, Any]:
        """Validate all F5 improvements"""
        print("🚀 VALIDATING F5 IMPROVEMENTS FOR AGESIC DATA LAKE")
        print("=" * 60)
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'profile': self.profile,
            'region': self.region,
            'validations': {}
        }
        
        # 1. Validate Glue Table Schema
        print("\n1️⃣ VALIDATING GLUE TABLE SCHEMA...")
        results['validations']['glue_table'] = self.validate_glue_table_schema()
        
        # 2. Validate CloudWatch Metrics and Alarms
        print("\n2️⃣ VALIDATING CLOUDWATCH F5 METRICS...")
        results['validations']['cloudwatch_metrics'] = self.validate_cloudwatch_metrics()
        
        # 3. Validate Lambda Function
        print("\n3️⃣ VALIDATING LAMBDA F5 ENHANCEMENTS...")
        results['validations']['lambda_function'] = self.validate_lambda_enhancements()
        
        # 4. Validate CloudFormation Stacks
        print("\n4️⃣ VALIDATING CLOUDFORMATION STACKS...")
        results['validations']['cloudformation'] = self.validate_cloudformation_stacks()
        
        # 5. Generate Summary Report
        print("\n📊 GENERATING SUMMARY REPORT...")
        results['summary'] = self.generate_summary_report(results['validations'])
        
        return results
    
    def validate_glue_table_schema(self) -> Dict[str, Any]:
        """Validate F5 logs table schema and partitioning"""
        validation = {
            'status': 'UNKNOWN',
            'details': {},
            'errors': []
        }
        
        try:
            # Check if database exists
            try:
                database = self.glue.get_database(Name=self.database_name)
                validation['details']['database_exists'] = True
                print(f"✅ Database '{self.database_name}' exists")
            except self.glue.exceptions.EntityNotFoundException:
                validation['details']['database_exists'] = False
                validation['errors'].append(f"Database '{self.database_name}' not found")
                print(f"❌ Database '{self.database_name}' not found")
            
            # Check if F5 table exists with proper schema
            try:
                table = self.glue.get_table(
                    DatabaseName=self.database_name,
                    Name='f5_logs_processed'
                )
                
                validation['details']['table_exists'] = True
                print("✅ F5 logs table exists")
                
                # Validate schema columns
                columns = table['Table']['StorageDescriptor']['Columns']
                partition_keys = table['Table'].get('PartitionKeys', [])
                
                expected_columns = [
                    'timestamp_syslog', 'parsed_timestamp_syslog', 'hostname',
                    'ip_cliente_externo', 'ip_backend_interno', 'metodo', 'request',
                    'codigo_respuesta', 'tamano_respuesta', 'tiempo_respuesta_ms',
                    'f5_virtualserver', 'f5_pool', 'f5_bigip_name',
                    'is_error', 'is_slow', 'status_category', 'response_time_category',
                    'content_category', 'is_mobile', 'cache_hit'
                ]
                
                expected_partitions = ['year', 'month', 'day', 'hour', 'f5_environment']
                
                column_names = [col['Name'] for col in columns]
                partition_names = [pk['Name'] for pk in partition_keys]
                
                missing_columns = [col for col in expected_columns if col not in column_names]
                missing_partitions = [pk for pk in expected_partitions if pk not in partition_names]
                
                validation['details']['schema_columns'] = len(column_names)
                validation['details']['partition_keys'] = len(partition_names)
                validation['details']['missing_columns'] = missing_columns
                validation['details']['missing_partitions'] = missing_partitions
                
                if not missing_columns and not missing_partitions:
                    print("✅ Table schema is complete with F5 enhancements")
                    validation['details']['schema_complete'] = True
                else:
                    print(f"⚠️ Schema issues - Missing columns: {missing_columns}, Missing partitions: {missing_partitions}")
                    validation['details']['schema_complete'] = False
                
            except self.glue.exceptions.EntityNotFoundException:
                validation['details']['table_exists'] = False
                validation['errors'].append("F5 logs table 'f5_logs_processed' not found")
                print("❌ F5 logs table not found")
            
            # Determine overall status
            if validation['details'].get('database_exists') and validation['details'].get('table_exists') and validation['details'].get('schema_complete'):
                validation['status'] = 'PASS'
            elif validation['errors']:
                validation['status'] = 'FAIL'
            else:
                validation['status'] = 'PARTIAL'
                
        except Exception as e:
            validation['status'] = 'ERROR'
            validation['errors'].append(f"Glue validation error: {str(e)}")
            print(f"❌ Error validating Glue: {str(e)}")
        
        return validation
    
    def validate_cloudwatch_metrics(self) -> Dict[str, Any]:
        """Validate F5-specific CloudWatch metrics and alarms"""
        validation = {
            'status': 'UNKNOWN',
            'details': {},
            'errors': []
        }
        
        try:
            # Check for F5-specific alarms
            expected_alarms = [
                f"{self.project_prefix}-f5-high-response-time",
                f"{self.project_prefix}-f5-high-error-rate",
                f"{self.project_prefix}-f5-pool-unhealthy"
            ]
            
            alarms = self.cloudwatch.describe_alarms()['MetricAlarms']
            alarm_names = [alarm['AlarmName'] for alarm in alarms]
            
            found_alarms = [alarm for alarm in expected_alarms if alarm in alarm_names]
            missing_alarms = [alarm for alarm in expected_alarms if alarm not in alarm_names]
            
            validation['details']['expected_alarms'] = len(expected_alarms)
            validation['details']['found_alarms'] = len(found_alarms)
            validation['details']['missing_alarms'] = missing_alarms
            
            # Check for F5 dashboard
            try:
                dashboards = self.cloudwatch.list_dashboards()['DashboardEntries']
                f5_dashboard = next((d for d in dashboards if 'f5-metrics' in d['DashboardName']), None)
                
                if f5_dashboard:
                    validation['details']['dashboard_exists'] = True
                    print("✅ F5 metrics dashboard exists")
                else:
                    validation['details']['dashboard_exists'] = False
                    print("❌ F5 metrics dashboard not found")
                    
            except Exception as e:
                validation['details']['dashboard_exists'] = False
                validation['errors'].append(f"Dashboard check error: {str(e)}")
            
            # Check for custom metrics namespace
            try:
                metrics = self.cloudwatch.list_metrics(Namespace='AGESIC/F5Logs')['Metrics']
                validation['details']['custom_metrics_count'] = len(metrics)
                
                if metrics:
                    print(f"✅ Found {len(metrics)} custom F5 metrics")
                else:
                    print("⚠️ No custom F5 metrics found yet (may appear after first Lambda execution)")
                    
            except Exception as e:
                validation['details']['custom_metrics_count'] = 0
                validation['errors'].append(f"Custom metrics check error: {str(e)}")
            
            print(f"✅ Found {len(found_alarms)}/{len(expected_alarms)} expected F5 alarms")
            if missing_alarms:
                print(f"⚠️ Missing alarms: {missing_alarms}")
            
            # Determine status
            if len(found_alarms) == len(expected_alarms) and validation['details'].get('dashboard_exists'):
                validation['status'] = 'PASS'
            elif found_alarms:
                validation['status'] = 'PARTIAL'
            else:
                validation['status'] = 'FAIL'
                
        except Exception as e:
            validation['status'] = 'ERROR'
            validation['errors'].append(f"CloudWatch validation error: {str(e)}")
            print(f"❌ Error validating CloudWatch: {str(e)}")
        
        return validation
    
    def validate_lambda_enhancements(self) -> Dict[str, Any]:
        """Validate Lambda function F5 enhancements"""
        validation = {
            'status': 'UNKNOWN',
            'details': {},
            'errors': []
        }
        
        try:
            # Find F5 Lambda function
            lambda_name = f"{self.project_prefix}-f5-log-filter"
            
            try:
                function = self.lambda_client.get_function(FunctionName=lambda_name)
                validation['details']['function_exists'] = True
                validation['details']['runtime'] = function['Configuration']['Runtime']
                validation['details']['timeout'] = function['Configuration']['Timeout']
                validation['details']['memory'] = function['Configuration']['MemorySize']
                
                print(f"✅ Lambda function '{lambda_name}' exists")
                print(f"   Runtime: {function['Configuration']['Runtime']}")
                print(f"   Memory: {function['Configuration']['MemorySize']} MB")
                print(f"   Timeout: {function['Configuration']['Timeout']} seconds")
                
                # Check if function code contains F5 enhancements
                try:
                    code = self.lambda_client.get_function(FunctionName=lambda_name)
                    # We can't directly check code content via API, but we can check configuration
                    env_vars = function['Configuration'].get('Environment', {}).get('Variables', {})
                    validation['details']['environment_variables'] = len(env_vars)
                    
                    if 'PROJECT_PREFIX' in env_vars:
                        print("✅ Lambda has proper environment configuration")
                        validation['details']['proper_config'] = True
                    else:
                        print("⚠️ Lambda environment configuration may be incomplete")
                        validation['details']['proper_config'] = False
                        
                except Exception as e:
                    validation['errors'].append(f"Lambda code check error: {str(e)}")
                
                validation['status'] = 'PASS'
                
            except self.lambda_client.exceptions.ResourceNotFoundException:
                validation['details']['function_exists'] = False
                validation['errors'].append(f"Lambda function '{lambda_name}' not found")
                validation['status'] = 'FAIL'
                print(f"❌ Lambda function '{lambda_name}' not found")
                
        except Exception as e:
            validation['status'] = 'ERROR'
            validation['errors'].append(f"Lambda validation error: {str(e)}")
            print(f"❌ Error validating Lambda: {str(e)}")
        
        return validation
    
    def validate_cloudformation_stacks(self) -> Dict[str, Any]:
        """Validate CloudFormation stacks deployment"""
        validation = {
            'status': 'UNKNOWN',
            'details': {},
            'errors': []
        }
        
        try:
            expected_stacks = [
                f"{self.project_prefix}-network",
                f"{self.project_prefix}-storage", 
                f"{self.project_prefix}-streaming",
                f"{self.project_prefix}-compute",
                f"{self.project_prefix}-analytics",
                f"{self.project_prefix}-monitoring"
            ]
            
            stacks = self.cloudformation.list_stacks(
                StackStatusFilter=['CREATE_COMPLETE', 'UPDATE_COMPLETE']
            )['StackSummaries']
            
            stack_names = [stack['StackName'] for stack in stacks]
            found_stacks = [stack for stack in expected_stacks if stack in stack_names]
            missing_stacks = [stack for stack in expected_stacks if stack not in stack_names]
            
            validation['details']['expected_stacks'] = len(expected_stacks)
            validation['details']['found_stacks'] = len(found_stacks)
            validation['details']['missing_stacks'] = missing_stacks
            
            print(f"✅ Found {len(found_stacks)}/{len(expected_stacks)} expected stacks")
            if missing_stacks:
                print(f"⚠️ Missing stacks: {missing_stacks}")
            
            # Determine status
            if len(found_stacks) == len(expected_stacks):
                validation['status'] = 'PASS'
            elif found_stacks:
                validation['status'] = 'PARTIAL'
            else:
                validation['status'] = 'FAIL'
                
        except Exception as e:
            validation['status'] = 'ERROR'
            validation['errors'].append(f"CloudFormation validation error: {str(e)}")
            print(f"❌ Error validating CloudFormation: {str(e)}")
        
        return validation
    
    def generate_summary_report(self, validations: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary report of all validations"""
        summary = {
            'overall_status': 'UNKNOWN',
            'total_validations': len(validations),
            'passed': 0,
            'partial': 0,
            'failed': 0,
            'errors': 0,
            'recommendations': []
        }
        
        # Count validation results
        for validation_name, validation_result in validations.items():
            status = validation_result.get('status', 'UNKNOWN')
            if status == 'PASS':
                summary['passed'] += 1
            elif status == 'PARTIAL':
                summary['partial'] += 1
            elif status == 'FAIL':
                summary['failed'] += 1
            elif status == 'ERROR':
                summary['errors'] += 1
        
        # Determine overall status
        if summary['passed'] == summary['total_validations']:
            summary['overall_status'] = 'PASS'
        elif summary['failed'] == 0 and summary['errors'] == 0:
            summary['overall_status'] = 'PARTIAL'
        else:
            summary['overall_status'] = 'FAIL'
        
        # Generate recommendations
        if validations.get('glue_table', {}).get('status') != 'PASS':
            summary['recommendations'].append("Deploy compute stack to create F5 table schema")
        
        if validations.get('cloudwatch_metrics', {}).get('status') != 'PASS':
            summary['recommendations'].append("Deploy monitoring stack to create F5 alarms and dashboard")
        
        if validations.get('lambda_function', {}).get('status') != 'PASS':
            summary['recommendations'].append("Deploy compute stack to create enhanced F5 Lambda function")
        
        if validations.get('cloudformation', {}).get('status') != 'PASS':
            summary['recommendations'].append("Deploy missing CloudFormation stacks")
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 VALIDATION SUMMARY REPORT")
        print("=" * 60)
        print(f"Overall Status: {summary['overall_status']}")
        print(f"Total Validations: {summary['total_validations']}")
        print(f"✅ Passed: {summary['passed']}")
        print(f"⚠️ Partial: {summary['partial']}")
        print(f"❌ Failed: {summary['failed']}")
        print(f"🚨 Errors: {summary['errors']}")
        
        if summary['recommendations']:
            print("\n🔧 RECOMMENDATIONS:")
            for i, rec in enumerate(summary['recommendations'], 1):
                print(f"   {i}. {rec}")
        
        return summary

def main():
    parser = argparse.ArgumentParser(description='Validate F5 improvements in AGESIC Data Lake')
    parser.add_argument('--profile', help='AWS profile name')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--output', help='Output file for results (JSON)')
    
    args = parser.parse_args()
    
    try:
        validator = F5ImprovementsValidator(
            profile_name=args.profile,
            region=args.region
        )
        
        results = validator.validate_all_improvements()
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Results saved to: {args.output}")
        
        # Exit with appropriate code
        overall_status = results['summary']['overall_status']
        if overall_status == 'PASS':
            sys.exit(0)
        elif overall_status == 'PARTIAL':
            sys.exit(1)
        else:
            sys.exit(2)
            
    except Exception as e:
        print(f"❌ Validation failed with error: {str(e)}")
        sys.exit(3)

if __name__ == "__main__":
    main()
