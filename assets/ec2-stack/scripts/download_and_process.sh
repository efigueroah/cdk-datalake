#!/bin/bash
# AGESIC Data Lake F5 Bridge - Download and Process Script

echo "=== AGESIC Data Lake F5 Log Download and Processing ==="

# Set environment variables with defaults
export SOURCE_BUCKET="${SOURCE_BUCKET:-rawdata-analytics-poc-voh9ai}"
export SOURCE_FILE="${SOURCE_FILE:-extracto_logs_acceso_f5_portalgubuy.txt}"
export LOCAL_LOG_DIR="${LOCAL_LOG_DIR:-/var/log/logs_f5}"
export KINESIS_STREAM_NAME="${KINESIS_STREAM_NAME:-agesic-dl-poc-streaming-DataStream6F9DAC72-guBUYFNpPRE3}"

# Ensure directory exists
mkdir -p $LOCAL_LOG_DIR

echo "Configuration:"
echo "  Source: s3://$SOURCE_BUCKET/$SOURCE_FILE"
echo "  Local dir: $LOCAL_LOG_DIR"
echo "  Kinesis stream: $KINESIS_STREAM_NAME"
echo ""

# Check if processor exists
PROCESSOR_PATH="/opt/agesic-datalake/f5_log_processor.py"
if [ ! -f "$PROCESSOR_PATH" ]; then
    echo "ERROR: F5 log processor not found at $PROCESSOR_PATH"
    echo "Please run SSM Document 'agesic-dl-poc-complete-setup' first"
    exit 1
fi

echo "Processing F5 logs and sending to Kinesis..."
python3 $PROCESSOR_PATH --max-records 5000

PROCESSOR_EXIT_CODE=$?

echo ""
if [ $PROCESSOR_EXIT_CODE -eq 0 ]; then
    echo "=== Processing completed successfully ==="
    echo "Check status with: /opt/agesic-datalake/status.sh"
else
    echo "=== Processing failed with exit code $PROCESSOR_EXIT_CODE ==="
    echo "Check logs for details"
    exit $PROCESSOR_EXIT_CODE
fi
