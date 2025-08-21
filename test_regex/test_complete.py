#!/usr/bin/env python3
"""
Prueba completa del parser F5 - Validación final antes de despliegue
"""

import json
import sys
from f5_log_parser import F5LogParser
from validate_kinesis_config import KinesisAgentValidator

def main():
    print("🚀 PRUEBA COMPLETA DEL PARSER F5")
    print("=" * 50)
    
    # Datos de prueba
    test_lines = [
        'Aug  8 03:33:33 www.gub.uy 186.48.242.68 [10.233.114.14] - "" [08/Aug/2025:03:33:33 -0300] "GET /direccion-general-impositiva/sites/direccion-general-impositiva/files/js/optimized/js_jiFsxh7G-xhq8-kNY5JOQzg7iGjjdKKHeJOnBhXRQ9Y.1Y_hXdDeLuHhX6RaroZ2rqX-4SwNhz4SI8p7lUR0ds0.js?t0epq7 HTTP/1.1" 200 905 "https://www.gub.uy/direccion-general-impositiva/personas?gad_source=1&gad_campaignid=22722788345&gbraid=0AAAABAVnRy_w87dsVPZAMrVSKf3B8vTrL&gclid=EAIaIQobChMIrKLS0Mv6jgMV8l9IAB0k1w5cEAAYASACEgLAxPD_BwE" "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1" Time 4213 Age "" "application/javascript" "" - "/PortalGubUy/wwwgubuy-TEPROD-443/wwwgubuy-TEPROD-443" "/PortalGubUy/wwwgubuy-TEPROD-443/Pool_dgi" TEPROD',
        'Aug  8 03:33:33 www.gub.uy 186.48.242.68 [10.233.114.14] - "" [08/Aug/2025:03:33:33 -0300] "GET /direccion-general-impositiva/sites/direccion-general-impositiva/files/js/optimized/js_I8INAQ0miW75vWTPYFMGmVDMuTV8eIPjpET3V0K8Nwg.eCPSVfCVtWzfNYs1RIjbVopFtVCVMGGx7gZf6jB75iU.js?t0epq7 HTTP/1.1" 200 849 "https://www.gub.uy/direccion-general-impositiva/personas?gad_source=1&gad_campaignid=22722788345&gbraid=0AAAABAVnRy_w87dsVPZAMrVSKf3B8vTrL&gclid=EAIaIQobChMIrKLS0Mv6jgMV8l9IAB0k1w5cEAAYASACEgLAxPD_BwE" "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1" Time 6723 Age "" "application/javascript" "" - "/PortalGubUy/wwwgubuy-TEPROD-443/wwwgubuy-TEPROD-443" "/PortalGubUy/wwwgubuy-TEPROD-443/Pool_dgi" TEPROD'
    ]
    
    # 1. Prueba del parser con grupos nombrados
    print("\n1️⃣ PARSER CON GRUPOS NOMBRADOS")
    print("-" * 30)
    
    f5_parser = F5LogParser()
    valid_count = 0
    
    for i, line in enumerate(test_lines, 1):
        parsed = f5_parser.parse_line(line)
        if parsed:
            valid_count += 1
            print(f"✅ Línea {i}: Válida")
        else:
            print(f"❌ Línea {i}: Inválida")
    
    print(f"📊 Resultado: {valid_count}/{len(test_lines)} líneas válidas")
    
    # 2. Prueba del validador de Kinesis Agent
    print("\n2️⃣ VALIDADOR DE KINESIS AGENT")
    print("-" * 30)
    
    try:
        validator = KinesisAgentValidator("kinesis_agent_config.json")
        results = validator.validate_with_test_data(test_lines)
        
        print(f"✅ Configuración cargada correctamente")
        print(f"📊 Resultado: {results['valid_lines']}/{results['total_lines']} líneas válidas")
        
        if results['valid_lines'] == len(test_lines):
            print("🎯 Todas las líneas procesadas correctamente")
        else:
            print("⚠️  Algunas líneas no se procesaron")
    
    except Exception as e:
        print(f"❌ Error en validador: {str(e)}")
        return False
    
    # 3. Comparación de resultados
    print("\n3️⃣ COMPARACIÓN DE RESULTADOS")
    print("-" * 30)
    
    line = test_lines[0]
    named_result = f5_parser.parse_line(line)
    numbered_result = validator.process_line(line)
    
    if named_result and numbered_result:
        print("✅ Ambos parsers procesan la línea correctamente")
        
        # Comparar campos clave
        key_fields = ["hostname", "ip_cliente_externo", "metodo", "codigo_respuesta", "entorno_nodo"]
        differences = 0
        
        for field in key_fields:
            named_val = str(named_result.get(field, ""))
            numbered_val = str(numbered_result.get(field, ""))
            
            if named_val != numbered_val:
                differences += 1
                print(f"⚠️  {field}: '{named_val}' vs '{numbered_val}'")
        
        if differences == 0:
            print("🎯 Campos clave coinciden perfectamente")
        else:
            print(f"⚠️  {differences} diferencias en campos clave")
    
    # 4. Validación del esquema Avro
    print("\n4️⃣ VALIDACIÓN DEL ESQUEMA AVRO")
    print("-" * 30)
    
    if named_result:
        required_fields = [
            "timestamp_syslog", "hostname", "ip_cliente_externo", "ip_red_interna",
            "metodo", "recurso", "protocolo", "codigo_respuesta", "tamano_respuesta",
            "user_agent", "tiempo_respuesta_ms", "ambiente_origen", "ambiente_pool", "entorno_nodo"
        ]
        
        missing_fields = []
        for field in required_fields:
            if field not in named_result:
                missing_fields.append(field)
        
        if not missing_fields:
            print("✅ Todos los campos requeridos están presentes")
        else:
            print(f"❌ Campos faltantes: {missing_fields}")
        
        # Validar tipos de datos
        int_fields = ["codigo_respuesta", "tamano_respuesta", "tiempo_respuesta_ms"]
        type_errors = []
        
        for field in int_fields:
            value = named_result.get(field)
            if value is not None and not isinstance(value, int):
                type_errors.append(f"{field}: {type(value)} (esperado int)")
        
        if not type_errors:
            print("✅ Tipos de datos correctos")
        else:
            print(f"⚠️  Errores de tipo: {type_errors}")
    
    # 5. Resumen final
    print("\n5️⃣ RESUMEN FINAL")
    print("-" * 30)
    
    all_tests_passed = (
        valid_count == len(test_lines) and
        results['valid_lines'] == len(test_lines) and
        not missing_fields and
        not type_errors
    )
    
    if all_tests_passed:
        print("🎉 TODAS LAS PRUEBAS PASARON")
        print("✅ Parser listo para despliegue en Kinesis Agent")
        print("\n📋 Próximos pasos:")
        print("   1. Desplegar nueva instancia EC2")
        print("   2. Copiar kinesis_agent_config.json a /etc/aws-kinesis/agent.json")
        print("   3. Reiniciar aws-kinesis-agent")
        print("   4. Monitorear métricas en CloudWatch")
        return True
    else:
        print("⚠️  ALGUNAS PRUEBAS FALLARON")
        print("🔧 Revisar configuración antes del despliegue")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
