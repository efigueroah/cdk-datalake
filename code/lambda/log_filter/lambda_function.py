import json
import base64
import gzip
import boto3
import re
from datetime import datetime
from typing import Dict, List, Any

# Initialize CloudWatch Logs client
cloudwatch_logs = boto3.client('logs')

# HTTP Combined Log Format regex pattern
# Format: IP - - [timestamp] "method path protocol" status size "referer" "user-agent"
COMBINED_LOG_PATTERN = re.compile(
    r'(?P<ip>\S+) \S+ \S+ \[(?P<timestamp>[^\]]+)\] "(?P<method>\S+) (?P<path>\S+) (?P<protocol>\S+)" (?P<status>\d+) (?P<size>\S+) "(?P<referer>[^"]*)" "(?P<user_agent>[^"]*)"'
)

# Error status codes and log levels to filter
ERROR_STATUS_CODES = ['4', '5']  # 4xx and 5xx status codes
ERROR_LOG_LEVELS = ['ERROR', 'WARN', 'CRITICAL', 'FATAL']

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to filter HTTP logs for ERROR/WARN entries
    and send them to CloudWatch Logs
    """
    
    log_group_name = f"/aws/lambda/agesic-dl-poc-error-logs"
    log_stream_name = f"error-stream-{datetime.now().strftime('%Y-%m-%d-%H')}"
    
    try:
        # Process Kinesis records
        error_logs = []
        
        for record in event['Records']:
            # Decode Kinesis data
            payload = base64.b64decode(record['kinesis']['data'])
            
            # Handle gzip compression if present
            try:
                if payload[:2] == b'\x1f\x8b':  # gzip magic number
                    payload = gzip.decompress(payload)
                log_data = payload.decode('utf-8')
            except Exception as e:
                print(f"Error decompressing data: {str(e)}")
                continue
            
            # Process each log line
            for line in log_data.strip().split('\n'):
                if line.strip():
                    error_log = process_log_line(line.strip())
                    if error_log:
                        error_logs.append(error_log)
        
        # Send error logs to CloudWatch if any found
        if error_logs:
            send_to_cloudwatch(log_group_name, log_stream_name, error_logs)
            print(f"Processed {len(error_logs)} error log entries")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Processed {len(error_logs)} error logs',
                'processed_records': len(event['Records'])
            })
        }
        
    except Exception as e:
        print(f"Error processing records: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def process_log_line(log_line: str) -> Dict[str, Any]:
    """
    Process a single log line and return structured data if it's an error
    """
    try:
        # Check if it's a structured log (JSON)
        if log_line.startswith('{'):
            try:
                log_json = json.loads(log_line)
                if is_error_log_json(log_json):
                    return {
                        'timestamp': datetime.now().isoformat(),
                        'original_log': log_line,
                        'log_type': 'structured',
                        'parsed_data': log_json
                    }
            except json.JSONDecodeError:
                pass
        
        # Try to parse as HTTP Combined Log Format
        match = COMBINED_LOG_PATTERN.match(log_line)
        if match:
            log_data = match.groupdict()
            
            # Check if it's an error status code
            if log_data['status'][0] in ERROR_STATUS_CODES:
                return {
                    'timestamp': datetime.now().isoformat(),
                    'original_log': log_line,
                    'log_type': 'http_combined',
                    'parsed_data': {
                        'ip': log_data['ip'],
                        'timestamp': log_data['timestamp'],
                        'method': log_data['method'],
                        'path': log_data['path'],
                        'status': int(log_data['status']),
                        'size': log_data['size'],
                        'referer': log_data['referer'],
                        'user_agent': log_data['user_agent'],
                        'error_type': 'client_error' if log_data['status'][0] == '4' else 'server_error'
                    }
                }
        
        # Check for error keywords in unstructured logs
        if any(level in log_line.upper() for level in ERROR_LOG_LEVELS):
            return {
                'timestamp': datetime.now().isoformat(),
                'original_log': log_line,
                'log_type': 'unstructured',
                'parsed_data': {
                    'contains_error_keyword': True
                }
            }
            
    except Exception as e:
        print(f"Error processing log line: {str(e)}")
    
    return None

def is_error_log_json(log_json: Dict[str, Any]) -> bool:
    """
    Check if a JSON log entry represents an error
    """
    # Check common log level fields
    level_fields = ['level', 'severity', 'log_level', 'priority']
    
    for field in level_fields:
        if field in log_json:
            level_value = str(log_json[field]).upper()
            if any(error_level in level_value for error_level in ERROR_LOG_LEVELS):
                return True
    
    # Check for HTTP status codes
    status_fields = ['status', 'status_code', 'http_status']
    for field in status_fields:
        if field in log_json:
            status = str(log_json[field])
            if len(status) >= 3 and status[0] in ERROR_STATUS_CODES:
                return True
    
    return False

def send_to_cloudwatch(log_group_name: str, log_stream_name: str, error_logs: List[Dict[str, Any]]):
    """
    Send error logs to CloudWatch Logs
    """
    try:
        # Create log group if it doesn't exist
        try:
            cloudwatch_logs.create_log_group(logGroupName=log_group_name)
        except cloudwatch_logs.exceptions.ResourceAlreadyExistsException:
            pass
        
        # Create log stream if it doesn't exist
        try:
            cloudwatch_logs.create_log_stream(
                logGroupName=log_group_name,
                logStreamName=log_stream_name
            )
        except cloudwatch_logs.exceptions.ResourceAlreadyExistsException:
            pass
        
        # Prepare log events
        log_events = []
        for error_log in error_logs:
            log_events.append({
                'timestamp': int(datetime.now().timestamp() * 1000),
                'message': json.dumps(error_log, ensure_ascii=False)
            })
        
        # Send logs to CloudWatch
        if log_events:
            cloudwatch_logs.put_log_events(
                logGroupName=log_group_name,
                logStreamName=log_stream_name,
                logEvents=log_events
            )
            
    except Exception as e:
        print(f"Error sending logs to CloudWatch: {str(e)}")
        raise
