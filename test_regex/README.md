# F5 Log Parser - Pruebas Locales

Este directorio contiene herramientas para probar y validar el parsing de logs F5 antes de implementarlo en el AWS Kinesis Agent.

## Archivos

- `f5_log_parser.py` - Script principal de parsing y pruebas
- `sample_f5_logs.txt` - Datos de prueba con logs F5 reales
- `README.md` - Este archivo de documentación

## Uso

### 1. Pruebas Rápidas con Datos de Ejemplo

```bash
# Ejecutar pruebas básicas
python3 f5_log_parser.py --test

# Pruebas con salida detallada
python3 f5_log_parser.py --test --verbose
```

### 2. Procesar Archivo de Logs

```bash
# Procesar archivo de muestra
python3 f5_log_parser.py --file sample_f5_logs.txt

# Con salida detallada
python3 f5_log_parser.py --file sample_f5_logs.txt --verbose
```

### 3. Generar Configuración para Kinesis Agent

```bash
# Generar configuración compatible con AWS Kinesis Agent
python3 f5_log_parser.py --config /opt/agesic-datalake/logs/f5_logs.log --stream agesic-dl-poc-data-stream
```

## Esquema de Datos

El parser convierte logs F5 al siguiente esquema JSON basado en Avro:

```json
{
  "timestamp_syslog": "Aug  8 03:33:33",
  "hostname": "www.gub.uy",
  "ip_cliente_externo": "186.48.242.68",
  "ip_red_interna": "10.233.114.14",
  "usuario_autenticado": null,
  "identidad": null,
  "timestamp_apache": "08/Aug/2025:03:33:33 -0300",
  "metodo": "GET",
  "recurso": "/direccion-general-impositiva/sites/...",
  "protocolo": "HTTP/1.1",
  "codigo_respuesta": 200,
  "tamano_respuesta": 905,
  "referer": "https://www.gub.uy/direccion-general-impositiva/personas...",
  "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5...)",
  "tiempo_respuesta_ms": 4213,
  "edad_cache": null,
  "content_type": "application/javascript",
  "campo_reservado_1": null,
  "campo_reservado_2": null,
  "campo_reservado_3": null,
  "ambiente_origen": "/PortalGubUy/wwwgubuy-TEPROD-443/wwwgubuy-TEPROD-443",
  "ambiente_pool": "/PortalGubUy/wwwgubuy-TEPROD-443/Pool_dgi",
  "entorno_nodo": "TEPROD"
}
```

## Compatibilidad con AWS Kinesis Agent

El script genera configuración compatible con la documentación oficial:
https://docs.aws.amazon.com/streams/latest/dev/writing-with-agents.html

### Diferencias Clave:

1. **Grupos Nombrados**: El parser local usa `(?P<name>)` para facilidad de desarrollo
2. **Kinesis Agent**: Usa grupos numerados `()` y `customFieldNames` para mapear campos
3. **Configuración**: Se genera automáticamente la configuración JSON compatible

### Configuración Generada:

```json
{
  "cloudwatch.emitMetrics": true,
  "flows": [
    {
      "filePattern": "/path/to/logs",
      "kinesisStream": "stream-name",
      "partitionKeyOption": "RANDOM",
      "dataProcessingOptions": [
        {
          "optionName": "LOGTOJSON",
          "logFormat": "COMMONAPACHELOG",
          "matchPattern": "regex_sin_grupos_nombrados",
          "customFieldNames": ["campo1", "campo2", ...]
        }
      ]
    }
  ]
}
```

## Validación

El parser incluye validación automática:

- ✅ **Regex Pattern**: Verifica que las líneas coincidan con el patrón
- ✅ **Tipos de Datos**: Convierte strings a int donde corresponde
- ✅ **Campos Nulos**: Maneja campos vacíos (`-`, `""`) correctamente
- ✅ **Esquema Avro**: Mapea campos según especificación
- ✅ **Estadísticas**: Reporta líneas válidas vs inválidas

## Próximos Pasos

1. **Validar Localmente**: Ejecutar todas las pruebas
2. **Generar Configuración**: Crear `agent.json` para Kinesis Agent
3. **Desplegar en EC2**: Aplicar configuración en instancia
4. **Monitorear**: Verificar métricas en CloudWatch
