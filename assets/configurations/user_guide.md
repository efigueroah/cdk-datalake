# AGESIC Data Lake PoC - Guía de Usuario

## Conexión a la Instancia EC2

### 1. Obtener Instance ID
```bash
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=agesic-dl-poc-log-generator" \
  --query "Reservations[].Instances[?State.Name=='running'].InstanceId" \
  --output text \
  --profile your-profile
```

### 2. Conectar via SSM Session Manager
```bash
aws ssm start-session --target i-1234567890abcdef0 --profile your-profile
```

## Uso del Generador de Logs

### Comandos Básicos

Una vez conectado a la instancia:

```bash
# Ir al directorio de trabajo
cd /opt/agesic-datalake

# Ver estado del sistema
./status.sh

# Iniciar generación interactiva
./start_generator.sh

# Editar configuración
./edit_config.sh
```

### Generación con Parámetros Específicos

```bash
# Generar exactamente 500 logs
python3 log_generator.py --max-logs 500

# Ejecutar por 30 minutos
python3 log_generator.py --duration 30

# Combinar ambos (se detiene al alcanzar cualquier límite)
python3 log_generator.py --max-logs 1000 --duration 60

# Usar archivo de configuración personalizado
python3 log_generator.py --config mi_config.json --max-logs 200
```

### Monitoreo y Estadísticas

```bash
# Ver estadísticas actuales
python3 log_generator.py --stats

# Ver logs del generador en tiempo real
tail -f generator.log

# Ver estado del sistema
./status.sh
```

## Configuración

### Archivo config.json

El archivo `/opt/agesic-datalake/config.json` contiene todos los parámetros:

```json
{
  "kinesis": {
    "stream_name": "agesic-dl-poc-data-stream",
    "partition_key": "log-simulator"
  },
  "generation": {
    "max_logs": 1000,           // Máximo número de logs
    "duration_minutes": 60,     // Duración máxima en minutos
    "interval_min_seconds": 1,  // Intervalo mínimo entre logs
    "interval_max_seconds": 5,  // Intervalo máximo entre logs
    "batch_size": 1             // Logs por batch (futuro)
  },
  "logging": {
    "level": "INFO",            // Nivel de logging
    "log_every_n_records": 100  // Mostrar progreso cada N logs
  },
  "simulation": {
    "error_rate_percent": 15,   // Porcentaje de logs de error
    "paths": [...],             // Rutas HTTP a simular
    "status_codes": {...}       // Códigos de estado y sus pesos
  }
}
```

### Parámetros Importantes

- **max_logs**: Número máximo de logs a generar
- **duration_minutes**: Tiempo máximo de ejecución
- **error_rate_percent**: Porcentaje de logs que serán errores (4xx, 5xx)
- **interval_*_seconds**: Rango de tiempo entre logs (simula tráfico real)

## Ejemplos de Uso

### Prueba Rápida (100 logs)
```bash
python3 log_generator.py --max-logs 100
```

### Simulación de Tráfico Ligero (30 minutos)
```bash
# Editar config.json para intervalos más largos (5-15 segundos)
./edit_config.sh
python3 log_generator.py --duration 30
```

### Simulación de Tráfico Intenso (1000 logs rápidos)
```bash
# Editar config.json para intervalos cortos (0.5-2 segundos)
./edit_config.sh
python3 log_generator.py --max-logs 1000
```

### Prueba de Errores
```bash
# Editar config.json para aumentar error_rate_percent a 50%
./edit_config.sh
python3 log_generator.py --max-logs 200
```

## Detener la Generación

- **Ctrl+C**: Detiene gracefully y muestra estadísticas finales
- El generador se detiene automáticamente al alcanzar max_logs o duration_minutes

## Verificar Datos en AWS

### CloudWatch Metrics
```bash
# Ver métricas de Kinesis
aws cloudwatch get-metric-statistics \
  --namespace AWS/Kinesis \
  --metric-name IncomingRecords \
  --dimensions Name=StreamName,Value=agesic-dl-poc-data-stream \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

### S3 Raw Data
```bash
# Listar archivos en S3 raw zone
aws s3 ls s3://agesic-dl-poc-raw-zone/demo/ --recursive
```

## Troubleshooting

### Problemas Comunes

1. **Error de conexión a Kinesis**
   - Verificar que la instancia tenga permisos IAM
   - Verificar que el stream existe: `aws kinesis describe-stream --stream-name agesic-dl-poc-data-stream`

2. **Configuración JSON inválida**
   - Usar `./edit_config.sh` que valida automáticamente
   - Restaurar backup: `cp config.json.backup.* config.json`

3. **Generador no envía datos**
   - Verificar logs: `tail -f generator.log`
   - Verificar conectividad AWS: `aws sts get-caller-identity`

### Logs del Sistema
```bash
# Logs de inicialización
sudo cat /var/log/agesic-setup.log

# Logs del generador
cat /opt/agesic-datalake/generator.log

# Logs del sistema
sudo journalctl -u agesic-log-generator.service
```

## Mejores Prácticas

1. **Empezar con pruebas pequeñas**: 50-100 logs para verificar funcionamiento
2. **Monitorear recursos**: Usar `./status.sh` para verificar memoria/disco
3. **Configurar intervalos realistas**: 1-5 segundos simula tráfico web normal
4. **Verificar datos en S3**: Confirmar que los datos llegan correctamente
5. **Usar Ctrl+C**: Siempre detener gracefully para ver estadísticas

## Soporte

Para problemas técnicos:
1. Revisar `/opt/agesic-datalake/generator.log`
2. Ejecutar `./status.sh` para diagnóstico
3. Verificar configuración con `cat config.json | jq '.'`
