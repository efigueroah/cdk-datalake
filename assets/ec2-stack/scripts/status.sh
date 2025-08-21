#!/bin/bash
# AGESIC Data Lake F5 Bridge - System Status Script

echo "=== AGESIC Data Lake F5 Bridge Status ==="
echo "Date: $(date)"
echo ""

echo "=== System Status ==="
echo "Uptime: $(uptime)"
echo "Memory: $(free -h | grep Mem)"
echo "Disk Usage: $(df -h /var/log | tail -1)"
echo ""

echo "=== AWS Configuration ==="
echo "Region: $(aws configure get region || echo 'us-east-2')"
echo "Identity: $(aws sts get-caller-identity --query 'Account' --output text 2>/dev/null || echo 'Not configured')"
echo ""

echo "=== Environment Variables ==="
echo "SOURCE_BUCKET: ${SOURCE_BUCKET:-rawdata-analytics-poc-voh9ai}"
echo "SOURCE_FILE: ${SOURCE_FILE:-extracto_logs_acceso_f5_portalgubuy.txt}"
echo "LOCAL_LOG_DIR: ${LOCAL_LOG_DIR:-/var/log/logs_f5}"
echo "KINESIS_STREAM_NAME: ${KINESIS_STREAM_NAME:-agesic-dl-poc-streaming-DataStream6F9DAC72-guBUYFNpPRE3}"
echo ""

echo "=== Services Status ==="
systemctl is-active f5-processor.timer 2>/dev/null && echo "F5 Timer: Active" || echo "F5 Timer: Inactive"
systemctl is-active aws-kinesis-agent 2>/dev/null && echo "Kinesis Agent: Active" || echo "Kinesis Agent: Not installed/inactive"
systemctl is-active td-agent 2>/dev/null && echo "Fluentd: Active" || echo "Fluentd: Not installed/inactive"
echo ""

echo "=== Log Files ==="
echo "F5 Log Directory: /var/log/logs_f5"
if [ -d "/var/log/logs_f5" ]; then
    ls -la /var/log/logs_f5/ 2>/dev/null || echo "Directory exists but no files found"
else
    echo "Directory does not exist"
fi
echo ""

echo "=== Connectivity Tests ==="
echo "Testing S3 access..."
aws s3 ls s3://${SOURCE_BUCKET:-rawdata-analytics-poc-voh9ai}/ --max-items 3 2>/dev/null && echo "S3 access: OK" || echo "S3 access: FAILED"

echo "Testing Kinesis access..."
aws kinesis describe-stream --stream-name ${KINESIS_STREAM_NAME:-agesic-dl-poc-streaming-DataStream6F9DAC72-guBUYFNpPRE3} --query 'StreamDescription.StreamStatus' --output text 2>/dev/null && echo "Kinesis access: OK" || echo "Kinesis access: FAILED"
echo ""

echo "=== Recent Processing Activity ==="
if [ -f "/var/log/agesic-setup.log" ]; then
    echo "Last 5 setup log entries:"
    tail -5 /var/log/agesic-setup.log
else
    echo "No setup log found"
fi
echo ""

echo "=== SystemD Timer Status ==="
if systemctl list-unit-files | grep -q f5-processor.timer; then
    systemctl status f5-processor.timer --no-pager -l
else
    echo "F5 processor timer not configured"
fi
