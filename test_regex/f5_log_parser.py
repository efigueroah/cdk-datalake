#!/usr/bin/env python3
"""
F5 Log Parser - Pruebas locales para validar regex y transformación JSON
Compatible con AWS Kinesis Agent configuration

Basado en la documentación:
https://docs.aws.amazon.com/streams/latest/dev/writing-with-agents.html
"""

import re
import json
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any
import argparse


class F5LogParser:
    """Parser para logs F5 con formato TEPROD"""
    
    def __init__(self):
        # Expresión regular basada en la especificación proporcionada
        self.regex_pattern = r'(?P<timestamp_syslog>\w{3} \s+\d{1,2} \d{2}:\d{2}:\d{2}) (?P<hostname>[^\s]+) (?P<ip_cliente_externo>[^\s]+) \[(?P<ip_backend_interno>[^\]]+)\] (?P<usuario_autenticado>-|"[^"]*") (?P<identidad>"[^"]*") \[(?P<timestamp_rp>[^\]]+)\] "(?P<metodo>\w+) (?P<request>[^"]+) (?P<protocolo>HTTP/\d\.\d)" (?P<codigo_respuesta>\d+) (?P<tamano_respuesta>\d+) "(?P<referer>[^"]*)" "(?P<user_agent>[^"]*)" Time (?P<tiempo_respuesta_ms>\d+) Age "(?P<edad_cache>[^"]*)" "(?P<content_type>[^"]*)" "(?P<jsession_id>[^"]*)" (?P<campo_reservado_2>-|"[^"]*") "(?P<f5_virtualserver>[^"]*)" "(?P<f5_pool>[^"]*)" (?P<f5_bigip_name>\w+)'
        
        self.compiled_regex = re.compile(self.regex_pattern)
        
        # Esquema Avro para validación de campos
        self.avro_schema = {
            "type": "record",
            "name": "LogHttpTEPROD",
            "namespace": "uy.gub.logs.teprod",
            "doc": "Esquema para interpretar líneas de log HTTP extendido del entorno TEPROD",
            "fields": [
                {"name": "timestamp_syslog", "type": "string", "doc": "Timestamp del sistema (syslog)"},
                {"name": "hostname", "type": "string", "doc": "Nombre del host que genera el log"},
                {"name": "ip_cliente_externo", "type": "string", "doc": "IP pública del cliente que realiza la solicitud"},
                {"name": "ip_red_interna", "type": "string", "doc": "IP privada del backend (entre corchetes)"},
                {"name": "usuario_autenticado", "type": ["null", "string"], "default": None, "doc": "Usuario autenticado, si aplica"},
                {"name": "identidad", "type": ["null", "string"], "default": None, "doc": "Campo de identidad o identd"},
                {"name": "timestamp_apache", "type": "string", "doc": "Timestamp del momento exacto de la solicitud HTTP"},
                {"name": "metodo", "type": "string", "doc": "Método HTTP (GET, POST...)"},
                {"name": "recurso", "type": "string", "doc": "Ruta del recurso solicitado"},
                {"name": "protocolo", "type": "string", "doc": "Versión del protocolo HTTP"},
                {"name": "codigo_respuesta", "type": "int", "doc": "Código de estado HTTP (200, 404, etc.)"},
                {"name": "tamano_respuesta", "type": "int", "doc": "Tamaño en bytes del recurso servido"},
                {"name": "referer", "type": ["null", "string"], "default": None, "doc": "URL de origen de la solicitud"},
                {"name": "user_agent", "type": "string", "doc": "Cadena identificadora del navegador/dispositivo"},
                {"name": "tiempo_respuesta_ms", "type": "int", "doc": "Tiempo de respuesta en milisegundos"},
                {"name": "edad_cache", "type": ["null", "string"], "default": None, "doc": "Edad del recurso en caché (TTL), si aplica"},
                {"name": "content_type", "type": ["null", "string"], "default": None, "doc": "Tipo MIME del recurso (image/png, font/woff2, etc.)"},
                {"name": "campo_reservado_1", "type": ["null", "string"], "default": None},
                {"name": "campo_reservado_2", "type": ["null", "string"], "default": None},
                {"name": "campo_reservado_3", "type": ["null", "string"], "default": None},
                {"name": "ambiente_origen", "type": "string", "doc": "Host virtual o contexto del ambiente"},
                {"name": "ambiente_pool", "type": "string", "doc": "Pool de servicio que gestionó la solicitud"},
                {"name": "entorno_nodo", "type": "string", "doc": "Nombre del nodo/entorno (ej. TEPROD)"}
            ]
        }
    
    def parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parsea una línea de log F5 y retorna un diccionario JSON
        
        Args:
            line: Línea de log a procesar
            
        Returns:
            Diccionario con campos parseados o None si no coincide
        """
        line = line.strip()
        if not line:
            return None
            
        match = self.compiled_regex.match(line)
        if not match:
            return None
        
        # Extraer grupos nombrados
        groups = match.groupdict()
        
        # Mapear campos del regex a esquema Avro
        parsed_data = {
            "timestamp_syslog": groups.get("timestamp_syslog", ""),
            "hostname": groups.get("hostname", ""),
            "ip_cliente_externo": groups.get("ip_cliente_externo", ""),
            "ip_red_interna": groups.get("ip_backend_interno", ""),
            "usuario_autenticado": self._clean_field(groups.get("usuario_autenticado")),
            "identidad": self._clean_field(groups.get("identidad")),
            "timestamp_apache": groups.get("timestamp_rp", ""),
            "metodo": groups.get("metodo", ""),
            "recurso": groups.get("request", ""),
            "protocolo": groups.get("protocolo", ""),
            "codigo_respuesta": self._safe_int(groups.get("codigo_respuesta")),
            "tamano_respuesta": self._safe_int(groups.get("tamano_respuesta")),
            "referer": self._clean_field(groups.get("referer")),
            "user_agent": groups.get("user_agent", ""),
            "tiempo_respuesta_ms": self._safe_int(groups.get("tiempo_respuesta_ms")),
            "edad_cache": self._clean_field(groups.get("edad_cache")),
            "content_type": self._clean_field(groups.get("content_type")),
            "campo_reservado_1": self._clean_field(groups.get("jsession_id")),
            "campo_reservado_2": self._clean_field(groups.get("campo_reservado_2")),
            "campo_reservado_3": None,
            "ambiente_origen": groups.get("f5_virtualserver", ""),
            "ambiente_pool": groups.get("f5_pool", ""),
            "entorno_nodo": groups.get("f5_bigip_name", "")
        }
        
        return parsed_data
    
    def _clean_field(self, value: Optional[str]) -> Optional[str]:
        """Limpia campos eliminando comillas y convirtiendo '-' a None"""
        if not value or value == "-" or value == '""':
            return None
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        return value
    
    def _safe_int(self, value: Optional[str]) -> int:
        """Convierte string a int de forma segura"""
        if not value:
            return 0
        try:
            return int(value)
        except ValueError:
            return 0
    
    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """
        Procesa un archivo completo de logs
        
        Args:
            file_path: Ruta al archivo de logs
            
        Returns:
            Diccionario con estadísticas y resultados
        """
        results = {
            "total_lines": 0,
            "valid_lines": 0,
            "invalid_lines": 0,
            "parsed_records": [],
            "errors": []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    results["total_lines"] += 1
                    
                    parsed = self.parse_line(line)
                    if parsed:
                        results["valid_lines"] += 1
                        results["parsed_records"].append({
                            "line_number": line_num,
                            "data": parsed
                        })
                    else:
                        results["invalid_lines"] += 1
                        results["errors"].append({
                            "line_number": line_num,
                            "line": line.strip()[:100] + "..." if len(line.strip()) > 100 else line.strip(),
                            "error": "No match with regex pattern"
                        })
        
        except FileNotFoundError:
            results["errors"].append({"error": f"File not found: {file_path}"})
        except Exception as e:
            results["errors"].append({"error": f"Error reading file: {str(e)}"})
        
        return results
    
    def generate_kinesis_agent_config(self, log_file_path: str, stream_name: str) -> Dict[str, Any]:
        """
        Genera configuración compatible con AWS Kinesis Agent
        
        Args:
            log_file_path: Ruta al archivo de logs
            stream_name: Nombre del stream de Kinesis
            
        Returns:
            Configuración JSON para Kinesis Agent
        """
        # Regex para Kinesis Agent (sin grupos nombrados y sin grupos anidados)
        # AWS Kinesis Agent no soporta grupos nombrados (?P<name>)
        # Cada grupo captura exactamente lo que necesitamos en el orden correcto
        kinesis_regex = r'(\w{3} \s+\d{1,2} \d{2}:\d{2}:\d{2}) ([^\s]+) ([^\s]+) \[([^\]]+)\] (-|"[^"]*") ("[^"]*") \[([^\]]+)\] "(\w+) ([^"]+) (HTTP/\d\.\d)" (\d+) (\d+) "([^"]*)" "([^"]*)" Time (\d+) Age "([^"]*)" "([^"]*)" "([^"]*)" (-|"[^"]*") "([^"]*)" "([^"]*)" (\w+)'
        
        config = {
            "cloudwatch.emitMetrics": True,
            "cloudwatch.endpoint": "https://monitoring.us-east-1.amazonaws.com",
            "firehose.endpoint": "https://firehose.us-east-1.amazonaws.com",
            "flows": [
                {
                    "filePattern": log_file_path,
                    "kinesisStream": stream_name,
                    "partitionKeyOption": "RANDOM",
                    "dataProcessingOptions": [
                        {
                            "optionName": "LOGTOJSON",
                            "logFormat": "COMMONAPACHELOG",
                            "matchPattern": kinesis_regex,
                            "customFieldNames": [
                                "timestamp_syslog",
                                "hostname", 
                                "ip_cliente_externo",
                                "ip_red_interna",
                                "usuario_autenticado",
                                "identidad",
                                "timestamp_apache",
                                "metodo",
                                "recurso",
                                "protocolo",
                                "codigo_respuesta",
                                "tamano_respuesta",
                                "referer",
                                "user_agent",
                                "tiempo_respuesta_ms",
                                "edad_cache",
                                "content_type",
                                "campo_reservado_1",
                                "campo_reservado_2",
                                "ambiente_origen",
                                "ambiente_pool",
                                "entorno_nodo"
                            ]
                        }
                    ]
                }
            ]
        }
        
        return config


def main():
    parser = argparse.ArgumentParser(description="F5 Log Parser - Pruebas locales")
    parser.add_argument("--file", "-f", help="Archivo de logs a procesar")
    parser.add_argument("--test", "-t", action="store_true", help="Ejecutar pruebas con datos de ejemplo")
    parser.add_argument("--config", "-c", help="Generar configuración de Kinesis Agent")
    parser.add_argument("--stream", "-s", default="agesic-dl-poc-data-stream", help="Nombre del stream de Kinesis")
    parser.add_argument("--verbose", "-v", action="store_true", help="Salida detallada")
    
    args = parser.parse_args()
    
    f5_parser = F5LogParser()
    
    if args.test:
        print("🧪 Ejecutando pruebas con datos de ejemplo...")
        test_lines = [
            'Aug  8 03:33:33 www.gub.uy 186.48.242.68 [10.233.114.14] - "" [08/Aug/2025:03:33:33 -0300] "GET /direccion-general-impositiva/sites/direccion-general-impositiva/files/js/optimized/js_jiFsxh7G-xhq8-kNY5JOQzg7iGjjdKKHeJOnBhXRQ9Y.1Y_hXdDeLuHhX6RaroZ2rqX-4SwNhz4SI8p7lUR0ds0.js?t0epq7 HTTP/1.1" 200 905 "https://www.gub.uy/direccion-general-impositiva/personas?gad_source=1&gad_campaignid=22722788345&gbraid=0AAAABAVnRy_w87dsVPZAMrVSKf3B8vTrL&gclid=EAIaIQobChMIrKLS0Mv6jgMV8l9IAB0k1w5cEAAYASACEgLAxPD_BwE" "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1" Time 4213 Age "" "application/javascript" "" - "/PortalGubUy/wwwgubuy-TEPROD-443/wwwgubuy-TEPROD-443" "/PortalGubUy/wwwgubuy-TEPROD-443/Pool_dgi" TEPROD',
            'Aug  8 03:33:33 www.gub.uy 186.48.242.68 [10.233.114.14] - "" [08/Aug/2025:03:33:33 -0300] "GET /direccion-general-impositiva/sites/direccion-general-impositiva/files/js/optimized/js_I8INAQ0miW75vWTPYFMGmVDMuTV8eIPjpET3V0K8Nwg.eCPSVfCVtWzfNYs1RIjbVopFtVCVMGGx7gZf6jB75iU.js?t0epq7 HTTP/1.1" 200 849 "https://www.gub.uy/direccion-general-impositiva/personas?gad_source=1&gad_campaignid=22722788345&gbraid=0AAAABAVnRy_w87dsVPZAMrVSKf3B8vTrL&gclid=EAIaIQobChMIrKLS0Mv6jgMV8l9IAB0k1w5cEAAYASACEgLAxPD_BwE" "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1" Time 6723 Age "" "application/javascript" "" - "/PortalGubUy/wwwgubuy-TEPROD-443/wwwgubuy-TEPROD-443" "/PortalGubUy/wwwgubuy-TEPROD-443/Pool_dgi" TEPROD'
        ]
        
        valid_count = 0
        for i, line in enumerate(test_lines, 1):
            print(f"\n📝 Procesando línea {i}:")
            parsed = f5_parser.parse_line(line)
            if parsed:
                valid_count += 1
                print("✅ Válida")
                if args.verbose:
                    print(json.dumps(parsed, indent=2, ensure_ascii=False))
            else:
                print("❌ Inválida")
        
        print(f"\n📊 Resumen: Válidos: {valid_count} | Rechazados: {len(test_lines) - valid_count}")
    
    elif args.file:
        print(f"📁 Procesando archivo: {args.file}")
        results = f5_parser.parse_file(args.file)
        
        print(f"📊 Estadísticas:")
        print(f"  Total líneas: {results['total_lines']}")
        print(f"  Válidas: {results['valid_lines']}")
        print(f"  Inválidas: {results['invalid_lines']}")
        
        if results['errors'] and args.verbose:
            print(f"\n❌ Errores encontrados:")
            for error in results['errors'][:5]:  # Mostrar solo los primeros 5
                print(f"  Línea {error.get('line_number', 'N/A')}: {error['error']}")
        
        if args.verbose and results['parsed_records']:
            print(f"\n📝 Primeros registros parseados:")
            for record in results['parsed_records'][:2]:
                print(f"Línea {record['line_number']}:")
                print(json.dumps(record['data'], indent=2, ensure_ascii=False))
    
    elif args.config:
        print(f"⚙️  Generando configuración de Kinesis Agent...")
        config = f5_parser.generate_kinesis_agent_config(args.config, args.stream)
        
        config_file = "kinesis_agent_config.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ Configuración guardada en: {config_file}")
        print(f"🔧 Para usar con Kinesis Agent:")
        print(f"   sudo cp {config_file} /etc/aws-kinesis/agent.json")
        print(f"   sudo systemctl restart aws-kinesis-agent")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
