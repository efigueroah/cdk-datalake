#!/usr/bin/env python3
"""
AGESIC Data Lake - F5 Log Processor
Downloads F5 logs from S3 and sends directly to Kinesis
Specialized regex parser for F5 access logs with 25+ fields
"""

import boto3
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

# F5 Log regex pattern with 25+ specific fields
F5_LOG_PATTERN = re.compile(
    r'(?P<timestamp_syslog>\w{3} \s+\d{1,2} \d{2}:\d{2}:\d{2}) '
    r'(?P<hostname>[^\s]+) '
    r'(?P<ip_cliente_externo>[^\s]+) '
    r'\[(?P<ip_backend_interno>[^\]]+)\] '
    r'(?P<usuario_autenticado>-|"[^"]*") '
    r'(?P<identidad>"[^"]*") '
    r'\[(?P<timestamp_rp>[^\]]+)\] '
    r'"(?P<metodo>\w+) (?P<request>[^"]+) (?P<protocolo>HTTP/\d\.\d)" '
    r'(?P<codigo_respuesta>\d+) '
    r'(?P<tamano_respuesta>\d+) '
    r'"(?P<referer>[^"]*)" '
    r'"(?P<user_agent>[^"]*)" '
    r'Time (?P<tiempo_respuesta_ms>\d+) '
    r'Age "(?P<edad_cache>[^"]*)" '
    r'"(?P<content_type>[^"]*)" '
    r'"(?P<jsession_id>[^"]*)" '
    r'(?P<campo_reservado_2>-|"[^"]*") '
    r'"(?P<f5_virtualserver>[^"]*)" '
    r'"(?P<f5_pool>[^"]*)" '
    r'(?P<f5_bigip_name>\w+)'
)

class F5LogProcessor:
    """F5 Log Processor with specialized parsing and Kinesis integration"""
    
    def __init__(self, source_bucket: str, source_file: str, local_dir: str):
        self.source_bucket = source_bucket
        self.source_file = source_file
        self.local_dir = local_dir
        self.s3_client = boto3.client('s3')
        
    def download_logs(self) -> str:
        """Download F5 logs from S3"""
        local_file = os.path.join(self.local_dir, f"f5_logs_{int(time.time())}.txt")
        
        try:
            print(f"Downloading s3://{self.source_bucket}/{self.source_file} to {local_file}")
            self.s3_client.download_file(self.source_bucket, self.source_file, local_file)
            print(f"Successfully downloaded {local_file}")
            return local_file
        except Exception as e:
            print(f"Error downloading file: {e}")
            raise
    
    def parse_f5_log(self, log_line: str) -> Optional[Dict]:
        """Parse F5 log line using specialized regex"""
        match = F5_LOG_PATTERN.match(log_line.strip())
        if not match:
            return None
            
        data = match.groupdict()
        
        # Convert numeric fields
        try:
            data['codigo_respuesta'] = int(data['codigo_respuesta'])
            data['tamano_respuesta'] = int(data['tamano_respuesta'])
            data['tiempo_respuesta_ms'] = int(data['tiempo_respuesta_ms'])
        except ValueError:
            pass
        
        # Add processing metadata
        data['processed_at'] = datetime.now().isoformat()
        data['log_type'] = 'f5_access'
        data['processor_version'] = '2.0'
        
        # Add analytics fields
        data['is_error'] = data['codigo_respuesta'] >= 400
        data['is_slow'] = data['tiempo_respuesta_ms'] > 1000
        data['status_category'] = self._categorize_status(data['codigo_respuesta'])
        data['response_time_category'] = self._categorize_response_time(data['tiempo_respuesta_ms'])
        
        return data
    
    def _categorize_status(self, status_code: int) -> str:
        """Categorize HTTP status codes"""
        if status_code < 300:
            return 'success'
        elif status_code < 400:
            return 'redirect'
        elif status_code < 500:
            return 'client_error'
        else:
            return 'server_error'
    
    def _categorize_response_time(self, response_time_ms: int) -> str:
        """Categorize response times"""
        if response_time_ms < 100:
            return 'fast'
        elif response_time_ms < 500:
            return 'normal'
        elif response_time_ms < 1000:
            return 'slow'
        else:
            return 'very_slow'
    
    def send_to_kinesis_direct(self, file_path: str, stream_name: str, max_records: int = 1000) -> int:
        """Send processed logs directly to Kinesis with batch optimization"""
        kinesis_client = boto3.client('kinesis')
        sent_count = 0
        failed_count = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8') as infile:
                records = []
                
                for line_num, line in enumerate(infile, 1):
                    if line.strip():
                        parsed = self.parse_f5_log(line)
                        if parsed:
                            records.append({
                                'Data': json.dumps(parsed, ensure_ascii=False).encode('utf-8'),
                                'PartitionKey': str(line_num % 10)
                            })
                        
                        # Send in batches of 500 (Kinesis limit)
                        if len(records) >= 500:
                            response = kinesis_client.put_records(
                                Records=records,
                                StreamName=stream_name
                            )
                            batch_failed = response.get('FailedRecordCount', 0)
                            batch_sent = len(records) - batch_failed
                            sent_count += batch_sent
                            failed_count += batch_failed
                            records = []
                            print(f"Sent batch: {batch_sent} successful, {batch_failed} failed. Total sent: {sent_count}")
                            
                        if max_records and sent_count >= max_records:
                            break
                
                # Send remaining records
                if records:
                    response = kinesis_client.put_records(
                        Records=records,
                        StreamName=stream_name
                    )
                    batch_failed = response.get('FailedRecordCount', 0)
                    batch_sent = len(records) - batch_failed
                    sent_count += batch_sent
                    failed_count += batch_failed
            
            print(f"Processing completed: {sent_count} records sent, {failed_count} failed")
            return sent_count
            
        except Exception as e:
            print(f"Error sending to Kinesis: {e}")
            raise

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='AGESIC F5 Log Processor')
    parser.add_argument('--stats', action='store_true', help='Show processing statistics')
    parser.add_argument('--max-records', type=int, default=5000, help='Maximum records to send to Kinesis')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    source_bucket = os.environ.get('SOURCE_BUCKET', 'rawdata-analytics-poc-voh9ai')
    source_file = os.environ.get('SOURCE_FILE', 'extracto_logs_acceso_f5_portalgubuy.txt')
    local_dir = os.environ.get('LOCAL_LOG_DIR', '/var/log/logs_f5')
    kinesis_stream = os.environ.get('KINESIS_STREAM_NAME', 'agesic-dl-poc-streaming-DataStream6F9DAC72-guBUYFNpPRE3')
    
    if args.stats:
        print("=== F5 Log Processing Statistics ===")
        print(f"Source: s3://{source_bucket}/{source_file}")
        print(f"Local directory: {local_dir}")
        print(f"Kinesis stream: {kinesis_stream}")
        print(f"Max records: {args.max_records}")
        
        if os.path.exists(local_dir):
            files = os.listdir(local_dir)
            print(f"Local files: {len(files)}")
            for f in files:
                file_path = os.path.join(local_dir, f)
                size = os.path.getsize(file_path)
                print(f"  {f}: {size} bytes")
        return
    
    processor = F5LogProcessor(source_bucket, source_file, local_dir)
    
    try:
        if args.verbose:
            print("Starting F5 log processing...")
        
        local_file = processor.download_logs()
        sent_count = processor.send_to_kinesis_direct(local_file, kinesis_stream, args.max_records)
        
        print(f"Processing completed successfully. {sent_count} records sent to Kinesis.")
        
    except Exception as e:
        print(f"Error in main processing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
