#!/bin/bash

# AGESIC Data Lake PoC - Upload F5 Test File to S3
# Script to upload the F5 log file for testing the new architecture

set -e

# Configuration
SOURCE_FILE="/home/efigueroa/Proyectos/AWS-QDeveloper/proyectos/AgesicDataLakes/Logs/parser/extracto_logs_acceso_f5_portalgubuy.txt"
TARGET_BUCKET="rawdata-analytics-poc-voh9ai"
TARGET_KEY="extracto_logs_acceso_f5_portalgubuy.txt"
AWS_PROFILE="agesicUruguay-699019841929"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if source file exists
if [ ! -f "$SOURCE_FILE" ]; then
    error "Source file not found: $SOURCE_FILE"
    exit 1
fi

# Check file size
FILE_SIZE=$(stat -c%s "$SOURCE_FILE")
FILE_SIZE_MB=$((FILE_SIZE / 1024 / 1024))

log "=== AGESIC Data Lake F5 File Upload ==="
log "Source file: $SOURCE_FILE"
log "File size: ${FILE_SIZE_MB} MB (${FILE_SIZE} bytes)"
log "Target bucket: s3://$TARGET_BUCKET/$TARGET_KEY"
log "AWS Profile: $AWS_PROFILE"

# Verify AWS credentials
log "Verifying AWS credentials..."
if ! aws sts get-caller-identity --profile "$AWS_PROFILE" > /dev/null 2>&1; then
    error "AWS credentials not configured or invalid for profile: $AWS_PROFILE"
    error "Please run: aws configure --profile $AWS_PROFILE"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query 'Account' --output text)
log "Using AWS Account: $ACCOUNT_ID"

# Check if bucket exists and is accessible
log "Checking bucket access..."
if ! aws s3 ls "s3://$TARGET_BUCKET" --profile "$AWS_PROFILE" > /dev/null 2>&1; then
    error "Cannot access bucket: s3://$TARGET_BUCKET"
    error "Please verify bucket exists and you have permissions"
    exit 1
fi

# Show first few lines of the file for verification
log "Sample of F5 log file (first 3 lines):"
head -3 "$SOURCE_FILE" | while IFS= read -r line; do
    echo "  $line"
done

# Confirm upload
echo ""
read -p "Do you want to upload this file to S3? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    warning "Upload cancelled by user"
    exit 0
fi

# Upload file to S3
log "Uploading file to S3..."
if aws s3 cp "$SOURCE_FILE" "s3://$TARGET_BUCKET/$TARGET_KEY" \
    --profile "$AWS_PROFILE" \
    --metadata "source=agesic-datalake-poc,upload-date=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --storage-class STANDARD; then
    
    log "✅ File uploaded successfully!"
    
    # Verify upload
    log "Verifying upload..."
    UPLOADED_SIZE=$(aws s3api head-object \
        --bucket "$TARGET_BUCKET" \
        --key "$TARGET_KEY" \
        --profile "$AWS_PROFILE" \
        --query 'ContentLength' \
        --output text)
    
    if [ "$UPLOADED_SIZE" = "$FILE_SIZE" ]; then
        log "✅ Upload verification successful (${UPLOADED_SIZE} bytes)"
    else
        error "❌ Upload verification failed! Local: ${FILE_SIZE}, S3: ${UPLOADED_SIZE}"
        exit 1
    fi
    
    # Show S3 object details
    log "S3 Object Details:"
    aws s3api head-object \
        --bucket "$TARGET_BUCKET" \
        --key "$TARGET_KEY" \
        --profile "$AWS_PROFILE" \
        --query '{Size: ContentLength, LastModified: LastModified, ETag: ETag, StorageClass: StorageClass}' \
        --output table
    
    log "=== Upload Complete ==="
    log "Next steps:"
    log "1. Deploy the updated CDK stacks"
    log "2. Connect to EC2 instance via SSM"
    log "3. Run: /opt/agesic-datalake/download_and_process.sh"
    log "4. Monitor Kinesis and S3 for processed data"
    
else
    error "❌ Upload failed!"
    exit 1
fi
