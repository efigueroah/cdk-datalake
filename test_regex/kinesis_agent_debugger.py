#!/usr/bin/env python3
"""
Kinesis Agent Debugger - Simula el comportamiento del agente sin enviar datos
Permite validar regex y configuración rápidamente
"""

import re
import json
import sys
from typing import Dict, List, Optional, Any

class KinesisAgentDebugger:
    """Simula el comportamiento del Kinesis Agent para debugging"""
    
    def __init__(self, config_file: str):
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        self.flow = self.config['flows'][0]
        
        # Verificar si tiene procesamiento de datos
        if 'dataProcessingOptions' in self.flow:
            self.processing_options = self.flow['dataProcessingOptions'][0]
            self.has_processing = True
            self.regex_pattern = self.processing_options['matchPattern']
            self.field_names = self.processing_options['customFieldNames']
            
            try:
                self.compiled_regex = re.compile(self.regex_pattern)
                self.regex_valid = True
                self.regex_error = None
            except Exception as e:
                self.regex_valid = False
                self.regex_error = str(e)
        else:
            self.has_processing = False
    
    def debug_config(self):
        """Debuggea la configuración"""
        print("🔍 DEBUGGING DE CONFIGURACIÓN")
        print("=" * 50)
        
        print(f"📁 Archivo de logs: {self.flow['filePattern']}")
        print(f"🌊 Stream de Kinesis: {self.flow['kinesisStream']}")
        print(f"🔑 Partition Key: {self.flow['partitionKeyOption']}")
        
        if self.has_processing:
            print(f"⚙️  Procesamiento: {self.processing_options['optionName']}")
            print(f"📋 Formato: {self.processing_options['logFormat']}")
            print(f"🎯 Campos esperados: {len(self.field_names)}")
            
            if self.regex_valid:
                print("✅ Regex compilada exitosamente")
                print(f"📝 Patrón: {self.regex_pattern[:100]}...")
            else:
                print("❌ Error en regex:")
                print(f"   {self.regex_error}")
                return False
        else:
            print("📝 Modo: Texto plano (sin procesamiento)")
        
        return True
    
    def test_regex_with_sample(self, sample_lines: List[str]):
        """Prueba la regex con líneas de muestra"""
        if not self.has_processing:
            print("ℹ️  Modo texto plano - no hay regex que probar")
            return
        
        if not self.regex_valid:
            print("❌ No se puede probar - regex inválida")
            return
        
        print(f"\n🧪 PROBANDO REGEX CON {len(sample_lines)} LÍNEAS")
        print("=" * 50)
        
        for i, line in enumerate(sample_lines, 1):
            print(f"\n📝 Línea {i}:")
            print(f"   {line[:80]}...")
            
            match = self.compiled_regex.match(line.strip())
            if match:
                groups = match.groups()
                print(f"✅ Match exitoso - {len(groups)} grupos capturados")
                
                if len(groups) == len(self.field_names):
                    print("✅ Número de grupos coincide con campos esperados")
                    
                    # Mostrar primeros 5 campos
                    for j, (field, value) in enumerate(zip(self.field_names[:5], groups[:5])):
                        print(f"   {j+1:2d}. {field:20s}: {value}")
                    
                    if len(self.field_names) > 5:
                        print(f"   ... y {len(self.field_names) - 5} campos más")
                else:
                    print(f"⚠️  Grupos capturados ({len(groups)}) != campos esperados ({len(self.field_names)})")
            else:
                print("❌ No match - la línea no coincide con el patrón")
    
    def simulate_processing(self, log_file: str, max_lines: int = 10):
        """Simula el procesamiento completo de un archivo"""
        print(f"\n🔄 SIMULANDO PROCESAMIENTO DE {log_file}")
        print("=" * 50)
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()][:max_lines]
            
            print(f"📊 Procesando {len(lines)} líneas...")
            
            if not self.has_processing:
                print("📝 Modo texto plano:")
                for i, line in enumerate(lines, 1):
                    print(f"   Línea {i}: {len(line)} caracteres -> Enviado como texto")
                print(f"✅ {len(lines)} registros serían enviados como texto plano")
                return
            
            if not self.regex_valid:
                print("❌ No se puede procesar - regex inválida")
                return
            
            matched = 0
            skipped = 0
            
            for i, line in enumerate(lines, 1):
                match = self.compiled_regex.match(line)
                if match:
                    matched += 1
                    groups = match.groups()
                    if len(groups) == len(self.field_names):
                        print(f"✅ Línea {i}: Match exitoso -> JSON con {len(self.field_names)} campos")
                    else:
                        print(f"⚠️  Línea {i}: Match parcial -> {len(groups)} grupos vs {len(self.field_names)} esperados")
                else:
                    skipped += 1
                    print(f"❌ Línea {i}: No match -> Registro saltado")
            
            print(f"\n📊 RESUMEN DE SIMULACIÓN:")
            print(f"   ✅ Procesados exitosamente: {matched}")
            print(f"   ❌ Saltados: {skipped}")
            print(f"   📈 Tasa de éxito: {(matched/len(lines)*100):.1f}%")
            
            if matched == len(lines):
                print("🎉 ¡CONFIGURACIÓN PERFECTA! Todos los registros serían procesados")
            elif matched > 0:
                print("⚠️  CONFIGURACIÓN PARCIAL - Algunos registros se procesarían")
            else:
                print("💥 CONFIGURACIÓN FALLIDA - Ningún registro se procesaría")
        
        except FileNotFoundError:
            print(f"❌ Archivo no encontrado: {log_file}")
        except Exception as e:
            print(f"❌ Error: {str(e)}")

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 kinesis_agent_debugger.py <config_file> [log_file]")
        sys.exit(1)
    
    config_file = sys.argv[1]
    log_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        debugger = KinesisAgentDebugger(config_file)
        
        # Debug de configuración
        if not debugger.debug_config():
            sys.exit(1)
        
        # Prueba con líneas de muestra
        sample_lines = [
            'Aug  8 03:33:33 www.gub.uy 186.48.242.68 [10.233.114.14] - "" [08/Aug/2025:03:33:33 -0300] "GET /direccion-general-impositiva/sites/direccion-general-impositiva/files/js/optimized/js_jiFsxh7G-xhq8-kNY5JOQzg7iGjjdKKHeJOnBhXRQ9Y.1Y_hXdDeLuHhX6RaroZ2rqX-4SwNhz4SI8p7lUR0ds0.js?t0epq7 HTTP/1.1" 200 905 "https://www.gub.uy/direccion-general-impositiva/personas?gad_source=1&gad_campaignid=22722788345&gbraid=0AAAABAVnRy_w87dsVPZAMrVSKf3B8vTrL&gclid=EAIaIQobChMIrKLS0Mv6jgMV8l9IAB0k1w5cEAAYASACEgLAxPD_BwE" "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1" Time 4213 Age "" "application/javascript" "" - "/PortalGubUy/wwwgubuy-TEPROD-443/wwwgubuy-TEPROD-443" "/PortalGubUy/wwwgubuy-TEPROD-443/Pool_dgi" TEPROD'
        ]
        
        debugger.test_regex_with_sample(sample_lines)
        
        # Simulación con archivo real si se proporciona
        if log_file:
            debugger.simulate_processing(log_file)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
