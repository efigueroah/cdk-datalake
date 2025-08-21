#!/usr/bin/env python3
"""
Script de validación para verificar que los Log Groups se eliminan automáticamente
con RemovalPolicy.DESTROY implementado en el proyecto AGESIC Data Lake PoC.

Autor: AWS Data Engineer
Fecha: 2025-08-15
Propósito: Validar la tarea crítica de eliminación automática de CloudWatch Log Groups
"""

import boto3
import json
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Any

def get_log_groups_by_prefix(logs_client, prefix: str) -> List[Dict[str, Any]]:
    """Obtener Log Groups por prefijo."""
    try:
        response = logs_client.describe_log_groups(logGroupNamePrefix=prefix)
        return response.get('logGroups', [])
    except Exception as e:
        print(f"❌ Error obteniendo Log Groups con prefijo {prefix}: {e}")
        return []

def check_cloudformation_stack_log_groups(cf_client, stack_name: str) -> Dict[str, Any]:
    """Verificar Log Groups en un stack de CloudFormation."""
    try:
        response = cf_client.describe_stack_resources(StackName=stack_name)
        log_groups = [
            resource for resource in response['StackResources']
            if resource['ResourceType'] == 'AWS::Logs::LogGroup'
        ]
        return {
            'stack_exists': True,
            'log_groups': log_groups,
            'total_log_groups': len(log_groups)
        }
    except cf_client.exceptions.ClientError as e:
        if 'does not exist' in str(e):
            return {'stack_exists': False, 'log_groups': [], 'total_log_groups': 0}
        else:
            print(f"❌ Error verificando stack {stack_name}: {e}")
            return {'stack_exists': False, 'log_groups': [], 'total_log_groups': 0}

def validate_log_groups_cleanup(profile: str, region: str) -> Dict[str, Any]:
    """Validar la implementación de limpieza automática de Log Groups."""
    
    print("🚨 VALIDACIÓN: Eliminación Automática CloudWatch Log Groups")
    print("=" * 60)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"🔧 Profile: {profile}")
    print(f"🌍 Región: {region}")
    print()
    
    # Inicializar clientes AWS
    session = boto3.Session(profile_name=profile, region_name=region)
    logs_client = session.client('logs')
    cf_client = session.client('cloudformation')
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'profile': profile,
        'region': region,
        'validation_results': {},
        'recommendations': [],
        'overall_status': 'UNKNOWN'
    }
    
    # 1. Verificar Log Groups huérfanos del proyecto
    print("1️⃣ VERIFICANDO LOG GROUPS HUÉRFANOS DEL PROYECTO")
    print("-" * 50)
    
    project_prefixes = [
        '/aws/lambda/agesic-dl-poc',
        '/aws-glue/jobs',
        '/aws-glue/crawlers/agesic-dl-poc',
        '/aws/kinesisfirehose/agesic-dl-poc'
    ]
    
    orphaned_log_groups = []
    for prefix in project_prefixes:
        log_groups = get_log_groups_by_prefix(logs_client, prefix)
        for lg in log_groups:
            orphaned_log_groups.append({
                'name': lg['logGroupName'],
                'creation_time': lg.get('creationTime', 0),
                'retention_days': lg.get('retentionInDays', 'Never expire'),
                'stored_bytes': lg.get('storedBytes', 0)
            })
    
    results['validation_results']['orphaned_log_groups'] = {
        'count': len(orphaned_log_groups),
        'log_groups': orphaned_log_groups
    }
    
    if orphaned_log_groups:
        print(f"⚠️  Encontrados {len(orphaned_log_groups)} Log Groups huérfanos:")
        for lg in orphaned_log_groups:
            print(f"   - {lg['name']} (Retención: {lg['retention_days']} días)")
        results['recommendations'].append(
            "Eliminar Log Groups huérfanos manualmente antes del próximo despliegue"
        )
    else:
        print("✅ No se encontraron Log Groups huérfanos del proyecto")
    
    print()
    
    # 2. Verificar stacks de CloudFormation
    print("2️⃣ VERIFICANDO STACKS CLOUDFORMATION")
    print("-" * 50)
    
    stacks_to_check = [
        'agesic-dl-poc-compute',
        'agesic-dl-poc-streaming',
        'agesic-dl-poc-monitoring'
    ]
    
    stack_results = {}
    for stack_name in stacks_to_check:
        stack_info = check_cloudformation_stack_log_groups(cf_client, stack_name)
        stack_results[stack_name] = stack_info
        
        if stack_info['stack_exists']:
            print(f"✅ Stack {stack_name}: {stack_info['total_log_groups']} Log Groups")
            for lg in stack_info['log_groups']:
                print(f"   - {lg['LogicalResourceId']} ({lg['ResourceStatus']})")
        else:
            print(f"ℹ️  Stack {stack_name}: No existe (OK para testing)")
    
    results['validation_results']['cloudformation_stacks'] = stack_results
    print()
    
    # 3. Verificar implementación en código CDK
    print("3️⃣ VERIFICANDO IMPLEMENTACIÓN CDK")
    print("-" * 50)
    
    cdk_files_to_check = [
        'stacks/compute_stack.py',
        'stacks/streaming_stack.py'
    ]
    
    implementation_status = {}
    for file_path in cdk_files_to_check:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                
            has_removal_policy = 'RemovalPolicy.DESTROY' in content
            has_logs_import = 'aws_logs as logs' in content
            has_explicit_log_groups = 'logs.LogGroup(' in content
            
            implementation_status[file_path] = {
                'has_removal_policy': has_removal_policy,
                'has_logs_import': has_logs_import,
                'has_explicit_log_groups': has_explicit_log_groups,
                'status': 'IMPLEMENTED' if all([has_removal_policy, has_logs_import, has_explicit_log_groups]) else 'PARTIAL'
            }
            
            status_icon = "✅" if implementation_status[file_path]['status'] == 'IMPLEMENTED' else "⚠️"
            print(f"{status_icon} {file_path}:")
            print(f"   - RemovalPolicy.DESTROY: {'✅' if has_removal_policy else '❌'}")
            print(f"   - aws_logs import: {'✅' if has_logs_import else '❌'}")
            print(f"   - Explicit LogGroups: {'✅' if has_explicit_log_groups else '❌'}")
            
        except FileNotFoundError:
            implementation_status[file_path] = {
                'status': 'FILE_NOT_FOUND',
                'error': f'Archivo {file_path} no encontrado'
            }
            print(f"❌ {file_path}: Archivo no encontrado")
    
    results['validation_results']['cdk_implementation'] = implementation_status
    print()
    
    # 4. Generar recomendaciones
    print("4️⃣ RECOMENDACIONES")
    print("-" * 50)
    
    if orphaned_log_groups:
        results['recommendations'].append(
            f"Eliminar {len(orphaned_log_groups)} Log Groups huérfanos antes del próximo despliegue"
        )
    
    implemented_files = sum(1 for status in implementation_status.values() 
                          if status.get('status') == 'IMPLEMENTED')
    total_files = len(implementation_status)
    
    if implemented_files == total_files:
        results['recommendations'].append("✅ Implementación CDK completa - Lista para testing")
        results['overall_status'] = 'READY_FOR_TESTING'
    else:
        results['recommendations'].append(
            f"⚠️ Completar implementación en {total_files - implemented_files} archivos restantes"
        )
        results['overall_status'] = 'NEEDS_IMPLEMENTATION'
    
    if not orphaned_log_groups and implemented_files == total_files:
        results['overall_status'] = 'FULLY_IMPLEMENTED'
    
    for rec in results['recommendations']:
        print(f"💡 {rec}")
    
    print()
    print("5️⃣ ESTADO GENERAL")
    print("-" * 50)
    
    status_icons = {
        'FULLY_IMPLEMENTED': '🎯',
        'READY_FOR_TESTING': '🚀',
        'NEEDS_IMPLEMENTATION': '⚠️',
        'UNKNOWN': '❓'
    }
    
    status_messages = {
        'FULLY_IMPLEMENTED': 'Implementación completa y sin Log Groups huérfanos',
        'READY_FOR_TESTING': 'Lista para testing - Implementación CDK completa',
        'NEEDS_IMPLEMENTATION': 'Requiere completar implementación CDK',
        'UNKNOWN': 'Estado desconocido - Revisar manualmente'
    }
    
    icon = status_icons.get(results['overall_status'], '❓')
    message = status_messages.get(results['overall_status'], 'Estado desconocido')
    
    print(f"{icon} ESTADO: {results['overall_status']}")
    print(f"📋 DESCRIPCIÓN: {message}")
    
    return results

def main():
    parser = argparse.ArgumentParser(
        description='Validar implementación de eliminación automática de CloudWatch Log Groups'
    )
    parser.add_argument('--profile', default='efigueroah_efigueroa',
                       help='AWS profile a usar (default: efigueroah_efigueroa)')
    parser.add_argument('--region', default='us-east-2',
                       help='AWS region (default: us-east-2)')
    parser.add_argument('--output', help='Archivo para guardar resultados JSON')
    
    args = parser.parse_args()
    
    try:
        results = validate_log_groups_cleanup(args.profile, args.region)
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n💾 Resultados guardados en: {args.output}")
        
        # Exit code basado en el estado
        exit_codes = {
            'FULLY_IMPLEMENTED': 0,
            'READY_FOR_TESTING': 0,
            'NEEDS_IMPLEMENTATION': 1,
            'UNKNOWN': 2
        }
        
        sys.exit(exit_codes.get(results['overall_status'], 2))
        
    except Exception as e:
        print(f"❌ Error durante la validación: {e}")
        sys.exit(3)

if __name__ == '__main__':
    main()
