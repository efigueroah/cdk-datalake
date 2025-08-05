#!/bin/bash

# AGESIC Data Lake PoC - EC2 UserData Script
# This script sets up an EC2 instance to simulate Apache HTTP log generation
# and send data to Kinesis Data Stream

# Update system
yum update -y

# Install required packages
yum install -y python3 python3-pip awscli jq

# Install Python packages
pip3 install boto3 faker

# Create application directory
mkdir -p /opt/agesic-datalake
cd /opt/agesic-datalake

# Create configuration file
cat > /opt/agesic-datalake/config.json << 'EOF'
{
  "kinesis": {
    "stream_name": "agesic-dl-poc-data-stream",
    "partition_key": "log-simulator"
  },
  "generation": {
    "max_logs": 1000,
    "duration_minutes": 60,
    "interval_min_seconds": 1,
    "interval_max_seconds": 5,
    "batch_size": 1
  },
  "logging": {
    "level": "INFO",
    "log_every_n_records": 100
  },
  "simulation": {
    "error_rate_percent": 15,
    "paths": [
      "/", "/index.html", "/about.html", "/contact.html", "/products.html",
      "/api/users", "/api/products", "/api/orders", "/api/health",
      "/images/logo.png", "/css/style.css", "/js/app.js",
      "/admin/login", "/admin/dashboard", "/admin/users",
      "/search", "/login", "/logout", "/profile", "/settings"
    ],
    "status_codes": {
      "200": 60, "201": 5, "204": 5,
      "301": 3, "302": 2,
      "400": 5, "401": 3, "403": 4, "404": 8,
      "500": 3, "502": 1, "503": 1
    }
  }
}
EOF

# Create log generator script
cat > /opt/agesic-datalake/log_generator.py << 'EOF'
#!/usr/bin/env python3
import json
import time
import random
import boto3
import argparse
import signal
import sys
from datetime import datetime, timedelta
from faker import Faker
import logging
import os

# Global flag for graceful shutdown
shutdown_flag = False

def signal_handler(signum, frame):
    global shutdown_flag
    print(f"\nReceived signal {signum}. Shutting down gracefully...")
    shutdown_flag = True

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

class LogGenerator:
    def __init__(self, config_file='config.json'):
        self.config = self.load_config(config_file)
        self.setup_logging()
        self.fake = Faker()
        self.kinesis_client = boto3.client('kinesis')
        self.stats = {
            'total_sent': 0,
            'total_errors': 0,
            'start_time': datetime.now()
        }
        
    def load_config(self, config_file):
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Override with environment variables if present
            if os.getenv('KINESIS_STREAM_NAME'):
                config['kinesis']['stream_name'] = os.getenv('KINESIS_STREAM_NAME')
                
            return config
        except FileNotFoundError:
            print(f"Configuration file {config_file} not found. Using defaults.")
            return self.get_default_config()
        except json.JSONDecodeError as e:
            print(f"Error parsing configuration file: {e}. Using defaults.")
            return self.get_default_config()
    
    def get_default_config(self):
        """Return default configuration"""
        return {
            "kinesis": {
                "stream_name": "agesic-dl-poc-data-stream",
                "partition_key": "log-simulator"
            },
            "generation": {
                "max_logs": 1000,
                "duration_minutes": 60,
                "interval_min_seconds": 1,
                "interval_max_seconds": 5,
                "batch_size": 1
            },
            "logging": {
                "level": "INFO",
                "log_every_n_records": 100
            },
            "simulation": {
                "error_rate_percent": 15,
                "paths": ["/", "/index.html", "/api/health"],
                "status_codes": {"200": 70, "404": 20, "500": 10}
            }
        }
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_level = getattr(logging, self.config['logging']['level'].upper())
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('/opt/agesic-datalake/generator.log')
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def weighted_choice(self, choices_dict):
        """Select item based on weights from dictionary"""
        choices = list(choices_dict.items())
        total = sum(weight for choice, weight in choices)
        r = random.uniform(0, total)
        upto = 0
        for choice, weight in choices:
            if upto + weight >= r:
                return choice
            upto += weight
        return list(choices_dict.keys())[-1]
    
    def generate_apache_log(self):
        """Generate a realistic Apache Combined Log Format entry"""
        try:
            # Generate components
            ip = self.fake.ipv4()
            timestamp = datetime.now().strftime('%d/%b/%Y:%H:%M:%S +0000')
            
            method = random.choice(['GET', 'POST', 'PUT', 'DELETE'])
            path = random.choice(self.config['simulation']['paths'])
            protocol = 'HTTP/1.1'
            
            # Determine if this should be an error based on error rate
            should_be_error = random.randint(1, 100) <= self.config['simulation']['error_rate_percent']
            
            if should_be_error:
                # Filter status codes to errors only
                error_codes = {k: v for k, v in self.config['simulation']['status_codes'].items() 
                             if int(k) >= 400}
                status = int(self.weighted_choice(error_codes)) if error_codes else 404
            else:
                # Filter status codes to success only
                success_codes = {k: v for k, v in self.config['simulation']['status_codes'].items() 
                               if int(k) < 400}
                status = int(self.weighted_choice(success_codes)) if success_codes else 200
            
            size = random.randint(200, 50000) if status < 400 else random.randint(100, 5000)
            referer = random.choice(['-', 'http://example.com/', 'https://google.com/'])
            user_agent = random.choice([
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15'
            ])
            
            # Format as Apache Combined Log
            log_entry = f'{ip} - - [{timestamp}] "{method} {path} {protocol}" {status} {size} "{referer}" "{user_agent}"'
            
            return log_entry
            
        except Exception as e:
            self.logger.error(f"Error generating log entry: {str(e)}")
            return None
    
    def send_to_kinesis(self, log_entry):
        """Send log entry to Kinesis Data Stream"""
        try:
            # Create JSON payload
            payload = {
                'message': log_entry,
                'timestamp': datetime.now().isoformat(),
                'source': 'apache-simulator'
            }
            
            # Send to Kinesis
            response = self.kinesis_client.put_record(
                StreamName=self.config['kinesis']['stream_name'],
                Data=json.dumps(payload),
                PartitionKey=self.config['kinesis']['partition_key']
            )
            
            self.logger.debug(f"Sent to Kinesis: {response['SequenceNumber']}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending to Kinesis: {str(e)}")
            return False
    
    def print_stats(self):
        """Print current statistics"""
        elapsed = datetime.now() - self.stats['start_time']
        rate = self.stats['total_sent'] / elapsed.total_seconds() if elapsed.total_seconds() > 0 else 0
        
        print(f"\n=== STATISTICS ===")
        print(f"Total logs sent: {self.stats['total_sent']}")
        print(f"Total errors: {self.stats['total_errors']}")
        print(f"Success rate: {((self.stats['total_sent'] - self.stats['total_errors']) / max(self.stats['total_sent'], 1) * 100):.1f}%")
        print(f"Elapsed time: {elapsed}")
        print(f"Rate: {rate:.2f} logs/second")
        print(f"Stream: {self.config['kinesis']['stream_name']}")
        print("==================\n")
    
    def run(self, max_logs=None, duration_minutes=None):
        """Main execution method"""
        global shutdown_flag
        
        # Use parameters or config defaults
        max_logs = max_logs or self.config['generation']['max_logs']
        duration_minutes = duration_minutes or self.config['generation']['duration_minutes']
        
        self.logger.info(f"Starting log generator for stream: {self.config['kinesis']['stream_name']}")
        self.logger.info(f"Max logs: {max_logs}, Duration: {duration_minutes} minutes")
        
        # Test Kinesis connection
        try:
            self.kinesis_client.describe_stream(StreamName=self.config['kinesis']['stream_name'])
            self.logger.info("Successfully connected to Kinesis stream")
        except Exception as e:
            self.logger.error(f"Cannot connect to Kinesis stream: {str(e)}")
            return
        
        # Calculate end time
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        
        # Generate logs
        while not shutdown_flag and self.stats['total_sent'] < max_logs and datetime.now() < end_time:
            try:
                # Generate log entry
                log_entry = self.generate_apache_log()
                if not log_entry:
                    continue
                
                # Send to Kinesis
                if self.send_to_kinesis(log_entry):
                    self.stats['total_sent'] += 1
                    
                    # Log progress
                    if self.stats['total_sent'] % self.config['logging']['log_every_n_records'] == 0:
                        self.logger.info(f"Sent {self.stats['total_sent']} log entries (errors: {self.stats['total_errors']})")
                else:
                    self.stats['total_errors'] += 1
                
                # Wait between entries
                interval = random.uniform(
                    self.config['generation']['interval_min_seconds'],
                    self.config['generation']['interval_max_seconds']
                )
                time.sleep(interval)
                
            except KeyboardInterrupt:
                self.logger.info("Received interrupt signal...")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error: {str(e)}")
                self.stats['total_errors'] += 1
                time.sleep(5)  # Wait before retrying
        
        # Final statistics
        self.print_stats()
        
        if shutdown_flag:
            self.logger.info("Log generator stopped by signal")
        elif self.stats['total_sent'] >= max_logs:
            self.logger.info(f"Log generator completed: reached max logs ({max_logs})")
        elif datetime.now() >= end_time:
            self.logger.info(f"Log generator completed: reached time limit ({duration_minutes} minutes)")

def main():
    parser = argparse.ArgumentParser(description='AGESIC Data Lake Log Generator')
    parser.add_argument('--config', '-c', default='config.json', help='Configuration file path')
    parser.add_argument('--max-logs', '-n', type=int, help='Maximum number of logs to generate')
    parser.add_argument('--duration', '-d', type=int, help='Duration in minutes')
    parser.add_argument('--stats', '-s', action='store_true', help='Show current statistics and exit')
    
    args = parser.parse_args()
    
    if args.stats:
        # Show stats from log file if exists
        log_file = '/opt/agesic-datalake/generator.log'
        if os.path.exists(log_file):
            print("Recent log entries:")
            os.system(f"tail -20 {log_file}")
        else:
            print("No log file found.")
        return
    
    # Create and run generator
    generator = LogGenerator(args.config)
    generator.run(max_logs=args.max_logs, duration_minutes=args.duration)

if __name__ == "__main__":
    main()
EOF

# Make script executable
chmod +x /opt/agesic-datalake/log_generator.py

# Create control scripts
cat > /opt/agesic-datalake/start_generator.sh << 'EOF'
#!/bin/bash
# Start log generator with custom parameters

CONFIG_FILE="/opt/agesic-datalake/config.json"
SCRIPT_DIR="/opt/agesic-datalake"

echo "=== AGESIC Data Lake Log Generator ==="
echo "Configuration file: $CONFIG_FILE"
echo ""

# Check if config exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Configuration file not found at $CONFIG_FILE"
    exit 1
fi

# Show current configuration
echo "Current configuration:"
cat "$CONFIG_FILE" | jq '.'
echo ""

# Ask for parameters
read -p "Enter max number of logs (default from config): " MAX_LOGS
read -p "Enter duration in minutes (default from config): " DURATION

# Build command
CMD="python3 $SCRIPT_DIR/log_generator.py -c $CONFIG_FILE"

if [ ! -z "$MAX_LOGS" ]; then
    CMD="$CMD --max-logs $MAX_LOGS"
fi

if [ ! -z "$DURATION" ]; then
    CMD="$CMD --duration $DURATION"
fi

echo ""
echo "Starting log generator with command:"
echo "$CMD"
echo ""
echo "Press Ctrl+C to stop the generator"
echo "=================================="

# Execute
cd $SCRIPT_DIR
exec $CMD
EOF

chmod +x /opt/agesic-datalake/start_generator.sh

# Create configuration editor script
cat > /opt/agesic-datalake/edit_config.sh << 'EOF'
#!/bin/bash
# Edit configuration file

CONFIG_FILE="/opt/agesic-datalake/config.json"

echo "=== Configuration Editor ==="
echo "Current configuration:"
echo ""
cat "$CONFIG_FILE" | jq '.'
echo ""

read -p "Do you want to edit the configuration? (y/N): " EDIT

if [[ $EDIT =~ ^[Yy]$ ]]; then
    # Backup current config
    cp "$CONFIG_FILE" "${CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    
    # Edit with nano (or vi if nano not available)
    if command -v nano &> /dev/null; then
        nano "$CONFIG_FILE"
    else
        vi "$CONFIG_FILE"
    fi
    
    # Validate JSON
    if jq empty "$CONFIG_FILE" 2>/dev/null; then
        echo "Configuration updated successfully!"
    else
        echo "Error: Invalid JSON format. Restoring backup..."
        cp "${CONFIG_FILE}.backup."* "$CONFIG_FILE" 2>/dev/null || true
    fi
else
    echo "Configuration not modified."
fi
EOF

chmod +x /opt/agesic-datalake/edit_config.sh

# Create status/monitoring script
cat > /opt/agesic-datalake/status.sh << 'EOF'
#!/bin/bash
# Show system status and recent logs

echo "=== AGESIC Data Lake System Status ==="
echo ""

echo "1. System Resources:"
echo "   Memory: $(free -h | grep Mem | awk '{print $3 "/" $2}')"
echo "   Disk: $(df -h / | tail -1 | awk '{print $3 "/" $2 " (" $5 " used)"}')"
echo ""

echo "2. AWS Connectivity:"
aws sts get-caller-identity --output table 2>/dev/null || echo "   AWS CLI not configured or no connectivity"
echo ""

echo "3. Kinesis Stream Status:"
STREAM_NAME=$(cat /opt/agesic-datalake/config.json | jq -r '.kinesis.stream_name')
aws kinesis describe-stream --stream-name "$STREAM_NAME" --query 'StreamDescription.StreamStatus' --output text 2>/dev/null || echo "   Cannot connect to Kinesis stream"
echo ""

echo "4. Recent Generator Activity:"
if [ -f "/opt/agesic-datalake/generator.log" ]; then
    echo "   Last 10 log entries:"
    tail -10 /opt/agesic-datalake/generator.log
else
    echo "   No generator log found"
fi
echo ""

echo "5. Available Commands:"
echo "   ./start_generator.sh  - Start log generation"
echo "   ./edit_config.sh      - Edit configuration"
echo "   ./status.sh           - Show this status"
echo "   python3 log_generator.py --stats  - Show generator statistics"
echo ""
EOF

chmod +x /opt/agesic-datalake/status.sh

# Create README for users
cat > /opt/agesic-datalake/README.md << 'EOF'
# AGESIC Data Lake Log Generator

## Overview
This directory contains the log generator for the AGESIC Data Lake PoC. The generator creates realistic Apache HTTP Combined Log Format entries and sends them to Amazon Kinesis Data Stream.

## Files
- `log_generator.py` - Main Python script for log generation
- `config.json` - Configuration file with all parameters
- `start_generator.sh` - Interactive script to start generation
- `edit_config.sh` - Script to edit configuration
- `status.sh` - System status and monitoring
- `generator.log` - Log file (created when generator runs)

## Quick Start

### 1. Check System Status
```bash
./status.sh
```

### 2. Start Log Generation (Interactive)
```bash
./start_generator.sh
```

### 3. Start with Specific Parameters
```bash
# Generate 500 logs
python3 log_generator.py --max-logs 500

# Run for 30 minutes
python3 log_generator.py --duration 30

# Both parameters
python3 log_generator.py --max-logs 1000 --duration 60
```

### 4. Edit Configuration
```bash
./edit_config.sh
```

### 5. View Statistics
```bash
python3 log_generator.py --stats
```

## Configuration Parameters

The `config.json` file contains:

- **kinesis**: Stream name and partition key
- **generation**: Max logs, duration, intervals
- **logging**: Log level and frequency
- **simulation**: Error rates, paths, status codes

## Monitoring

- Generator logs: `tail -f generator.log`
- System status: `./status.sh`
- AWS CloudWatch: Monitor Kinesis metrics in AWS Console

## Stopping Generation

Press `Ctrl+C` to gracefully stop the generator. It will show final statistics before exiting.
EOF

# Set ownership
chown -R ec2-user:ec2-user /opt/agesic-datalake

# Create systemd service (disabled by default)
cat > /etc/systemd/system/agesic-log-generator.service << 'EOF'
[Unit]
Description=AGESIC Data Lake Log Generator
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/opt/agesic-datalake
ExecStart=/usr/bin/python3 /opt/agesic-datalake/log_generator.py
Restart=no
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd but DO NOT enable or start the service
systemctl daemon-reload

# Create welcome message
cat > /etc/motd << 'EOF'

=== AGESIC Data Lake PoC - Log Generator Instance ===

Welcome! This instance is configured to generate Apache HTTP logs
and send them to Kinesis Data Stream.

Quick Start:
  cd /opt/agesic-datalake
  ./status.sh              # Check system status
  ./start_generator.sh     # Start interactive log generation

For more information, see: /opt/agesic-datalake/README.md

========================================================

EOF

# Log completion
echo "$(date): AGESIC Data Lake EC2 setup completed - Manual start mode" >> /var/log/agesic-setup.log
echo "Log generator is ready but NOT started automatically." >> /var/log/agesic-setup.log
echo "Users must connect via SSM and start manually." >> /var/log/agesic-setup.log
