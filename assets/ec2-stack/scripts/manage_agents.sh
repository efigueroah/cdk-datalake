#!/bin/bash
# AGESIC Data Lake - Agent Management Script
# Manages Python processor, Kinesis Agent, and Fluentd services

usage() {
    echo "Usage: $0 {start|stop|restart|status|logs} [agent_type]"
    echo "agent_type: python|kinesis|fluentd|all (default: all)"
    echo ""
    echo "Examples:"
    echo "  $0 status                    # Show status of all agents"
    echo "  $0 start python             # Start only Python processor"
    echo "  $0 restart kinesis          # Restart only Kinesis Agent"
    echo "  $0 logs fluentd             # Show Fluentd logs"
    echo "  $0 stop all                 # Stop all agents"
    exit 1
}

ACTION=$1
AGENT_TYPE=${2:-all}

if [ -z "$ACTION" ]; then
    usage
fi

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

manage_python() {
    case $1 in
        start)
            if systemctl start f5-processor.timer; then
                log_success "Python processor timer started"
            else
                log_error "Failed to start Python processor timer"
            fi
            ;;
        stop)
            if systemctl stop f5-processor.timer; then
                log_success "Python processor timer stopped"
            else
                log_error "Failed to stop Python processor timer"
            fi
            ;;
        restart)
            if systemctl restart f5-processor.timer; then
                log_success "Python processor timer restarted"
            else
                log_error "Failed to restart Python processor timer"
            fi
            ;;
        status)
            echo -e "${BLUE}=== Python F5 Processor Status ===${NC}"
            systemctl status f5-processor.timer --no-pager -l
            echo ""
            systemctl status f5-processor.service --no-pager -l
            ;;
        logs)
            echo -e "${BLUE}=== Python F5 Processor Logs ===${NC}"
            journalctl -u f5-processor.service -n 50 --no-pager
            ;;
        run)
            log_info "Running Python processor manually"
            cd /opt/agesic-datalake && ./download_and_process.sh
            ;;
    esac
}

manage_kinesis() {
    if systemctl list-unit-files | grep -q aws-kinesis-agent; then
        case $1 in
            start)
                if systemctl start aws-kinesis-agent; then
                    log_success "Kinesis Agent started"
                else
                    log_error "Failed to start Kinesis Agent"
                fi
                ;;
            stop)
                if systemctl stop aws-kinesis-agent; then
                    log_success "Kinesis Agent stopped"
                else
                    log_error "Failed to stop Kinesis Agent"
                fi
                ;;
            restart)
                if systemctl restart aws-kinesis-agent; then
                    log_success "Kinesis Agent restarted"
                else
                    log_error "Failed to restart Kinesis Agent"
                fi
                ;;
            status)
                echo -e "${BLUE}=== Kinesis Agent Status ===${NC}"
                systemctl status aws-kinesis-agent --no-pager -l
                ;;
            logs)
                echo -e "${BLUE}=== Kinesis Agent Logs ===${NC}"
                journalctl -u aws-kinesis-agent -n 50 --no-pager
                ;;
        esac
    else
        log_warning "Kinesis Agent not installed"
        if [ "$1" = "status" ]; then
            echo "Status: Not installed"
            echo "Install with: aws ssm send-command --document-name agesic-dl-poc-install-agents --parameters agentType=kinesis_agent"
        fi
    fi
}

manage_fluentd() {
    if systemctl list-unit-files | grep -q td-agent; then
        case $1 in
            start)
                if systemctl start td-agent; then
                    log_success "Fluentd started"
                else
                    log_error "Failed to start Fluentd"
                fi
                ;;
            stop)
                if systemctl stop td-agent; then
                    log_success "Fluentd stopped"
                else
                    log_error "Failed to stop Fluentd"
                fi
                ;;
            restart)
                if systemctl restart td-agent; then
                    log_success "Fluentd restarted"
                else
                    log_error "Failed to restart Fluentd"
                fi
                ;;
            status)
                echo -e "${BLUE}=== Fluentd Status ===${NC}"
                systemctl status td-agent --no-pager -l
                ;;
            logs)
                echo -e "${BLUE}=== Fluentd Logs ===${NC}"
                journalctl -u td-agent -n 50 --no-pager
                ;;
        esac
    else
        log_warning "Fluentd not installed"
        if [ "$1" = "status" ]; then
            echo "Status: Not installed"
            echo "Install with: aws ssm send-command --document-name agesic-dl-poc-install-agents --parameters agentType=fluentd"
        fi
    fi
}

show_summary() {
    echo -e "${BLUE}=== AGESIC Data Lake F5 Bridge Agent Summary ===${NC}"
    echo "Date: $(date)"
    echo ""
    
    # Python processor
    if systemctl is-active f5-processor.timer >/dev/null 2>&1; then
        echo -e "Python Processor: ${GREEN}Active${NC}"
    else
        echo -e "Python Processor: ${RED}Inactive${NC}"
    fi
    
    # Kinesis Agent
    if systemctl list-unit-files | grep -q aws-kinesis-agent; then
        if systemctl is-active aws-kinesis-agent >/dev/null 2>&1; then
            echo -e "Kinesis Agent: ${GREEN}Active${NC}"
        else
            echo -e "Kinesis Agent: ${YELLOW}Installed but inactive${NC}"
        fi
    else
        echo -e "Kinesis Agent: ${RED}Not installed${NC}"
    fi
    
    # Fluentd
    if systemctl list-unit-files | grep -q td-agent; then
        if systemctl is-active td-agent >/dev/null 2>&1; then
            echo -e "Fluentd: ${GREEN}Active${NC}"
        else
            echo -e "Fluentd: ${YELLOW}Installed but inactive${NC}"
        fi
    else
        echo -e "Fluentd: ${RED}Not installed${NC}"
    fi
    
    echo ""
    echo -e "${BLUE}Configuration:${NC}"
    echo "Stream: ${KINESIS_STREAM_NAME:-Not set}"
    echo "Bucket: ${SOURCE_BUCKET:-Not set}"
    echo "File: ${SOURCE_FILE:-Not set}"
}

case $AGENT_TYPE in
    python)
        manage_python $ACTION
        ;;
    kinesis)
        manage_kinesis $ACTION
        ;;
    fluentd)
        manage_fluentd $ACTION
        ;;
    all)
        if [ "$ACTION" = "status" ]; then
            show_summary
        elif [ "$ACTION" = "logs" ]; then
            manage_python logs
            echo ""
            manage_kinesis logs
            echo ""
            manage_fluentd logs
        else
            log_info "Managing All Agents: $ACTION"
            manage_python $ACTION
            manage_kinesis $ACTION
            manage_fluentd $ACTION
        fi
        ;;
    *)
        usage
        ;;
esac
