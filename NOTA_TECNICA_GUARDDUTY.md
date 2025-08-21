# 📝 NOTA TÉCNICA - GuardDuty y Stack Network

**Fecha:** 21 de Agosto de 2025  
**Problema:** Eliminación del stack `agesic-dl-poc-network`  
**Causa:** Recursos automáticos de GuardDuty  

## ⚠️ ACCIÓN REQUERIDA

**ANTES** de eliminar el stack de network, ejecutar:

```bash
# Opción 1: Script automatizado
./scripts/cleanup-guardduty-resources.sh vpc-{VPC_ID}

# Opción 2: Comandos manuales
aws ec2 describe-vpc-endpoints --filters "Name=vpc-id,Values={VPC_ID}" "Name=service-name,Values=com.amazonaws.us-east-2.guardduty-data"
aws ec2 delete-vpc-endpoints --vpc-endpoint-ids {ENDPOINT_ID}
aws ec2 describe-security-groups --filters "Name=vpc-id,Values={VPC_ID}" "Name=tag:GuardDutyManaged,Values=true"
aws ec2 delete-security-group --group-id {SECURITY_GROUP_ID}
```

## 🔍 Recursos Problemáticos

- **VPC Endpoint:** `com.amazonaws.us-east-2.guardduty-data`
- **Security Group:** `GuardDutyManagedSecurityGroup-vpc-{VPC_ID}`
- **ENIs:** Creadas automáticamente en subnets privadas

## 📚 Documentación Completa

Ver: [GUARDDUTY_CLEANUP_GUIDE.md](./GUARDDUTY_CLEANUP_GUIDE.md)

---
**💡 Recordatorio:** GuardDuty crea recursos automáticamente que NO son gestionados por CDK
