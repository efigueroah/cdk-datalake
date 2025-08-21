#!/usr/bin/env python3
"""
Validación completa del archivo F5 con 300 registros
"""

import sys
from f5_log_parser import F5LogParser
from validate_kinesis_config import KinesisAgentValidator

def main():
    print("🚀 VALIDACIÓN COMPLETA - ARCHIVO F5 CON 300 REGISTROS")
    print("=" * 60)
    
    file_path = "extracto_logs_acceso_f5_portalgubuy.log"
    config_path = "kinesis_agent_config.json"
    
    # 1. Validar con parser de grupos nombrados
    print("\n1️⃣ PARSER CON GRUPOS NOMBRADOS")
    print("-" * 40)
    
    f5_parser = F5LogParser()
    results_named = f5_parser.parse_file(file_path)
    
    print(f"📊 Resultados del parser nombrado:")
    print(f"  Total líneas: {results_named['total_lines']}")
    print(f"  Válidas: {results_named['valid_lines']}")
    print(f"  Inválidas: {results_named['invalid_lines']}")
    
    if results_named['errors']:
        print(f"  ❌ Errores: {len(results_named['errors'])}")
        for error in results_named['errors'][:3]:  # Mostrar solo los primeros 3
            print(f"    Línea {error['line_number']}: {error['error']}")
    else:
        print(f"  ✅ Sin errores")
    
    # 2. Validar con simulador de Kinesis Agent
    print(f"\n2️⃣ SIMULADOR DE KINESIS AGENT")
    print("-" * 40)
    
    try:
        validator = KinesisAgentValidator(config_path)
        
        # Leer todas las líneas del archivo
        with open(file_path, 'r', encoding='utf-8') as f:
            all_lines = [line.strip() for line in f if line.strip()]
        
        results_kinesis = validator.validate_with_test_data(all_lines)
        
        print(f"📊 Resultados del simulador Kinesis:")
        print(f"  Total líneas: {results_kinesis['total_lines']}")
        print(f"  Válidas: {results_kinesis['valid_lines']}")
        print(f"  Inválidas: {results_kinesis['invalid_lines']}")
        
        if results_kinesis['errors']:
            print(f"  ❌ Errores: {len(results_kinesis['errors'])}")
            for error in results_kinesis['errors'][:3]:  # Mostrar solo los primeros 3
                print(f"    Línea {error['line_number']}: {error['error']}")
        else:
            print(f"  ✅ Sin errores")
    
    except Exception as e:
        print(f"❌ Error en simulador: {str(e)}")
        return False
    
    # 3. Comparación de resultados
    print(f"\n3️⃣ COMPARACIÓN DE RESULTADOS")
    print("-" * 40)
    
    if results_named['valid_lines'] == results_kinesis['valid_lines']:
        print(f"✅ Ambos parsers procesan el mismo número de líneas: {results_named['valid_lines']}")
    else:
        print(f"⚠️  Diferencia en líneas procesadas:")
        print(f"   Parser nombrado: {results_named['valid_lines']}")
        print(f"   Simulador Kinesis: {results_kinesis['valid_lines']}")
    
    # 4. Análisis de diversidad de datos
    print(f"\n4️⃣ ANÁLISIS DE DIVERSIDAD DE DATOS")
    print("-" * 40)
    
    if results_named['parsed_records']:
        # Analizar diferentes tipos de contenido
        content_types = set()
        response_codes = set()
        methods = set()
        pools = set()
        
        for record in results_named['parsed_records']:
            data = record['data']
            if data.get('content_type'):
                content_types.add(data['content_type'])
            if data.get('codigo_respuesta'):
                response_codes.add(str(data['codigo_respuesta']))
            if data.get('metodo'):
                methods.add(data['metodo'])
            if data.get('ambiente_pool'):
                pools.add(data['ambiente_pool'])
        
        print(f"📊 Diversidad encontrada:")
        print(f"  Content Types: {len(content_types)} únicos")
        print(f"    {sorted(list(content_types))[:5]}...")  # Mostrar primeros 5
        print(f"  Response Codes: {len(response_codes)} únicos")
        print(f"    {sorted(list(response_codes))}")
        print(f"  HTTP Methods: {len(methods)} únicos")
        print(f"    {sorted(list(methods))}")
        print(f"  F5 Pools: {len(pools)} únicos")
        for pool in sorted(list(pools)):
            print(f"    {pool}")
    
    # 5. Estadísticas de performance
    print(f"\n5️⃣ ESTADÍSTICAS DE PERFORMANCE")
    print("-" * 40)
    
    if results_named['parsed_records']:
        response_times = []
        response_sizes = []
        
        for record in results_named['parsed_records']:
            data = record['data']
            if data.get('tiempo_respuesta_ms'):
                response_times.append(data['tiempo_respuesta_ms'])
            if data.get('tamano_respuesta'):
                response_sizes.append(data['tamano_respuesta'])
        
        if response_times:
            print(f"📊 Tiempos de respuesta (ms):")
            print(f"  Mínimo: {min(response_times)}")
            print(f"  Máximo: {max(response_times)}")
            print(f"  Promedio: {sum(response_times) // len(response_times)}")
        
        if response_sizes:
            print(f"📊 Tamaños de respuesta (bytes):")
            print(f"  Mínimo: {min(response_sizes)}")
            print(f"  Máximo: {max(response_sizes)}")
            print(f"  Promedio: {sum(response_sizes) // len(response_sizes)}")
    
    # 6. Resumen final
    print(f"\n6️⃣ RESUMEN FINAL")
    print("-" * 40)
    
    success = (
        results_named['valid_lines'] == results_named['total_lines'] and
        results_kinesis['valid_lines'] == results_kinesis['total_lines'] and
        results_named['valid_lines'] == results_kinesis['valid_lines']
    )
    
    if success:
        print("🎉 VALIDACIÓN COMPLETA EXITOSA")
        print(f"✅ {results_named['valid_lines']}/{results_named['total_lines']} registros procesados correctamente")
        print("✅ Parser de desarrollo y Kinesis Agent coinciden 100%")
        print("✅ Configuración lista para despliegue en producción")
        
        print(f"\n📋 Configuración final:")
        print(f"  Archivo de logs: {file_path}")
        print(f"  Registros totales: {results_named['total_lines']}")
        print(f"  Tasa de éxito: 100%")
        print(f"  Configuración Kinesis: {config_path}")
        
        return True
    else:
        print("⚠️  VALIDACIÓN INCOMPLETA")
        print("🔧 Revisar errores antes del despliegue")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
