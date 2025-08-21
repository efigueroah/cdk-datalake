#!/bin/bash

# AGESIC Data Lake - Clean Deployment Script
# Deploys all stacks in the correct order with validation

set -e

echo "🚀 AGESIC Data Lake - Clean Deployment Script"
echo "=============================================="

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

# Verify region
CONFIGURED_REGION=$(aws configure get region --profile $PROFILE)
if [ "$CONFIGURED_REGION" != "$REGION" ]; then
    print_warning "Profile region is '$CONFIGURED_REGION', expected '$REGION'"
    print_status "Using profile region: $CONFIGURED_REGION"
    REGION=$CONFIGURED_REGION
fi

print_success "Prerequisites validated"

# Run integration validation
print_status "Running integration validation..."
if python scripts/validate_visualization_integration.py; then
    print_success "Integration validation passed"
else
    print_error "Integration validation failed"
    exit 1
fi

# CDK Bootstrap (if needed)
print_status "Checking CDK bootstrap status..."
if aws cloudformation describe-stacks --stack-name CDKToolkit --profile $PROFILE --region $REGION &> /dev/null; then
    print_success "CDK already bootstrapped"
else
    print_status "Bootstrapping CDK..."
    cdk bootstrap --profile $PROFILE
    print_success "CDK bootstrapped"
fi

# Synthesize templates
print_status "Synthesizing CDK templates..."
if cdk synth --profile $PROFILE; then
    print_success "CDK synthesis successful"
else
    print_error "CDK synthesis failed"
    exit 1
fi

# Deploy stacks in order
STACKS=(
    "agesic-dl-poc-network"
    "agesic-dl-poc-storage"
    "agesic-dl-poc-streaming"
    "agesic-dl-poc-compute"
    "agesic-dl-poc-analytics"
    "agesic-dl-poc-monitoring"
    "agesic-dl-poc-ec2"
    "agesic-dl-poc-visualization"
)

print_status "Starting deployment of ${#STACKS[@]} stacks..."

for i in "${!STACKS[@]}"; do
    stack="${STACKS[$i]}"
    stack_num=$((i + 1))
    
    print_status "Deploying stack $stack_num/${#STACKS[@]}: $stack"
    
    if [ "$stack" == "agesic-dl-poc-visualization" ]; then
        print_status "🎨 Deploying Visualization Stack (Grafana OSS 12.1.0 with F5 integration)"
    fi
    
    if cdk deploy $stack --profile $PROFILE --require-approval never; then
        print_success "Stack $stack deployed successfully"
        
        # Special handling for visualization stack
        if [ "$stack" == "agesic-dl-poc-visualization" ]; then
            print_success "🎉 Visualization stack deployed!"
            print_status "Grafana will be available at the ALB URL (check CloudFormation outputs)"
            print_status "Default credentials: admin / admin123"
            print_warning "Remember to change default password after first login"
        fi
    else
        print_error "Failed to deploy stack: $stack"
        exit 1
    fi
    
    echo ""
done

# Get deployment outputs
print_status "Retrieving deployment outputs..."

echo ""
print_success "🎉 DEPLOYMENT COMPLETED SUCCESSFULLY!"
echo "======================================"

print_status "All 8 stacks deployed in region: $REGION"
print_status "Stack deployment order:"
for i in "${!STACKS[@]}"; do
    stack="${STACKS[$i]}"
    stack_num=$((i + 1))
    if [ "$stack" == "agesic-dl-poc-visualization" ]; then
        echo "  $stack_num. $stack ⭐ (Grafana OSS 12.1.0)"
    else
        echo "  $stack_num. $stack"
    fi
done

echo ""
print_status "🔍 Key Resources Created:"
echo "  • VPC with public/private subnets across 2 AZs"
echo "  • S3 buckets for data lake (raw, processed, scripts, results)"
echo "  • Kinesis Data Streams + Firehose for real-time ingestion"
echo "  • Lambda functions with F5 log processing + custom metrics"
echo "  • Glue ETL jobs with F5-optimized schema (25+ fields)"
echo "  • Athena workgroup with 8 predefined F5 queries"
echo "  • CloudWatch dashboard with F5 metrics + alarms"
echo "  • EC2 Auto Scaling Group for F5 log bridge"
echo "  • Grafana OSS 12.1.0 with Athena + CloudWatch datasources"
echo "  • Application Load Balancer for Grafana access"

echo ""
print_status "📊 F5 Analytics Features:"
echo "  • Custom F5 metrics: AverageResponseTime, ErrorRate, PoolHealthScore"
echo "  • F5-specific Glue table with intelligent partitioning"
echo "  • Mobile device detection and content categorization"
echo "  • Cache hit analysis and performance monitoring"
echo "  • Real-time P95 response time calculation"

echo ""
print_status "🎨 Grafana Features:"
echo "  • Pre-configured Athena datasource for F5 data queries"
echo "  • Pre-configured CloudWatch datasource for F5 metrics"
echo "  • Auto-configured for F5 dashboard creation"
echo "  • Public dashboards feature enabled"

echo ""
print_status "📋 Next Steps:"
echo "  1. Access Grafana via ALB URL (check CloudFormation outputs)"
echo "  2. Login with admin/admin123 and change password"
echo "  3. Create F5 dashboards using pre-configured datasources"
echo "  4. Upload F5 logs to trigger the processing pipeline"
echo "  5. Monitor F5 metrics in CloudWatch dashboard"

echo ""
print_success "✅ AGESIC Data Lake with F5 Integration Ready!"
