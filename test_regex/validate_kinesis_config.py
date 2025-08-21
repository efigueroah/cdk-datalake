#!/usr/bin/env python3
"""
Validador de configuración de Kinesis Agent
Simula el comportamiento del agente para validar que la regex funciona correctamente
"""

import re
import json
import sys
from typing import Dict, List, Optional, Any


class KinesisAgentValidator:
    """Simula el comportamiento del AWS Kinesis Agent para validar configuración"""
    
    def __init__(self, config_file: str):
        """
        Inicializa el validador con un archivo de configuración
        
        Args:
            config_file: Ruta al archivo de configuración JSON
        """
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        # Extraer configuración del primer flow
        self.flow = self.config['flows'][0]
        self.processing_options = self.flow['dataProcessingOptions'][0]
        
        # Compilar regex (sin grupos nombrados, como usa Kinesis Agent)
        self.regex_pattern = self.processing_options['matchPattern']
        self.compiled_regex = re.compile(self.regex_pattern)
        
        # Nombres de campos personalizados
        self.field_names = self.processing_options['customFieldNames']
    
    def process_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Procesa una línea como lo haría Kinesis Agent
        
        Args:
            line: Línea de log a procesar
            
        Returns:
            Diccionario JSON o None si no coincide
        """
        line = line.strip()
        if not line:
            return None
        
        match = self.compiled_regex.match(line)
        if not match:
            return None
        
        # Extraer grupos numerados (como hace Kinesis Agent)
        groups = match.groups()
        
        # Crear diccionario usando customFieldNames
        result = {}
        for i, field_name in enumerate(self.field_names):
            if i < len(groups):
                value = groups[i]
                # Limpiar valores como lo hace Kinesis Agent
                if value == '-' or value == '""':
                    result[field_name] = None
                elif value and value.startswith('"') and value.endswith('"'):
                    result[field_name] = value[1:-1]  # Remover comillas
                else:
                    result[field_name] = value
            else:
                result[field_name] = None
        
        return result
    
    def validate_with_test_data(self, test_lines: List[str]) -> Dict[str, Any]:
        """
        Valida la configuración con datos de prueba
        
        Args:
            test_lines: Lista de líneas de prueba
            
        Returns:
            Diccionario con resultados de validación
        """
        results = {
            "total_lines": len(test_lines),
            "valid_lines": 0,
            "invalid_lines": 0,
            "processed_records": [],
            "errors": []
        }
        
        for i, line in enumerate(test_lines, 1):
            processed = self.process_line(line)
            if processed:
                results["valid_lines"] += 1
                results["processed_records"].append({
                    "line_number": i,
                    "data": processed
                })
            else:
                results["invalid_lines"] += 1
                results["errors"].append({
                    "line_number": i,
                    "line": line[:100] + "..." if len(line) > 100 else line,
                    "error": "No match with Kinesis Agent regex pattern"
                })
        
        return results
    
    def compare_with_named_groups(self, test_lines: List[str], named_parser) -> Dict[str, Any]:
        """
        Compara resultados entre regex con grupos nombrados y grupos numerados
        
        Args:
            test_lines: Líneas de prueba
            named_parser: Parser con grupos nombrados
            
        Returns:
            Diccionario con comparación
        """
        comparison = {
            "total_lines": len(test_lines),
            "matches": {
                "both": 0,
                "named_only": 0,
                "numbered_only": 0,
                "neither": 0
            },
            "field_differences": []
        }
        
        for i, line in enumerate(test_lines, 1):
            named_result = named_parser.parse_line(line)
            numbered_result = self.process_line(line)
            
            if named_result and numbered_result:
                comparison["matches"]["both"] += 1
                
                # Comparar campos
                differences = []
                for field in self.field_names:
                    named_val = named_result.get(field)
                    numbered_val = numbered_result.get(field)
                    if named_val != numbered_val:
                        differences.append({
                            "field": field,
                            "named_value": named_val,
                            "numbered_value": numbered_val
                        })
                
                if differences:
                    comparison["field_differences"].append({
                        "line_number": i,
                        "differences": differences
                    })
            
            elif named_result and not numbered_result:
                comparison["matches"]["named_only"] += 1
            elif not named_result and numbered_result:
                comparison["matches"]["numbered_only"] += 1
            else:
                comparison["matches"]["neither"] += 1
        
        return comparison


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 validate_kinesis_config.py <config_file>")
        sys.exit(1)
    
    config_file = sys.argv[1]
    
    try:
        validator = KinesisAgentValidator(config_file)
        print(f"✅ Configuración cargada: {config_file}")
        print(f"📋 Regex pattern: {validator.regex_pattern}")
        print(f"🏷️  Campos: {len(validator.field_names)} definidos")
        
        # Datos de prueba
        test_lines = [
            'Aug  8 03:33:33 www.gub.uy 186.48.242.68 [10.233.114.14] - "" [08/Aug/2025:03:33:33 -0300] "GET /direccion-general-impositiva/sites/direccion-general-impositiva/files/js/optimized/js_jiFsxh7G-xhq8-kNY5JOQzg7iGjjdKKHeJOnBhXRQ9Y.1Y_hXdDeLuHhX6RaroZ2rqX-4SwNhz4SI8p7lUR0ds0.js?t0epq7 HTTP/1.1" 200 905 "https://www.gub.uy/direccion-general-impositiva/personas?gad_source=1&gad_campaignid=22722788345&gbraid=0AAAABAVnRy_w87dsVPZAMrVSKf3B8vTrL&gclid=EAIaIQobChMIrKLS0Mv6jgMV8l9IAB0k1w5cEAAYASACEgLAxPD_BwE" "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1" Time 4213 Age "" "application/javascript" "" - "/PortalGubUy/wwwgubuy-TEPROD-443/wwwgubuy-TEPROD-443" "/PortalGubUy/wwwgubuy-TEPROD-443/Pool_dgi" TEPROD',
            'Aug  8 03:33:33 www.gub.uy 186.48.242.68 [10.233.114.14] - "" [08/Aug/2025:03:33:33 -0300] "GET /direccion-general-impositiva/sites/direccion-general-impositiva/files/js/optimized/js_I8INAQ0miW75vWTPYFMGmVDMuTV8eIPjpET3V0K8Nwg.eCPSVfCVtWzfNYs1RIjbVopFtVCVMGGx7gZf6jB75iU.js?t0epq7 HTTP/1.1" 200 849 "https://www.gub.uy/direccion-general-impositiva/personas?gad_source=1&gad_campaignid=22722788345&gbraid=0AAAABAVnRy_w87dsVPZAMrVSKf3B8vTrL&gclid=EAIaIQobChMIrKLS0Mv6jgMV8l9IAB0k1w5cEAAYASACEgLAxPD_BwE" "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1" Time 6723 Age "" "application/javascript" "" - "/PortalGubUy/wwwgubuy-TEPROD-443/wwwgubuy-TEPROD-443" "/PortalGubUy/wwwgubuy-TEPROD-443/Pool_dgi" TEPROD'
        ]
        
        print(f"\n🧪 Validando con {len(test_lines)} líneas de prueba...")
        results = validator.validate_with_test_data(test_lines)
        
        print(f"\n📊 Resultados de validación:")
        print(f"  Total líneas: {results['total_lines']}")
        print(f"  Válidas: {results['valid_lines']}")
        print(f"  Inválidas: {results['invalid_lines']}")
        
        if results['valid_lines'] > 0:
            print(f"\n✅ Primer registro procesado:")
            first_record = results['processed_records'][0]['data']
            print(json.dumps(first_record, indent=2, ensure_ascii=False))
        
        if results['errors']:
            print(f"\n❌ Errores encontrados:")
            for error in results['errors']:
                print(f"  Línea {error['line_number']}: {error['error']}")
        
        # Comparar con parser de grupos nombrados si está disponible
        try:
            sys.path.append('.')
            from f5_log_parser import F5LogParser
            
            named_parser = F5LogParser()
            comparison = validator.compare_with_named_groups(test_lines, named_parser)
            
            print(f"\n🔍 Comparación con parser de grupos nombrados:")
            print(f"  Ambos coinciden: {comparison['matches']['both']}")
            print(f"  Solo grupos nombrados: {comparison['matches']['named_only']}")
            print(f"  Solo grupos numerados: {comparison['matches']['numbered_only']}")
            print(f"  Ninguno coincide: {comparison['matches']['neither']}")
            
            if comparison['field_differences']:
                print(f"  ⚠️  Diferencias en campos encontradas: {len(comparison['field_differences'])}")
                for diff in comparison['field_differences'][:2]:  # Mostrar solo las primeras 2
                    print(f"    Línea {diff['line_number']}: {len(diff['differences'])} campos diferentes")
            else:
                print(f"  ✅ No hay diferencias en los campos")
        
        except ImportError:
            print(f"\n⚠️  No se pudo importar F5LogParser para comparación")
        
        print(f"\n🎯 Configuración lista para Kinesis Agent!")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
