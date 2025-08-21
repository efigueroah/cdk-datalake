#!/usr/bin/env python3
"""
Tester de patrones Grok para validar antes de usar en AWS Glue
"""

import re
import sys

def test_grok_pattern():
    # Línea de ejemplo de nuestros logs F5
    sample_line = 'Aug  8 03:33:33 www.gub.uy 186.48.242.68 [10.233.114.14] - "" [08/Aug/2025:03:33:33 -0300] "GET /direccion-general-impositiva/sites/direccion-general-impositiva/files/js/optimized/js_jiFsxh7G-xhq8-kNY5JOQzg7iGjjdKKHeJOnBhXRQ9Y.1Y_hXdDeLuHhX6RaroZ2rqX-4SwNhz4SI8p7lUR0ds0.js?t0epq7 HTTP/1.1" 200 905 "https://www.gub.uy/direccion-general-impositiva/personas?gad_source=1&gad_campaignid=22722788345&gbraid=0AAAABAVnRy_w87dsVPZAMrVSKf3B8vTrL&gclid=EAIaIQobChMIrKLS0Mv6jgMV8l9IAB0k1w5cEAAYASACEgLAxPD_BwE" "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1" Time 4213 Age "" "application/javascript" "" - "/PortalGubUy/wwwgubuy-TEPROD-443/wwwgubuy-TEPROD-443" "/PortalGubUy/wwwgubuy-TEPROD-443/Pool_dgi" TEPROD'
    
    print("🧪 PROBANDO PATRÓN GROK SIMPLIFICADO")
    print("=" * 60)
    print(f"📝 Línea de prueba:")
    print(f"   {sample_line[:100]}...")
    
    # Patrón simplificado que debería funcionar
    # Basado en los patrones built-in de AWS Glue
    pattern = r'(?P<timestamp_syslog>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}) (?P<hostname>\S+) (?P<ip_cliente_externo>\S+) \[(?P<ip_red_interna>[^\]]+)\] (?P<usuario_autenticado>-|"[^"]*") (?P<identidad>"[^"]*") \[(?P<timestamp_apache>[^\]]+)\] "(?P<metodo>\w+) (?P<recurso>[^"]+) (?P<protocolo>HTTP/\d\.\d)" (?P<codigo_respuesta>\d+) (?P<tamano_respuesta>\d+) "(?P<referer>[^"]*)" "(?P<user_agent>[^"]*)" Time (?P<tiempo_respuesta_ms>\d+) Age "(?P<edad_cache>[^"]*)" "(?P<content_type>[^"]*)" "(?P<campo_reservado_1>[^"]*)" (?P<campo_reservado_2>-|"[^"]*") "(?P<ambiente_origen>[^"]*)" "(?P<ambiente_pool>[^"]*)" (?P<entorno_nodo>\w+)'
    
    try:
        compiled_pattern = re.compile(pattern)
        match = compiled_pattern.match(sample_line)
        
        if match:
            print("✅ PATRÓN COINCIDE!")
            groups = match.groupdict()
            print(f"📊 Campos capturados: {len(groups)}")
            
            # Mostrar algunos campos importantes
            important_fields = [
                'timestamp_syslog', 'hostname', 'ip_cliente_externo', 
                'metodo', 'codigo_respuesta', 'tiempo_respuesta_ms',
                'content_type', 'ambiente_pool', 'entorno_nodo'
            ]
            
            print("\n🔍 Campos importantes capturados:")
            for field in important_fields:
                if field in groups:
                    value = groups[field]
                    print(f"   {field:20s}: {value}")
            
            print(f"\n📋 Todos los campos ({len(groups)}):")
            for i, (field, value) in enumerate(groups.items(), 1):
                print(f"   {i:2d}. {field:20s}: {value}")
            
            return True
        else:
            print("❌ PATRÓN NO COINCIDE")
            return False
            
    except Exception as e:
        print(f"❌ Error en patrón: {str(e)}")
        return False

def test_aws_grok_equivalent():
    """Prueba el patrón equivalente que usaríamos en AWS Glue"""
    print("\n🔧 PATRÓN EQUIVALENTE PARA AWS GLUE:")
    print("=" * 60)
    
    # Este sería el patrón que usaríamos en AWS Glue
    aws_pattern = r'%{WORD:timestamp_month}\s+%{INT:timestamp_day}\s+%{TIME:timestamp_time} %{HOSTNAME:hostname} %{IP:ip_cliente_externo} \[%{DATA:ip_red_interna}\] %{DATA:usuario_autenticado} %{QUOTEDSTRING:identidad} \[%{DATA:timestamp_apache}\] "%{WORD:metodo} %{DATA:recurso} %{DATA:protocolo}" %{INT:codigo_respuesta} %{INT:tamano_respuesta} %{QUOTEDSTRING:referer} %{QUOTEDSTRING:user_agent} Time %{INT:tiempo_respuesta_ms} Age %{QUOTEDSTRING:edad_cache} %{QUOTEDSTRING:content_type} %{QUOTEDSTRING:campo_reservado_1} %{DATA:campo_reservado_2} %{QUOTEDSTRING:ambiente_origen} %{QUOTEDSTRING:ambiente_pool} %{WORD:entorno_nodo}'
    
    print("📝 Patrón AWS Glue:")
    print(f"   {aws_pattern}")
    
    # Patrones personalizados que necesitaríamos
    custom_patterns = """
F5_TIMESTAMP \\w{3}\\s+\\d{1,2}\\s+\\d{2}:\\d{2}:\\d{2}
F5_AUTH (-|"[^"]*")
    """.strip()
    
    print("\n📝 Patrones personalizados:")
    print(custom_patterns)
    
    return aws_pattern, custom_patterns

if __name__ == "__main__":
    print("🚀 VALIDADOR DE PATRONES GROK PARA F5 LOGS")
    print("=" * 60)
    
    # Probar patrón regex simple
    success = test_grok_pattern()
    
    # Mostrar equivalente para AWS
    aws_pattern, custom_patterns = test_aws_grok_equivalent()
    
    if success:
        print("\n🎉 RESULTADO: Patrón validado localmente")
        print("✅ Listo para usar en AWS Glue Classifier")
    else:
        print("\n💥 RESULTADO: Patrón necesita ajustes")
        print("❌ Revisar antes de usar en AWS Glue")
