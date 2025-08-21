#!/usr/bin/env python3
"""
Script de validación para migración AWS Glue 4.0 → 5.0
AGESIC Data Lake PoC

Valida que la migración se haya implementado correctamente:
- Glue version 5.0 configurada
- Nuevos parámetros de logging
- Log Groups actualizados
- Script ETL compatible

Autor: AWS Data Engineer
Fecha: 2025-08-15
"""

import boto3
import json
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Any

def validate_glue_50_migration(profile: str, region: str) -> Dict[str, Any]:
    """Validar migración completa a Glue 5.0."""
    
    print("🚀 VALIDACIÓN: Migración AWS Glue 4.0 → 5.0")
    print("=" * 50)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"🔧 Profile: {profile}")
    print(f"🌍 Región: {region}")
    print()
    
    session = boto3.Session(profile_name=profile, region_name=region)
    glue_client = session.client('glue')
    logs_client = session.client('logs')
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'profile': profile,
        'region': region,
        'validation_results': {},
        'overall_status': 'UNKNOWN'
    }
    
    # 1. Validar configuración del Job ETL
    print("1️⃣ VALIDANDO CONFIGURACIÓN GLUE ETL JOB")
    print("-" * 40)
    
    job_name = "agesic-dl-poc-f5-etl-job"
    try:
        response = glue_client.get_job(JobName=job_name)
        job_config = response['Job']
        
        # Verificar versión Glue
        glue_version = job_config.get('GlueVersion', 'Unknown')
        print(f"📊 Glue Version: {glue_version}")
        
        # Verificar argumentos específicos de Glue 5.0
        default_args = job_config.get('DefaultArguments', {})
        
        glue_50_params = {
            '--custom-logGroup-prefix': default_args.get('--custom-logGroup-prefix'),
            '--custom-logStream-prefix': default_args.get('--custom-logStream-prefix'),
            '--conf': default_args.get('--conf')
        }
        
        print("🔧 Parámetros Glue 5.0:")
        for param, value in glue_50_params.items():
            status = "✅" if value else "❌"
            print(f"   {status} {param}: {value or 'No configurado'}")
        
        # Verificar que parámetros deprecados no estén presentes
        deprecated_params = ['--enable-continuous-cloudwatch-log']
        deprecated_found = []
        for param in deprecated_params:
            if param in default_args:
                deprecated_found.append(param)
        
        if deprecated_found:
            print(f"⚠️  Parámetros deprecados encontrados: {deprecated_found}")
        else:
            print("✅ Sin parámetros deprecados")
        
        results['validation_results']['glue_job'] = {
            'glue_version': glue_version,
            'glue_50_params': glue_50_params,
            'deprecated_params': deprecated_found,
            'status': 'SUCCESS' if glue_version == '5.0' and all(glue_50_params.values()) else 'PARTIAL'
        }
        
    except Exception as e:
        print(f"❌ Error obteniendo configuración del job: {e}")
        results['validation_results']['glue_job'] = {'status': 'ERROR', 'error': str(e)}
    
    print()
    
    # 2. Validar Log Groups para Glue 5.0
    print("2️⃣ VALIDANDO LOG GROUPS GLUE 5.0")
    print("-" * 40)
    
    expected_log_groups = [
        '/aws-glue/jobs/error',
        '/agesic-dl-poc-etl/aws-glue/jobs/error'
    ]
    
    log_group_status = {}
    for log_group_name in expected_log_groups:
        try:
            response = logs_client.describe_log_groups(logGroupNamePrefix=log_group_name)
            log_groups = response.get('logGroups', [])
            
            found = any(lg['logGroupName'] == log_group_name for lg in log_groups)
            log_group_status[log_group_name] = found
            
            status = "✅" if found else "❌"
            print(f"   {status} {log_group_name}: {'Existe' if found else 'No encontrado'}")
            
        except Exception as e:
            log_group_status[log_group_name] = False
            print(f"   ❌ {log_group_name}: Error - {e}")
    
    results['validation_results']['log_groups'] = log_group_status
    print()
    
    # 3. Validar script ETL
    print("3️⃣ VALIDANDO SCRIPT ETL")
    print("-" * 40)
    
    script_path = "assets/glue_scripts/etl_f5_to_parquet.py"
    try:
        with open(script_path, 'r') as f:
            script_content = f.read()
        
        # Verificar comentarios de Glue 5.0
        has_glue_50_comments = 'GLUE 5.0' in script_content
        has_spark_version_info = 'Spark 3.5.4' in script_content
        has_optimizations = 'spark.sql.adaptive.enabled' in script_content
        
        print(f"   {'✅' if has_glue_50_comments else '❌'} Comentarios Glue 5.0: {has_glue_50_comments}")
        print(f"   {'✅' if has_spark_version_info else '❌'} Info Spark 3.5.4: {has_spark_version_info}")
        print(f"   {'✅' if has_optimizations else '❌'} Optimizaciones Spark: {has_optimizations}")
        
        results['validation_results']['etl_script'] = {
            'has_glue_50_comments': has_glue_50_comments,
            'has_spark_version_info': has_spark_version_info,
            'has_optimizations': has_optimizations,
            'status': 'SUCCESS' if all([has_glue_50_comments, has_spark_version_info]) else 'PARTIAL'
        }
        
    except FileNotFoundError:
        print(f"   ❌ Script no encontrado: {script_path}")
        results['validation_results']['etl_script'] = {'status': 'ERROR', 'error': 'Script not found'}
    
    print()
    
    # 4. Estado general
    print("4️⃣ ESTADO GENERAL DE LA MIGRACIÓN")
    print("-" * 40)
    
    job_ok = results['validation_results'].get('glue_job', {}).get('status') == 'SUCCESS'
    logs_ok = all(log_group_status.values())
    script_ok = results['validation_results'].get('etl_script', {}).get('status') in ['SUCCESS', 'PARTIAL']
    
    if job_ok and logs_ok and script_ok:
        results['overall_status'] = 'MIGRATION_COMPLETE'
        status_msg = "🎯 MIGRACIÓN COMPLETA - Glue 5.0 configurado correctamente"
    elif job_ok:
        results['overall_status'] = 'MIGRATION_PARTIAL'
        status_msg = "⚠️ MIGRACIÓN PARCIAL - Job configurado, revisar logs y script"
    else:
        results['overall_status'] = 'MIGRATION_FAILED'
        status_msg = "❌ MIGRACIÓN FALLIDA - Revisar configuración del job"
    
    print(status_msg)
    
    # 5. Recomendaciones
    print()
    print("5️⃣ RECOMENDACIONES")
    print("-" * 40)
    
    if results['overall_status'] == 'MIGRATION_COMPLETE':
        print("💡 ¡Migración exitosa! Proceder con testing del ETL job")
        print("💡 Ejecutar job manualmente para validar funcionamiento")
        print("💡 Verificar logs en /aws-glue/jobs/error")
    else:
        print("💡 Completar configuración faltante antes del despliegue")
        if not job_ok:
            print("💡 Verificar configuración del Glue job")
        if not logs_ok:
            print("💡 Crear Log Groups faltantes")
        if not script_ok:
            print("💡 Actualizar script ETL con optimizaciones")
    
    return results

def main():
    parser = argparse.ArgumentParser(
        description='Validar migración AWS Glue 4.0 → 5.0'
    )
    parser.add_argument('--profile', default='efigueroah_efigueroa',
                       help='AWS profile (default: efigueroah_efigueroa)')
    parser.add_argument('--region', default='us-east-2',
                       help='AWS region (default: us-east-2)')
    parser.add_argument('--output', help='Archivo para guardar resultados JSON')
    
    args = parser.parse_args()
    
    try:
        results = validate_glue_50_migration(args.profile, args.region)
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n💾 Resultados guardados en: {args.output}")
        
        # Exit code basado en el estado
        exit_codes = {
            'MIGRATION_COMPLETE': 0,
            'MIGRATION_PARTIAL': 1,
            'MIGRATION_FAILED': 2,
            'UNKNOWN': 3
        }
        
        sys.exit(exit_codes.get(results['overall_status'], 3))
        
    except Exception as e:
        print(f"❌ Error durante la validación: {e}")
        sys.exit(4)

if __name__ == '__main__':
    main()
