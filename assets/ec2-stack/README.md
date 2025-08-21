# AGESIC Data Lake - Enhanced EC2 Stack

## 🚀 Resumen de Mejoras

El **Enhanced EC2 Stack** resuelve las limitaciones del stack original mediante una arquitectura innovadora que supera las restricciones de UserData de AWS (16KB) y habilita el soporte completo para **dual agents**.

### ✅ Problemas Resueltos

| Problema Original | Solución Implementada | Beneficio |
|------------------|----------------------|-----------|
| **UserData 16KB limit** | SSM Documents para configuración | 96.58% reducción en uso de UserData |
| **Solo Python processor** | Dual agents: Kinesis Agent + Fluentd | Redundancia y flexibilidad |
| **Configuración manual** | Instalación automática vía Lambda | Despliegue hands-off |
| **Código disperso** | Estructura de assets organizada | Mantenibilidad mejorada |
| **Monitoreo limitado** | Logging y métricas comprehensivas | Observabilidad completa |

## 📊 Métricas de Optimización

### UserData Size Reduction
- **Antes**: 12,934 bytes (78.94% del límite de 16KB)
- **Después**: 442 bytes (2.69% del límite de 16KB)
- **Reducción**: 96.58% - Permite espacio para futuras expansiones

### Arquitectura Mejorada
- **Instance Type**: Upgrade de t3.micro → t3.small (dual agents support)
- **Spot Price**: Ajustado de $0.005 → $0.01 (mejor disponibilidad)
- **Automation**: 100% automatizado via EventBridge + Lambda

## 🏗️ Arquitectura del Stack Mejorado

```
┌─────────────────────────────────────────────────────────────┐
│                    Enhanced EC2 Stack                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐    ┌──────────────────────────────────┐ │
│  │   UserData      │    │        SSM Documents             │ │
│  │   (442 bytes)   │    │                                  │ │
│  │                 │    │  ┌─────────────────────────────┐ │ │
│  │ • Basic setup   │    │  │   complete-setup.yaml      │ │ │
│  │ • AWS CLI       │    │  │                             │ │ │
│  │ • Region config │    │  │ • Base environment         │ │ │
│  └─────────────────┘    │  │ • Python F5 processor      │ │ │
│                         │  │ • Management scripts       │ │ │
│  ┌─────────────────┐    │  │ • SystemD services         │ │ │
│  │   EventBridge   │    │  └─────────────────────────────┘ │ │
│  │                 │    │                                  │ │
│  │ • Launch events │    │  ┌─────────────────────────────┐ │ │
│  │ • Auto trigger  │    │  │   install-agents.yaml      │ │ │
│  └─────────────────┘    │  │                             │ │ │
│           │              │  │ • Kinesis Agent install    │ │ │
│           ▼              │  │ • Fluentd install          │ │ │
│  ┌─────────────────┐    │  │ • Agent management         │ │ │
│  │ Install Lambda  │    │  └─────────────────────────────┘ │ │
│  │                 │    └──────────────────────────────────┘ │
│  │ • Auto install  │                                         │
│  │ • SSM execution │    ┌──────────────────────────────────┐ │
│  │ • Error handling│    │           Assets Structure       │ │
│  └─────────────────┘    │                                  │ │
│                         │  scripts/                        │ │
│                         │  ├── f5_log_processor.py         │ │
│                         │  ├── manage_agents.sh            │ │
│                         │  ├── download_and_process.sh     │ │
│                         │  └── status.sh                   │ │
│                         │                                  │ │
│                         │  lambda/                         │ │
│                         │  └── install_agents.py           │ │
│                         │                                  │ │
│                         │  ssm-documents/                  │ │
│                         │  ├── complete-setup.yaml        │ │
│                         │  └── install-agents.yaml        │ │
│                         └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Estructura de Assets

```
assets/ec2-stack/
├── scripts/                          # Scripts de gestión y procesamiento
│   ├── f5_log_processor.py          # Procesador Python con 25+ campos F5
│   ├── manage_agents.sh             # Gestión de agentes con colores y logs
│   ├── download_and_process.sh      # Descarga y procesamiento automatizado
│   ├── status.sh                    # Estado del sistema mejorado
│   ├── deploy_enhanced_stack.sh     # Script de despliegue automatizado
│   └── validate_enhanced_stack.py   # Validación comprehensiva del stack
├── lambda/                          # Código Lambda para automatización
│   └── install_agents.py           # Instalación automática de agentes
├── ssm-documents/                   # Documentos SSM para configuración
│   ├── complete-setup.yaml         # Setup completo del F5 Bridge
│   └── install-agents.yaml         # Instalación de dual agents
└── cdk-context-enhanced.json       # Configuración CDK mejorada
```

## 🔧 Componentes del Stack

### 1. SSM Documents

#### complete-setup.yaml
- **Propósito**: Configuración completa del F5 Bridge
- **Incluye**:
  - Configuración del entorno base
  - Instalación del procesador Python F5
  - Scripts de gestión
  - Servicios SystemD
- **Timeout**: 600 segundos
- **Parámetros**: kinesisStreamName, sourceBucket, sourceFile

#### install-agents.yaml
- **Propósito**: Instalación de dual agents
- **Agentes soportados**:
  - Kinesis Agent (Java-based)
  - Fluentd (td-agent)
  - Both (instalación dual)
- **Configuración automática**: Streams, buffers, formatos

### 2. Lambda Function (Auto-Installer)

```python
# Características principales:
- Runtime: Python 3.9
- Timeout: 5 minutos
- Trigger: EventBridge (instance launch)
- Funciones:
  - Detección automática de nuevas instancias
  - Ejecución de SSM Documents
  - Manejo de errores y logging
  - Instalación secuencial (setup → agents)
```

### 3. Enhanced Scripts

#### f5_log_processor.py
- **Regex Pattern**: 25+ campos específicos F5
- **Funcionalidades**:
  - Descarga directa desde S3
  - Parsing avanzado de logs F5
  - Envío directo a Kinesis
  - Métricas y estadísticas
  - Manejo de errores robusto

#### manage_agents.sh
- **Gestión completa** de los 3 agentes
- **Comandos**: start, stop, restart, status, logs
- **Características**:
  - Output con colores
  - Logging detallado
  - Validación de estados
  - Instrucciones de instalación

### 4. Automated Deployment

#### deploy_enhanced_stack.sh
- **Funciones**:
  - Validación de prerequisitos
  - Actualización automática de app.py
  - Despliegue del stack
  - Validación post-despliegue
  - Testing de SSM Documents

## 🚀 Guía de Despliegue

### 1. Preparación

```bash
cd /home/efigueroa/Proyectos/AWS-QDeveloper/proyectos/AgesicDataLakes/agesicdatalake

# Hacer ejecutables los scripts
chmod +x assets/ec2-stack/scripts/*.sh
chmod +x assets/ec2-stack/scripts/*.py
```

### 2. Despliegue Automatizado

```bash
# Opción 1: Despliegue completo automatizado
./assets/ec2-stack/scripts/deploy_enhanced_stack.sh deploy

# Opción 2: Solo actualizar app.py
./assets/ec2-stack/scripts/deploy_enhanced_stack.sh update-app

# Opción 3: Verificar estado
./assets/ec2-stack/scripts/deploy_enhanced_stack.sh status
```

### 3. Despliegue Manual (CDK)

```bash
# Instalar PyYAML para SSM documents
pip install PyYAML

# Sintetizar y desplegar
cdk synth --profile agesicUruguay-699019841929
cdk deploy agesic-dl-poc-ec2-enhanced --profile agesicUruguay-699019841929
```

## 🔍 Validación y Testing

### 1. Validación Automática

```bash
# Validación completa del stack
python3 assets/ec2-stack/scripts/validate_enhanced_stack.py \
  --profile agesicUruguay-699019841929 \
  --output validation_report.json

# Validación con output detallado
python3 assets/ec2-stack/scripts/validate_enhanced_stack.py --verbose
```

### 2. Testing Manual

```bash
# Test de SSM Documents
./assets/ec2-stack/scripts/deploy_enhanced_stack.sh test-ssm

# Conectar a instancia via SSM
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=*f5-bridge*" "Name=instance-state-name,Values=running" \
  --query 'Reservations[].Instances[0].InstanceId' \
  --output text --profile agesicUruguay-699019841929)

aws ssm start-session --target $INSTANCE_ID --profile agesicUruguay-699019841929
```

### 3. Verificación en Instancia

```bash
# Una vez conectado via SSM
cd /opt/agesic-datalake

# Verificar estado general
./status.sh

# Gestionar agentes
./manage_agents.sh status
./manage_agents.sh logs python
./manage_agents.sh start kinesis

# Ejecutar procesamiento manual
./download_and_process.sh

# Ver estadísticas del procesador
python3 f5_log_processor.py --stats
```

## 📊 Monitoreo y Observabilidad

### 1. CloudWatch Logs

```bash
# Logs del procesador Python
journalctl -u f5-processor.service -f

# Logs de Kinesis Agent
journalctl -u aws-kinesis-agent -f

# Logs de Fluentd
journalctl -u td-agent -f

# Logs de setup SSM
tail -f /var/log/agesic-setup.log
```

### 2. Métricas Disponibles

- **SystemD Services**: Estado de timers y servicios
- **SSM Command History**: Historial de comandos ejecutados
- **Lambda Metrics**: Ejecuciones de auto-installer
- **EC2 Metrics**: CPU, memoria, red de instancias
- **Kinesis Metrics**: Records enviados, errores

### 3. Troubleshooting

```bash
# Verificar servicios
systemctl status f5-processor.timer
systemctl status aws-kinesis-agent
systemctl status td-agent

# Verificar configuraciones
cat /etc/aws-kinesis/agent.json
cat /etc/td-agent/td-agent.conf

# Verificar conectividad
aws kinesis describe-stream --stream-name $KINESIS_STREAM_NAME
aws s3 ls s3://$SOURCE_BUCKET/
```

## 🔄 Operaciones Comunes

### 1. Reinstalar Agentes

```bash
# Desde AWS CLI (fuera de la instancia)
aws ssm send-command \
  --instance-ids $INSTANCE_ID \
  --document-name "agesic-dl-poc-install-agents" \
  --parameters "agentType=both" \
  --profile agesicUruguay-699019841929
```

### 2. Reconfigurar Setup Completo

```bash
# Desde AWS CLI (fuera de la instancia)
aws ssm send-command \
  --instance-ids $INSTANCE_ID \
  --document-name "agesic-dl-poc-complete-setup" \
  --profile agesicUruguay-699019841929
```

### 3. Scaling y Gestión

```bash
# Escalar ASG
aws autoscaling set-desired-capacity \
  --auto-scaling-group-name agesic-dl-poc-f5-bridge-asg-enhanced \
  --desired-capacity 2 \
  --profile agesicUruguay-699019841929

# Terminar instancia específica
aws autoscaling terminate-instance-in-auto-scaling-group \
  --instance-id $INSTANCE_ID \
  --should-decrement-desired-capacity \
  --profile agesicUruguay-699019841929
```

## 🔧 Configuración Avanzada

### 1. Personalizar Contexto CDK

Editar `assets/ec2-stack/cdk-context-enhanced.json`:

```json
{
  "ec2": {
    "enable_dual_agents": true,
    "instance_type": "t3.medium",  // Upgrade si necesario
    "max_spot_price": 0.02
  },
  "f5_logs": {
    "processing_interval_minutes": 15,  // Más frecuente
    "max_records_per_batch": 10000     // Más records
  }
}
```

### 2. Modificar SSM Documents

Los documentos YAML en `ssm-documents/` pueden editarse para:
- Cambiar timeouts
- Agregar pasos adicionales
- Modificar configuraciones de agentes
- Personalizar logging

### 3. Extender Lambda Function

El código en `lambda/install_agents.py` puede modificarse para:
- Agregar validaciones adicionales
- Implementar retry logic
- Enviar notificaciones
- Integrar con otros servicios

## 📈 Beneficios del Stack Mejorado

### 1. Técnicos
- ✅ **Supera limitación UserData**: 96.58% reducción en uso
- ✅ **Dual agents support**: Redundancia y flexibilidad
- ✅ **Automatización completa**: Zero-touch deployment
- ✅ **Observabilidad mejorada**: Logging y métricas comprehensivas
- ✅ **Mantenibilidad**: Código organizado y documentado

### 2. Operacionales
- ✅ **Despliegue hands-off**: EventBridge + Lambda automation
- ✅ **Escalabilidad**: Soporte para múltiples instancias
- ✅ **Recuperación automática**: ASG + health checks
- ✅ **Troubleshooting simplificado**: Scripts de gestión mejorados
- ✅ **Configuración flexible**: SSM Documents parametrizados

### 3. Económicos
- ✅ **Spot instances optimizadas**: Mejor precio/disponibilidad
- ✅ **Recursos right-sized**: t3.small para dual agents
- ✅ **Automatización reduce OpEx**: Menos intervención manual
- ✅ **Monitoreo proactivo**: Prevención de problemas costosos

## 🎯 Próximos Pasos

1. **Desplegar stack mejorado** usando scripts automatizados
2. **Validar funcionamiento** con script de validación
3. **Monitorear métricas** en CloudWatch
4. **Optimizar configuración** según patrones de uso
5. **Documentar lecciones aprendidas** para futuras mejoras

---

**Nota**: Este stack mejorado representa una evolución significativa de la arquitectura original, resolviendo limitaciones técnicas críticas mientras mantiene compatibilidad con el ecosistema existente del Data Lake.
