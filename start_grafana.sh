#!/bin/bash

# Script para iniciar Grafana en contenedor Docker
# Archivo: start_grafana.sh
# Uso: ./start_grafana.sh

set -e

echo "=== AGESIC Data Lake - Grafana Deployment Script ==="
echo "Iniciando despliegue de Grafana OSS 12.1.0..."

# Verificar si Docker está instalado y funcionando
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker no está instalado"
    exit 1
fi

if ! sudo docker info &> /dev/null; then
    echo "ERROR: Docker no está funcionando o no tienes permisos sudo"
    exit 1
fi

# Detener y eliminar contenedor existente si existe
echo "Verificando contenedores existentes..."
if sudo docker ps -a | grep -q grafana; then
    echo "Deteniendo contenedor Grafana existente..."
    sudo docker stop grafana 2>/dev/null || true
    echo "Eliminando contenedor Grafana existente..."
    sudo docker rm grafana 2>/dev/null || true
fi

# Crear volúmenes si no existen
echo "Creando volúmenes de Docker..."
sudo docker volume create grafana-storage 2>/dev/null || true
sudo docker volume create grafana-logs 2>/dev/null || true

# Iniciar contenedor Grafana
echo "Iniciando contenedor Grafana..."
sudo docker run -d \
  --name grafana \
  -p 3000:3000 \
  -e GF_INSTALL_PLUGINS=grafana-athena-datasource,cloudwatch \
  -e GF_SECURITY_ADMIN_PASSWORD=admin123 \
  -e GF_SECURITY_ALLOW_EMBEDDING=true \
  -e GF_SECURITY_COOKIE_SECURE=false \
  -e GF_SECURITY_COOKIE_SAMESITE=lax \
  -e GF_ANALYTICS_REPORTING_ENABLED=false \
  -e GF_ANALYTICS_CHECK_FOR_UPDATES=false \
  -e GF_USERS_ALLOW_SIGN_UP=false \
  -e GF_USERS_ALLOW_ORG_CREATE=false \
  -e GF_SNAPSHOTS_EXTERNAL_ENABLED=false \
  -e GF_LOG_LEVEL=info \
  -e GF_SERVER_ROOT_URL='%(protocol)s://%(domain)s/' \
  -e GF_SERVER_SERVE_FROM_SUB_PATH=false \
  -e GF_FEATURE_TOGGLES_ENABLE=publicDashboards \
  -v grafana-storage:/var/lib/grafana \
  -v grafana-logs:/var/log/grafana \
  --restart unless-stopped \
  grafana/grafana-oss:12.1.0

if [ $? -eq 0 ]; then
    echo "✅ Contenedor Grafana iniciado exitosamente"
else
    echo "❌ Error al iniciar contenedor Grafana"
    exit 1
fi

# Esperar a que Grafana esté listo
echo "Esperando a que Grafana esté listo..."
sleep 30

# Verificar estado del contenedor
echo "Verificando estado del contenedor..."
CONTAINER_STATUS=$(sudo docker ps --filter "name=grafana" --format "{{.Status}}")
if [[ $CONTAINER_STATUS == *"Up"* ]]; then
    echo "✅ Contenedor está ejecutándose: $CONTAINER_STATUS"
else
    echo "❌ Problema con el contenedor:"
    sudo docker ps -a | grep grafana
    echo "Logs del contenedor:"
    sudo docker logs grafana | tail -10
    exit 1
fi

# Verificar conectividad local
echo "Verificando conectividad local..."
if curl -s -I http://localhost:3000 | grep -q "200 OK"; then
    echo "✅ Grafana responde correctamente en puerto 3000"
else
    echo "⚠️  Grafana aún no responde, verificando logs..."
    sudo docker logs grafana | tail -5
fi

# Mostrar información de acceso
echo ""
echo "=== INFORMACIÓN DE ACCESO ==="
echo "URL Local: http://localhost:3000"
echo "Usuario: admin"
echo "Contraseña: admin123"
echo ""
echo "=== COMANDOS ÚTILES ==="
echo "Ver logs: sudo docker logs grafana"
echo "Ver logs en tiempo real: sudo docker logs -f grafana"
echo "Reiniciar: sudo docker restart grafana"
echo "Detener: sudo docker stop grafana"
echo "Estado: sudo docker ps | grep grafana"
echo ""
echo "=== VERIFICACIÓN FINAL ==="
echo "Contenedores activos:"
sudo docker ps | grep grafana
echo ""
echo "Puerto 3000 en uso:"
ss -lnt | grep 3000 || echo "Puerto 3000 no está en uso"
echo ""
echo "✅ Script completado. Grafana debería estar disponible en unos minutos."
