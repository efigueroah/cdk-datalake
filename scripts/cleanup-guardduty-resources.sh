#!/bin/bash
# cleanup-guardduty-resources.sh
# Script para limpiar recursos de GuardDuty antes de eliminar el stack de network

set -e

VPC_ID="$1"
AWS_PROFILE="${AWS_PROFILE:-agesicUruguay-699019841929}"
AWS_REGION="${AWS_REGION:-us-east-2}"

if [ -z "$VPC_ID" ]; then
    echo "❌ Error: VPC_ID es requerido"
    echo "Uso: $0 <VPC_ID>"
    echo "Ejemplo: $0 vpc-054fc5cf21fba9f4d"
    exit 1
fi

echo "🔍 Limpiando recursos de GuardDuty para VPC: $VPC_ID"
echo "📋 Perfil AWS: $AWS_PROFILE"
echo "🌍 Región: $AWS_REGION"
echo ""

# 1. Eliminar VPC Endpoints de GuardDuty
echo "📡 Paso 1: Buscando VPC Endpoints de GuardDuty..."
ENDPOINTS=$(aws ec2 describe-vpc-endpoints \
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=service-name,Values=com.amazonaws.$AWS_REGION.guardduty-data" \
    --query "VpcEndpoints[].VpcEndpointId" \
    --output text \
    --profile $AWS_PROFILE --region $AWS_REGION 2>/dev/null || echo "")

if [ -n "$ENDPOINTS" ] && [ "$ENDPOINTS" != "None" ]; then
    for endpoint in $ENDPOINTS; do
        echo "🗑️  Eliminando VPC Endpoint: $endpoint"
        aws ec2 delete-vpc-endpoints \
            --vpc-endpoint-ids $endpoint \
            --profile $AWS_PROFILE --region $AWS_REGION
        echo "✅ VPC Endpoint $endpoint marcado para eliminación"
    done
    
    echo "⏳ Esperando eliminación completa de VPC Endpoints (60 segundos)..."
    sleep 60
    
    # Verificar eliminación
    for endpoint in $ENDPOINTS; do
        if aws ec2 describe-vpc-endpoints --vpc-endpoint-ids $endpoint --profile $AWS_PROFILE --region $AWS_REGION >/dev/null 2>&1; then
            echo "⚠️  VPC Endpoint $endpoint aún existe, esperando más tiempo..."
            sleep 30
        else
            echo "✅ VPC Endpoint $endpoint eliminado completamente"
        fi
    done
else
    echo "ℹ️  No se encontraron VPC Endpoints de GuardDuty"
fi

echo ""

# 2. Eliminar Security Groups de GuardDuty
echo "🛡️  Paso 2: Buscando Security Groups de GuardDuty..."
SECURITY_GROUPS=$(aws ec2 describe-security-groups \
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=tag:GuardDutyManaged,Values=true" \
    --query "SecurityGroups[].GroupId" \
    --output text \
    --profile $AWS_PROFILE --region $AWS_REGION 2>/dev/null || echo "")

if [ -n "$SECURITY_GROUPS" ] && [ "$SECURITY_GROUPS" != "None" ]; then
    for sg in $SECURITY_GROUPS; do
        echo "🗑️  Eliminando Security Group: $sg"
        
        # Verificar que no tenga ENIs asociadas
        ENIS=$(aws ec2 describe-network-interfaces \
            --filters "Name=group-id,Values=$sg" \
            --query "NetworkInterfaces[].NetworkInterfaceId" \
            --output text \
            --profile $AWS_PROFILE --region $AWS_REGION 2>/dev/null || echo "")
        
        if [ -n "$ENIS" ] && [ "$ENIS" != "None" ]; then
            echo "⚠️  Security Group $sg tiene ENIs asociadas: $ENIS"
            echo "⚠️  Esperando que se liberen las ENIs..."
            sleep 30
        fi
        
        # Intentar eliminar el Security Group
        if aws ec2 delete-security-group \
            --group-id $sg \
            --profile $AWS_PROFILE --region $AWS_REGION 2>/dev/null; then
            echo "✅ Security Group $sg eliminado exitosamente"
        else
            echo "❌ Error eliminando Security Group $sg (puede tener dependencias)"
        fi
    done
else
    echo "ℹ️  No se encontraron Security Groups de GuardDuty"
fi

echo ""
echo "🎉 Limpieza de recursos GuardDuty completada"
echo ""
echo "🚀 Ahora puedes proceder con:"
echo "   cdk destroy agesic-dl-poc-network --profile $AWS_PROFILE --force"
echo ""
echo "📋 O usar el comando completo de destroy:"
echo "   cdk destroy --all --profile $AWS_PROFILE --force"
