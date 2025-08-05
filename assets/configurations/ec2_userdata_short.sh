#!/bin/bash
# AGESIC Data Lake PoC - EC2 UserData Script (Short Version)

# Update system and install packages
yum update -y
yum install -y python3 python3-pip awscli jq

# Install Python packages
pip3 install boto3 faker

# Create application directory
mkdir -p /opt/agesic-datalake
cd /opt/agesic-datalake

# Download full setup from S3 or create minimal setup
cat > config.json << 'EOF'
{
  "kinesis": {"stream_name": "agesic-dl-poc-data-stream", "partition_key": "log-simulator"},
  "generation": {"max_logs": 1000, "duration_minutes": 60, "interval_min_seconds": 1, "interval_max_seconds": 5},
  "simulation": {"error_rate_percent": 15, "paths": ["/", "/api/health", "/admin"], "status_codes": {"200": 70, "404": 20, "500": 10}}
}
EOF

# Create minimal log generator
cat > log_generator.py << 'EOF'
#!/usr/bin/env python3
import json, time, random, boto3, sys
from datetime import datetime
from faker import Faker

class LogGenerator:
    def __init__(self):
        with open('config.json') as f:
            self.config = json.load(f)
        self.fake = Faker()
        self.kinesis = boto3.client('kinesis')
        
    def generate_log(self):
        ip = self.fake.ipv4()
        timestamp = datetime.now().strftime('%d/%b/%Y:%H:%M:%S +0000')
        path = random.choice(self.config['simulation']['paths'])
        status = random.choice(list(self.config['simulation']['status_codes'].keys()))
        size = random.randint(200, 5000)
        return f'{ip} - - [{timestamp}] "GET {path} HTTP/1.1" {status} {size} "-" "Mozilla/5.0"'
    
    def run(self):
        stream = self.config['kinesis']['stream_name']
        print(f"Starting log generator for stream: {stream}")
        
        for i in range(self.config['generation']['max_logs']):
            try:
                log = self.generate_log()
                self.kinesis.put_record(
                    StreamName=stream,
                    Data=json.dumps({'message': log, 'timestamp': datetime.now().isoformat()}),
                    PartitionKey=self.config['kinesis']['partition_key']
                )
                if i % 100 == 0:
                    print(f"Sent {i} logs")
                time.sleep(random.uniform(1, 5))
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)

if __name__ == "__main__":
    LogGenerator().run()
EOF

chmod +x log_generator.py
chown -R ec2-user:ec2-user /opt/agesic-datalake

# Create simple start script
cat > start_generator.sh << 'EOF'
#!/bin/bash
cd /opt/agesic-datalake
python3 log_generator.py
EOF

chmod +x start_generator.sh

echo "AGESIC Data Lake setup completed" > /var/log/agesic-setup.log
