#!/bin/bash

# AGESIC Data Lake - Clean Destroy Script
# Handles GuardDuty endpoints and Kinesis streams cleanup

set -e

echo "🧹 AGESIC Data Lake - Clean Destroy Script"
echo "=========================================="

# Configuration
PROFILE="agesicUruguay-699019841929"
REGION="us-east-2"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if stack exists
stack_exists() {
    local stack_name=$1
    aws cloudformation describe-stacks --stack-name "$stack_name" --profile "$PROFILE" --region "$REGION" &> /dev/null
}

# Function to get stack status
get_stack_status() {
    local stack_name=$1
    aws cloudformation describe-stacks --stack-name "$stack_name" --profile "$PROFILE" --region "$REGION" --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND"
}

# Function to wait for stack deletion
wait_for_stack_deletion() {
    local stack_name=$1
    local max_wait=1800  # 30 minutes
    local wait_time=0
    
    print_status "Waiting for stack deletion: $stack_name"
    
    while stack_exists "$stack_name" && [ $wait_time -lt $max_wait ]; do
        local status=$(get_stack_status "$stack_name")
        print_status "Stack $stack_name status: $status"
        
        if [ "$status" = "DELETE_FAILED" ]; then
            print_error "Stack deletion failed: $stack_name"
            return 1
        fi
        
        sleep 30
        wait_time=$((wait_time + 30))
    done
    
    if stack_exists "$stack_name"; then
        print_error "Stack deletion timeout: $stack_name"
        return 1
    else
        print_success "Stack deleted successfully: $stack_name"
        return 0
    fi
}

# Function to cleanup GuardDuty endpoints
cleanup_guardduty_endpoints() {
    print_status "Cleaning up GuardDuty VPC endpoints..."
    
    # Try to find the VPC
    local vpc_id=$(aws ec2 describe-vpcs \
        --filters "Name=tag:Name,Values=agesic-dl-poc-vpc" "Name=state,Values=available" \
        --query 'Vpcs[0].VpcId' \
        --output text \
        --profile "$PROFILE" \
        --region "$REGION" 2>/dev/null)
    
    if [ "$vpc_id" = "None" ] || [ -z "$vpc_id" ]; then
        print_warning "VPC not found, skipping GuardDuty cleanup"
        return 0
    fi
    
    print_status "Found VPC: $vpc_id"
    
    # Run the cleanup script
    if python scripts/cleanup_guardduty_endpoints.py --vpc-id "$vpc_id" --profile "$PROFILE" --region "$REGION"; then
        print_success "GuardDuty endpoints cleaned up"
        return 0
    else
        print_warning "GuardDuty cleanup had issues, continuing anyway"
        return 0
    fi
}

# Function to cleanup Kinesis streams manually
cleanup_kinesis_streams() {
    print_status "Cleaning up orphaned Kinesis streams..."
    
    # Find streams with our prefix
    local streams=$(aws kinesis list-streams \
        --profile "$PROFILE" \
        --region "$REGION" \
        --query 'StreamNames[?contains(@, `agesic-dl-poc-streaming-DataStream`)]' \
        --output text 2>/dev/null)
    
    if [ -z "$streams" ]; then
        print_status "No orphaned Kinesis streams found"
        return 0
    fi
    
    for stream in $streams; do
        print_status "Deleting Kinesis stream: $stream"
        
        # First, try to delete the stream
        if aws kinesis delete-stream \
            --stream-name "$stream" \
            --profile "$PROFILE" \
            --region "$REGION" 2>/dev/null; then
            print_success "Kinesis stream deletion initiated: $stream"
        else
            print_warning "Could not delete Kinesis stream: $stream"
        fi
    done
}

# Validate prerequisites
print_status "Validating prerequisites..."

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI not found. Please install AWS CLI."
    exit 1
fi

# Check CDK CLI
if ! command -v cdk &> /dev/null; then
    print_error "CDK CLI not found. Please install AWS CDK."
    exit 1
fi

# Check profile
if ! aws configure list --profile $PROFILE &> /dev/null; then
    print_error "AWS profile '$PROFILE' not found. Please configure the profile."
    exit 1
fi

print_success "Prerequisites validated"

# Warning
print_warning "This will destroy ALL AGESIC Data Lake resources!"
print_warning "This action cannot be undone!"
echo ""
read -p "Are you sure you want to continue? (type 'yes' to confirm): " confirm

if [ "$confirm" != "yes" ]; then
    print_error "Aborted by user"
    exit 0
fi

# List stacks to destroy
STACKS=(
    "agesic-dl-poc-visualization"
    "agesic-dl-poc-ec2"
    "agesic-dl-poc-monitoring"
    "agesic-dl-poc-analytics"
    "agesic-dl-poc-compute"
    "agesic-dl-poc-streaming"
    "agesic-dl-poc-storage"
    "agesic-dl-poc-network"
)

print_status "Starting destruction of ${#STACKS[@]} stacks..."

# Phase 1: Destroy stacks in reverse order
for i in "${!STACKS[@]}"; do
    stack="${STACKS[$i]}"
    stack_num=$((i + 1))
    
    if stack_exists "$stack"; then
        print_status "Destroying stack $stack_num/${#STACKS[@]}: $stack"
        
        if cdk destroy "$stack" --profile "$PROFILE" --force; then
            print_success "Stack destruction initiated: $stack"
        else
            print_error "Failed to initiate destruction of stack: $stack"
            
            # Special handling for network stack
            if [ "$stack" = "agesic-dl-poc-network" ]; then
                print_status "Network stack destruction failed, trying GuardDuty cleanup..."
                cleanup_guardduty_endpoints
                
                print_status "Retrying network stack destruction..."
                if cdk destroy "$stack" --profile "$PROFILE" --force; then
                    print_success "Network stack destruction succeeded after cleanup"
                else
                    print_error "Network stack destruction still failed"
                fi
            fi
        fi
    else
        print_status "Stack $stack does not exist, skipping"
    fi
    
    echo ""
done

# Phase 2: Wait for all deletions to complete
print_status "Waiting for all stack deletions to complete..."

for stack in "${STACKS[@]}"; do
    if stack_exists "$stack"; then
        wait_for_stack_deletion "$stack"
    fi
done

# Phase 3: Cleanup orphaned resources
print_status "Cleaning up orphaned resources..."

cleanup_kinesis_streams
cleanup_guardduty_endpoints

# Final verification
print_status "Verifying cleanup..."

remaining_stacks=()
for stack in "${STACKS[@]}"; do
    if stack_exists "$stack"; then
        remaining_stacks+=("$stack")
    fi
done

if [ ${#remaining_stacks[@]} -eq 0 ]; then
    print_success "🎉 ALL STACKS DESTROYED SUCCESSFULLY!"
    echo "======================================"
    print_status "All AGESIC Data Lake resources have been removed"
    print_status "No recurring costs should remain"
    echo ""
    print_status "📋 Resources that were cleaned up:"
    echo "  • All 8 CDK stacks"
    echo "  • VPC and networking components"
    echo "  • S3 buckets and data"
    echo "  • Kinesis streams and Firehose"
    echo "  • Lambda functions and Glue jobs"
    echo "  • CloudWatch dashboards and alarms"
    echo "  • EC2 instances and Auto Scaling Groups"
    echo "  • Grafana visualization infrastructure"
    echo "  • GuardDuty VPC endpoints (if any)"
    echo ""
    print_success "✅ CLEANUP COMPLETED!"
else
    print_warning "⚠️  Some stacks still exist:"
    for stack in "${remaining_stacks[@]}"; do
        local status=$(get_stack_status "$stack")
        echo "  • $stack ($status)"
    done
    echo ""
    print_status "You may need to:"
    echo "  1. Check the AWS Console for detailed error messages"
    echo "  2. Manually delete remaining resources"
    echo "  3. Run the cleanup scripts individually"
    echo ""
    print_status "Manual cleanup commands:"
    echo "  • GuardDuty: python scripts/cleanup_guardduty_endpoints.py --vpc-name agesic-dl-poc-vpc"
    echo "  • Kinesis: aws kinesis delete-stream --stream-name <stream-name>"
fi
