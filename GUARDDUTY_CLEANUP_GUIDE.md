# Guía de Limpieza de Recursos GuardDuty - AGESIC Data Lake PoC

## ⚠️ IMPORTANTE - Lección Aprendida

**Fecha de descubrimiento:** 21 de Agosto de 2025  
**Contexto:** Eliminación del stack `agesic-dl-poc-network`

## Problema Identificado

Al eliminar el stack de network, **GuardDuty crea automáticamente recursos que NO son gestionados por CDK** y que pueden impedir la eliminación limpia del stack.

## Recursos Problemáticos de GuardDuty

### 1. VPC Endpoint
- **Servicio:** `com.amazonaws.us-east-2.guardduty-data`
- **Tipo:** Interface VPC Endpoint
- **Problema:** Crea ENIs en subnets privadas que impiden su eliminación

### 2. Security Group
- **Nombre:** `GuardDutyManagedSecurityGroup-vpc-{VPC_ID}`
- **Tag:** `GuardDutyManaged: true`
- **Problema:** Permanece después de eliminar el VPC Endpoint

### 3. Network Interfaces (ENIs)
- **Descripción:** `VPC Endpoint Interface vpce-{ENDPOINT_ID}`
- **Ubicación:** Subnets privadas del VPC
- **Problema:** Impiden eliminación de subnets

## Procedimiento de Limpieza Obligatorio

### ANTES de eliminar el stack de network:

#### Paso 1: Identificar VPC Endpoints de GuardDuty
```bash
aws ec2 describe-vpc-endpoints \
  --filters "Name=vpc-id,Values={VPC_ID}" "Name=service-name,Values=com.amazonaws.us-east-2.guardduty-data" \
  --profile $AWS_PROFILE --region us-east-2
```

#### Paso 2: Eliminar VPC Endpoints de GuardDuty
```bash
aws ec2 delete-vpc-endpoints \
  --vpc-endpoint-ids {ENDPOINT_ID} \
  --profile $AWS_PROFILE --region us-east-2
```

#### Paso 3: Esperar eliminación completa del VPC Endpoint
```bash
# Verificar que el endpoint esté eliminado
aws ec2 describe-vpc-endpoints \
  --vpc-endpoint-ids {ENDPOINT_ID} \
  --profile $AWS_PROFILE --region us-east-2 2>/dev/null || echo "Eliminado"
```

#### Paso 4: Identificar Security Groups de GuardDuty
```bash
aws ec2 describe-security-groups \
  --filters "Name=vpc-id,Values={VPC_ID}" "Name=tag:GuardDutyManaged,Values=true" \
  --profile $AWS_PROFILE --region us-east-2
```

#### Paso 5: Eliminar Security Groups de GuardDuty
```bash
aws ec2 delete-security-group \
  --group-id {SECURITY_GROUP_ID} \
  --profile $AWS_PROFILE --region us-east-2
```

#### Paso 6: Proceder con eliminación del stack
```bash
cdk destroy agesic-dl-poc-network --profile $AWS_PROFILE --force
```

## Script de Limpieza Automatizada

```bash
#!/bin/bash
# cleanup-guardduty-resources.sh

set -e

VPC_ID="$1"
AWS_PROFILE="${AWS_PROFILE:-agesicUruguay-699019841929}"
AWS_REGION="${AWS_REGION:-us-east-2}"

if [ -z "$VPC_ID" ]; then
    echo "Uso: $0 <VPC_ID>"
    exit 1
fi

echo "🔍 Limpiando recursos de GuardDuty para VPC: $VPC_ID"

# 1. Eliminar VPC Endpoints de GuardDuty
echo "📡 Buscando VPC Endpoints de GuardDuty..."
ENDPOINTS=$(aws ec2 describe-vpc-endpoints \
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=service-name,Values=com.amazonaws.$AWS_REGION.guardduty-data" \
    --query "VpcEndpoints[].VpcEndpointId" \
    --output text \
    --profile $AWS_PROFILE --region $AWS_REGION)

if [ -n "$ENDPOINTS" ]; then
    for endpoint in $ENDPOINTS; do
        echo "🗑️  Eliminando VPC Endpoint: $endpoint"
        aws ec2 delete-vpc-endpoints \
            --vpc-endpoint-ids $endpoint \
            --profile $AWS_PROFILE --region $AWS_REGION
    done
    
    echo "⏳ Esperando eliminación de VPC Endpoints..."
    sleep 60
fi

# 2. Eliminar Security Groups de GuardDuty
echo "🛡️  Buscando Security Groups de GuardDuty..."
SECURITY_GROUPS=$(aws ec2 describe-security-groups \
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=tag:GuardDutyManaged,Values=true" \
    --query "SecurityGroups[].GroupId" \
    --output text \
    --profile $AWS_PROFILE --region $AWS_REGION)

if [ -n "$SECURITY_GROUPS" ]; then
    for sg in $SECURITY_GROUPS; do
        echo "🗑️  Eliminando Security Group: $sg"
        aws ec2 delete-security-group \
            --group-id $sg \
            --profile $AWS_PROFILE --region $AWS_REGION
    done
fi

echo "✅ Limpieza de recursos GuardDuty completada"
echo "🚀 Ahora puedes proceder con: cdk destroy agesic-dl-poc-network --profile $AWS_PROFILE --force"
```

## Integración en el Proceso de Destroy

### Modificar el orden de eliminación:

1. **agesic-dl-poc-visualization** ✅
2. **agesic-dl-poc-ec2** ✅
3. **agesic-dl-poc-monitoring** ✅
4. **agesic-dl-poc-analytics** ✅
5. **agesic-dl-poc-compute** ✅
6. **agesic-dl-poc-streaming** ✅
7. **agesic-dl-poc-storage** ✅
8. **🔧 LIMPIEZA GUARDDUTY** ← **NUEVO PASO OBLIGATORIO**
9. **agesic-dl-poc-network** ✅

## Comandos de Diagnóstico Útiles

### Verificar ENIs en subnets específicas:
```bash
aws ec2 describe-network-interfaces \
  --filters "Name=subnet-id,Values=subnet-xxx,subnet-yyy" \
  --profile $AWS_PROFILE --region us-east-2
```

### Verificar todos los VPC Endpoints en un VPC:
```bash
aws ec2 describe-vpc-endpoints \
  --filters "Name=vpc-id,Values=vpc-xxx" \
  --profile $AWS_PROFILE --region us-east-2
```

### Verificar Security Groups con tag GuardDuty:
```bash
aws ec2 describe-security-groups \
  --filters "Name=tag:GuardDutyManaged,Values=true" \
  --profile $AWS_PROFILE --region us-east-2
```

## Prevención Futura

### Opción 1: Deshabilitar GuardDuty temporalmente
```bash
# Antes del destroy
aws guardduty list-detectors --profile $AWS_PROFILE --region us-east-2
aws guardduty update-detector --detector-id {DETECTOR_ID} --enable false --profile $AWS_PROFILE --region us-east-2

# Después del destroy
aws guardduty update-detector --detector-id {DETECTOR_ID} --enable true --profile $AWS_PROFILE --region us-east-2
```

### Opción 2: Incluir limpieza en script de destroy
Integrar la limpieza de GuardDuty como paso automático antes de eliminar el stack de network.

## Recursos de Referencia

- **VPC Endpoint problemático encontrado:** `vpce-0d5a673c81c99527b`
- **Security Group problemático encontrado:** `sg-0d2497830e66b5eb8`
- **ENIs problemáticas encontradas:** `eni-0f7e222da5be03846`, `eni-0babe96939db2cf41`
- **VPC afectado:** `vpc-054fc5cf21fba9f4d`

---

**⚠️ RECORDATORIO CRÍTICO:**  
**SIEMPRE verificar y limpiar recursos de GuardDuty antes de eliminar el stack de network para evitar fallos en la eliminación.**
