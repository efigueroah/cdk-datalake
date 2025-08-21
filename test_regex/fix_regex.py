#!/usr/bin/env python3
"""
Script para analizar y corregir la regex de grupos numerados para Kinesis Agent
"""

import re

def analyze_regex():
    # Regex original con grupos nombrados (funciona)
    named_regex = r'(?P<timestamp_syslog>\w{3} \s+\d{1,2} \d{2}:\d{2}:\d{2}) (?P<hostname>[^\s]+) (?P<ip_cliente_externo>[^\s]+) \[(?P<ip_backend_interno>[^\]]+)\] (?P<usuario_autenticado>-|"[^"]*") (?P<identidad>"[^"]*") \[(?P<timestamp_rp>[^\]]+)\] "(?P<metodo>\w+) (?P<request>[^"]+) (?P<protocolo>HTTP/\d\.\d)" (?P<codigo_respuesta>\d+) (?P<tamano_respuesta>\d+) "(?P<referer>[^"]*)" "(?P<user_agent>[^"]*)" Time (?P<tiempo_respuesta_ms>\d+) Age "(?P<edad_cache>[^"]*)" "(?P<content_type>[^"]*)" "(?P<jsession_id>[^"]*)" (?P<campo_reservado_2>-|"[^"]*") "(?P<f5_virtualserver>[^"]*)" "(?P<f5_pool>[^"]*)" (?P<f5_bigip_name>\w+)'
    
    # Convertir a grupos numerados (sin nombres)
    numbered_regex = r'(\w{3} \s+\d{1,2} \d{2}:\d{2}:\d{2}) ([^\s]+) ([^\s]+) \[([^\]]+)\] (-|"[^"]*") ("([^"]*)") \[([^\]]+)\] "(\w+) ([^"]+) (HTTP/\d\.\d)" (\d+) (\d+) "([^"]*)" "([^"]*)" Time (\d+) Age "([^"]*)" "([^"]*)" "([^"]*)" (-|"[^"]*") "([^"]*)" "([^"]*)" (\w+)'
    
    # Línea de prueba
    test_line = 'Aug  8 03:33:33 www.gub.uy 186.48.242.68 [10.233.114.14] - "" [08/Aug/2025:03:33:33 -0300] "GET /direccion-general-impositiva/sites/direccion-general-impositiva/files/js/optimized/js_jiFsxh7G-xhq8-kNY5JOQzg7iGjjdKKHeJOnBhXRQ9Y.1Y_hXdDeLuHhX6RaroZ2rqX-4SwNhz4SI8p7lUR0ds0.js?t0epq7 HTTP/1.1" 200 905 "https://www.gub.uy/direccion-general-impositiva/personas?gad_source=1&gad_campaignid=22722788345&gbraid=0AAAABAVnRy_w87dsVPZAMrVSKf3B8vTrL&gclid=EAIaIQobChMIrKLS0Mv6jgMV8l9IAB0k1w5cEAAYASACEgLAxPD_BwE" "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1" Time 4213 Age "" "application/javascript" "" - "/PortalGubUy/wwwgubuy-TEPROD-443/wwwgubuy-TEPROD-443" "/PortalGubUy/wwwgubuy-TEPROD-443/Pool_dgi" TEPROD'
    
    print("🔍 Analizando regex con grupos nombrados...")
    named_match = re.match(named_regex, test_line)
    if named_match:
        print("✅ Grupos nombrados funcionan")
        groups = named_match.groupdict()
        print(f"📊 Grupos capturados: {len(groups)}")
        for key, value in list(groups.items())[:5]:  # Mostrar solo los primeros 5
            print(f"  {key}: {value}")
    else:
        print("❌ Grupos nombrados no funcionan")
    
    print(f"\n🔍 Analizando regex con grupos numerados...")
    numbered_match = re.match(numbered_regex, test_line)
    if numbered_match:
        print("✅ Grupos numerados funcionan")
        groups = numbered_match.groups()
        print(f"📊 Grupos capturados: {len(groups)}")
        for i, value in enumerate(groups[:5]):  # Mostrar solo los primeros 5
            print(f"  Grupo {i+1}: {value}")
        
        # Problema: hay grupos anidados que crean grupos extra
        print(f"\n⚠️  Problema detectado: {len(groups)} grupos capturados, pero esperamos 22")
        print("Los grupos anidados están creando capturas adicionales")
    else:
        print("❌ Grupos numerados no funcionan")
    
    # Crear regex corregida sin grupos anidados
    print(f"\n🔧 Creando regex corregida sin grupos anidados...")
    corrected_regex = r'(\w{3} \s+\d{1,2} \d{2}:\d{2}:\d{2}) ([^\s]+) ([^\s]+) \[([^\]]+)\] (-|"[^"]*") ("[^"]*") \[([^\]]+)\] "(\w+) ([^"]+) (HTTP/\d\.\d)" (\d+) (\d+) "([^"]*)" "([^"]*)" Time (\d+) Age "([^"]*)" "([^"]*)" "([^"]*)" (-|"[^"]*") "([^"]*)" "([^"]*)" (\w+)'
    
    corrected_match = re.match(corrected_regex, test_line)
    if corrected_match:
        print("✅ Regex corregida funciona")
        groups = corrected_match.groups()
        print(f"📊 Grupos capturados: {len(groups)}")
        
        # Mapear a nombres de campos
        field_names = [
            "timestamp_syslog", "hostname", "ip_cliente_externo", "ip_red_interna",
            "usuario_autenticado", "identidad", "timestamp_apache", "metodo",
            "recurso", "protocolo", "codigo_respuesta", "tamano_respuesta",
            "referer", "user_agent", "tiempo_respuesta_ms", "edad_cache",
            "content_type", "campo_reservado_1", "campo_reservado_2",
            "ambiente_origen", "ambiente_pool", "entorno_nodo"
        ]
        
        print(f"\n📋 Mapeo de campos:")
        for i, (field, value) in enumerate(zip(field_names, groups)):
            print(f"  {i+1:2d}. {field:20s}: {value}")
        
        return corrected_regex
    else:
        print("❌ Regex corregida no funciona")
        return None

if __name__ == "__main__":
    corrected_regex = analyze_regex()
    if corrected_regex:
        print(f"\n✅ Regex corregida para Kinesis Agent:")
        print(corrected_regex)
