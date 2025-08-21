#!/bin/bash
# AGESIC Data Lake - Enhanced EC2 Stack Deployment Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
PROJECT_DIR="/home/efigueroa/Proyectos/AWS-QDeveloper/proyectos/AgesicDataLakes/agesicdatalake"
AWS_PROFILE="agesicUruguay-699019841929"
AWS_REGION="us-east-2"

usage() {
    echo "Usage: $0 {deploy|destroy|status|update-app|test-ssm}"
    echo ""
    echo "Commands:"
    echo "  deploy      - Deploy enhanced EC2 stack"
    echo "  destroy     - Destroy enhanced EC2 stack"
    echo "  status      - Show deployment status"
    echo "  update-app  - Update app.py to use enhanced stack"
    echo "  test-ssm    - Test SSM Documents manually"
    echo ""
    echo "Environment:"
    echo "  AWS_PROFILE: $AWS_PROFILE"
    echo "  AWS_REGION: $AWS_REGION"
    exit 1
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install AWS CLI."
        exit 1
    fi
    
    # Check CDK
    if ! command -v cdk &> /dev/null; then
        log_error "AWS CDK not found. Please install AWS CDK."
        exit 1
    fi
    
    # Check AWS profile
    if ! aws sts get-caller-identity --profile $AWS_PROFILE &> /dev/null; then
        log_error "AWS profile $AWS_PROFILE not configured or invalid."
        exit 1
    fi
    
    # Check project directory
    if [ ! -d "$PROJECT_DIR" ]; then
        log_error "Project directory not found: $PROJECT_DIR"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

update_app_py() {
    log_info "Updating app.py to use enhanced EC2 stack..."
    
    cd "$PROJECT_DIR"
    
    # Backup original app.py
    if [ ! -f "app.py.backup" ]; then
        cp app.py app.py.backup
        log_info "Created backup: app.py.backup"
    fi
    
    # Create updated app.py
    cat > app.py << 'EOF'
#!/usr/bin/env python3
"""
AGESIC Data Lake PoC - AWS CDK Application
Enhanced version with SSM Documents for F5 Bridge
"""

import aws_cdk as cdk
from stacks.network_stack import NetworkStack
from stacks.storage_stack import StorageStack
from stacks.streaming_stack import StreamingStack
from stacks.compute_stack import ComputeStack
from stacks.analytics_stack import AnalyticsStack
from stacks.monitoring_stack import MonitoringStack
from stacks.ec2_stack_enhanced import EC2StackEnhanced  # Enhanced version
from stacks.visualization_stack import VisualizationStack

app = cdk.App()

# Get context values
project_config = app.node.try_get_context("project")
if not project_config:
    raise ValueError("Project configuration not found in cdk.json context")

# Common tags
common_tags = app.node.try_get_context("tags") or {}

# Environment
env = cdk.Environment(
    account=app.node.try_get_context("account") or "699019841929",
    region=app.node.try_get_context("region") or "us-east-2"
)

# Network Stack
network_stack = NetworkStack(
    app, f"{project_config['prefix']}-network",
    env=env,
    tags=common_tags
)

# Storage Stack
storage_stack = StorageStack(
    app, f"{project_config['prefix']}-storage",
    env=env,
    tags=common_tags
)

# Streaming Stack
streaming_stack = StreamingStack(
    app, f"{project_config['prefix']}-streaming",
    vpc=network_stack.vpc,
    raw_bucket=storage_stack.raw_bucket,
    processed_bucket=storage_stack.processed_bucket,
    env=env,
    tags=common_tags
)

# Compute Stack
compute_stack = ComputeStack(
    app, f"{project_config['prefix']}-compute",
    vpc=network_stack.vpc,
    kinesis_stream=streaming_stack.data_stream,
    raw_bucket=storage_stack.raw_bucket,
    processed_bucket=storage_stack.processed_bucket,
    env=env,
    tags=common_tags
)

# Analytics Stack
analytics_stack = AnalyticsStack(
    app, f"{project_config['prefix']}-analytics",
    processed_bucket=storage_stack.processed_bucket,
    glue_database=compute_stack.glue_database,
    env=env,
    tags=common_tags
)

# Monitoring Stack
monitoring_stack = MonitoringStack(
    app, f"{project_config['prefix']}-monitoring",
    kinesis_stream=streaming_stack.data_stream,
    lambda_function=compute_stack.log_filter_lambda,
    glue_job=compute_stack.etl_job,
    env=env,
    tags=common_tags
)

# Enhanced EC2 Stack (replaces original ec2_stack)
ec2_stack_enhanced = EC2StackEnhanced(
    app, f"{project_config['prefix']}-ec2-enhanced",
    vpc=network_stack.vpc,
    kinesis_stream=streaming_stack.data_stream,
    env=env,
    tags=common_tags
)

# Visualization Stack
visualization_stack = VisualizationStack(
    app, f"{project_config['prefix']}-visualization",
    vpc=network_stack.vpc,
    env=env,
    tags=common_tags
)

# Add dependencies
storage_stack.add_dependency(network_stack)
streaming_stack.add_dependency(storage_stack)
compute_stack.add_dependency(streaming_stack)
analytics_stack.add_dependency(compute_stack)
monitoring_stack.add_dependency(compute_stack)
ec2_stack_enhanced.add_dependency(streaming_stack)  # Enhanced stack dependency
visualization_stack.add_dependency(network_stack)

app.synth()
EOF
    
    log_success "Updated app.py to use enhanced EC2 stack"
}

deploy_stack() {
    log_info "Deploying enhanced EC2 stack..."
    
    cd "$PROJECT_DIR"
    
    # Update app.py first
    update_app_py
    
    # Install PyYAML if not present (for SSM document loading)
    log_info "Installing PyYAML for SSM document support..."
    pip install PyYAML || log_warning "PyYAML installation failed, will use fallback content"
    
    # Synthesize to check for errors
    log_info "Synthesizing CDK application..."
    cdk synth --profile $AWS_PROFILE
    
    # Deploy enhanced EC2 stack
    log_info "Deploying enhanced EC2 stack..."
    cdk deploy agesic-dl-poc-ec2-enhanced --profile $AWS_PROFILE --require-approval never
    
    log_success "Enhanced EC2 stack deployed successfully!"
    
    # Show deployment information
    show_deployment_status
}

destroy_stack() {
    log_warning "Destroying enhanced EC2 stack..."
    
    cd "$PROJECT_DIR"
    
    cdk destroy agesic-dl-poc-ec2-enhanced --profile $AWS_PROFILE --force
    
    log_success "Enhanced EC2 stack destroyed"
}

show_deployment_status() {
    log_info "Checking deployment status..."
    
    # Check CloudFormation stack
    STACK_STATUS=$(aws cloudformation describe-stacks \
        --stack-name agesic-dl-poc-ec2-enhanced \
        --query 'Stacks[0].StackStatus' \
        --output text \
        --profile $AWS_PROFILE \
        --region $AWS_REGION 2>/dev/null || echo "NOT_FOUND")
    
    echo ""
    echo -e "${BLUE}=== Enhanced EC2 Stack Status ===${NC}"
    echo "Stack Status: $STACK_STATUS"
    
    if [ "$STACK_STATUS" = "CREATE_COMPLETE" ] || [ "$STACK_STATUS" = "UPDATE_COMPLETE" ]; then
        log_success "Stack is deployed and ready"
        
        # Get stack outputs
        echo ""
        echo -e "${BLUE}=== Stack Outputs ===${NC}"
        aws cloudformation describe-stacks \
            --stack-name agesic-dl-poc-ec2-enhanced \
            --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue,Description]' \
            --output table \
            --profile $AWS_PROFILE \
            --region $AWS_REGION
        
        # Get instance information
        echo ""
        echo -e "${BLUE}=== EC2 Instance Information ===${NC}"
        INSTANCE_ID=$(aws ec2 describe-instances \
            --filters "Name=tag:Name,Values=*f5-bridge*" "Name=instance-state-name,Values=running" \
            --query 'Reservations[].Instances[0].InstanceId' \
            --output text \
            --profile $AWS_PROFILE \
            --region $AWS_REGION 2>/dev/null || echo "None")
        
        if [ "$INSTANCE_ID" != "None" ] && [ "$INSTANCE_ID" != "" ]; then
            echo "Instance ID: $INSTANCE_ID"
            echo "Connect via SSM: aws ssm start-session --target $INSTANCE_ID --profile $AWS_PROFILE"
        else
            echo "No running F5 Bridge instances found"
        fi
        
    elif [ "$STACK_STATUS" = "NOT_FOUND" ]; then
        log_warning "Stack not deployed"
    else
        log_error "Stack in unexpected state: $STACK_STATUS"
    fi
}

test_ssm_documents() {
    log_info "Testing SSM Documents..."
    
    # Get instance ID
    INSTANCE_ID=$(aws ec2 describe-instances \
        --filters "Name=tag:Name,Values=*f5-bridge*" "Name=instance-state-name,Values=running" \
        --query 'Reservations[].Instances[0].InstanceId' \
        --output text \
        --profile $AWS_PROFILE \
        --region $AWS_REGION 2>/dev/null)
    
    if [ "$INSTANCE_ID" = "" ] || [ "$INSTANCE_ID" = "None" ]; then
        log_error "No running F5 Bridge instance found"
        exit 1
    fi
    
    log_info "Found instance: $INSTANCE_ID"
    
    # Test complete setup document
    log_info "Testing complete setup document..."
    COMMAND_ID=$(aws ssm send-command \
        --instance-ids $INSTANCE_ID \
        --document-name "agesic-dl-poc-complete-setup" \
        --parameters "kinesisStreamName=agesic-dl-poc-streaming-DataStream6F9DAC72-guBUYFNpPRE3" \
        --query 'Command.CommandId' \
        --output text \
        --profile $AWS_PROFILE \
        --region $AWS_REGION)
    
    log_success "Setup command initiated: $COMMAND_ID"
    
    # Wait and check status
    log_info "Waiting for command completion..."
    sleep 30
    
    STATUS=$(aws ssm get-command-invocation \
        --command-id $COMMAND_ID \
        --instance-id $INSTANCE_ID \
        --query 'Status' \
        --output text \
        --profile $AWS_PROFILE \
        --region $AWS_REGION)
    
    echo "Command Status: $STATUS"
    
    if [ "$STATUS" = "Success" ]; then
        log_success "SSM Document test completed successfully"
    else
        log_warning "SSM Document test status: $STATUS"
        
        # Show output
        aws ssm get-command-invocation \
            --command-id $COMMAND_ID \
            --instance-id $INSTANCE_ID \
            --query 'StandardOutputContent' \
            --output text \
            --profile $AWS_PROFILE \
            --region $AWS_REGION
    fi
}

# Main script
case $1 in
    deploy)
        check_prerequisites
        deploy_stack
        ;;
    destroy)
        check_prerequisites
        destroy_stack
        ;;
    status)
        check_prerequisites
        show_deployment_status
        ;;
    update-app)
        update_app_py
        ;;
    test-ssm)
        check_prerequisites
        test_ssm_documents
        ;;
    *)
        usage
        ;;
esac
