import json
import base64
import gzip
import boto3
import re
from datetime import datetime
from typing import Dict, List, Any, Optional

# Initialize AWS clients
cloudwatch_logs = boto3.client('logs')
cloudwatch = boto3.client('cloudwatch')

# F5 Log Format regex pattern (from espec_portales_2.re)
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

# Error status codes and performance thresholds
ERROR_STATUS_CODES = ['4', '5']  # 4xx and 5xx status codes
SLOW_RESPONSE_THRESHOLD_MS = 5000  # 5 seconds
LARGE_RESPONSE_THRESHOLD_BYTES = 10 * 1024 * 1024  # 10MB

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to filter F5 logs for ERROR/WARN entries and performance issues
    and send them to CloudWatch Logs
    """
    
    log_group_name = f"/aws/lambda/agesic-dl-poc-f5-error-logs"
    log_stream_name = f"f5-error-stream-{datetime.now().strftime('%Y-%m-%d-%H')}"
    
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
            
            # Process each log line or JSON record
            try:
                # Try to parse as JSON first (from Kinesis Agent)
                if log_data.strip().startswith('{'):
                    json_data = json.loads(log_data.strip())
                    # Extract the actual log line if it's wrapped
                    if 'message' in json_data:
                        log_line = json_data['message']
                    else:
                        log_line = log_data.strip()
                else:
                    log_line = log_data.strip()
                
                # Process the log line
                for line in log_line.split('\n'):
                    if line.strip():
                        error_log = process_f5_log_line(line.strip())
                        if error_log:
                            error_logs.append(error_log)
                            
            except json.JSONDecodeError:
                # Not JSON, process as plain text
                for line in log_data.strip().split('\n'):
                    if line.strip():
                        error_log = process_f5_log_line(line.strip())
                        if error_log:
                            error_logs.append(error_log)
        
        # Send error logs to CloudWatch if any found
        if error_logs:
            send_to_cloudwatch(log_group_name, log_stream_name, error_logs)
            print(f"Processed {len(error_logs)} F5 error/performance log entries")
        
        # Send custom metrics to CloudWatch
        send_f5_metrics_to_cloudwatch(error_logs)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Processed {len(error_logs)} F5 error logs',
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

def process_f5_log_line(log_line: str) -> Optional[Dict[str, Any]]:
    """
    Process a single F5 log line and return structured data if it's an error or performance issue
    """
    try:
        # Try to parse as F5 log format
        match = F5_LOG_PATTERN.match(log_line)
        if match:
            log_data = match.groupdict()
            
            # Convert numeric fields
            try:
                status_code = int(log_data['codigo_respuesta'])
                response_size = int(log_data['tamano_respuesta'])
                response_time_ms = int(log_data['tiempo_respuesta_ms'])
            except ValueError:
                return None
            
            # Determine if this is an error or performance issue
            is_error = False
            error_reasons = []
            
            # Check for HTTP error status codes
            if str(status_code)[0] in ERROR_STATUS_CODES:
                is_error = True
                error_type = 'client_error' if str(status_code)[0] == '4' else 'server_error'
                error_reasons.append(f"HTTP {status_code} ({error_type})")
            
            # Check for slow responses
            if response_time_ms > SLOW_RESPONSE_THRESHOLD_MS:
                is_error = True
                error_reasons.append(f"Slow response: {response_time_ms}ms (threshold: {SLOW_RESPONSE_THRESHOLD_MS}ms)")
            
            # Check for large responses (potential performance issue)
            if response_size > LARGE_RESPONSE_THRESHOLD_BYTES:
                is_error = True
                error_reasons.append(f"Large response: {response_size} bytes (threshold: {LARGE_RESPONSE_THRESHOLD_BYTES} bytes)")
            
            # Return structured error log if any issues found
            if is_error:
                return {
                    'timestamp': datetime.now().isoformat(),
                    'original_log': log_line,
                    'log_type': 'f5_access',
                    'error_reasons': error_reasons,
                    'parsed_data': {
                        'timestamp_syslog': log_data['timestamp_syslog'],
                        'hostname': log_data['hostname'],
                        'ip_cliente_externo': log_data['ip_cliente_externo'],
                        'ip_backend_interno': log_data['ip_backend_interno'],
                        'timestamp_rp': log_data['timestamp_rp'],
                        'metodo': log_data['metodo'],
                        'request': log_data['request'],
                        'protocolo': log_data['protocolo'],
                        'codigo_respuesta': status_code,
                        'tamano_respuesta': response_size,
                        'referer': log_data['referer'],
                        'user_agent': log_data['user_agent'],
                        'tiempo_respuesta_ms': response_time_ms,
                        'edad_cache': log_data['edad_cache'],
                        'content_type': log_data['content_type'],
                        'jsession_id': log_data['jsession_id'],
                        'f5_virtualserver': log_data['f5_virtualserver'],
                        'f5_pool': log_data['f5_pool'],
                        'f5_bigip_name': log_data['f5_bigip_name'],
                        'error_category': determine_error_category(status_code, response_time_ms, response_size)
                    }
                }
        
        # If not F5 format, check for generic error patterns
        error_keywords = ['ERROR', 'CRITICAL', 'FATAL', 'EXCEPTION', 'FAILED']
        if any(keyword in log_line.upper() for keyword in error_keywords):
            return {
                'timestamp': datetime.now().isoformat(),
                'original_log': log_line,
                'log_type': 'f5_generic_error',
                'error_reasons': ['Contains error keyword'],
                'parsed_data': {
                    'contains_error_keyword': True,
                    'detected_keywords': [kw for kw in error_keywords if kw in log_line.upper()]
                }
            }
            
    except Exception as e:
        print(f"Error processing F5 log line: {str(e)}")
    
    return None

def determine_error_category(status_code: int, response_time_ms: int, response_size: int) -> str:
    """
    Determine the category of error based on metrics
    """
    categories = []
    
    if 400 <= status_code < 500:
        categories.append('client_error')
    elif status_code >= 500:
        categories.append('server_error')
    
    if response_time_ms > SLOW_RESPONSE_THRESHOLD_MS:
        categories.append('performance_slow')
    
    if response_size > LARGE_RESPONSE_THRESHOLD_BYTES:
        categories.append('performance_large')
    
    return ','.join(categories) if categories else 'unknown'

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
        
        # Send logs to CloudWatch in batches (CloudWatch has a limit of 10,000 events per request)
        batch_size = 1000
        for i in range(0, len(log_events), batch_size):
            batch = log_events[i:i + batch_size]
            cloudwatch_logs.put_log_events(
                logGroupName=log_group_name,
                logStreamName=log_stream_name,
                logEvents=batch
            )
            
    except Exception as e:
        print(f"Error sending logs to CloudWatch: {str(e)}")
        raise

def send_f5_metrics_to_cloudwatch(error_logs: List[Dict[str, Any]]):
    """
    Send F5-specific custom metrics to CloudWatch
    """
    try:
        if not error_logs:
            return
        
        # Aggregate metrics by F5 components
        metrics_data = {}
        
        for error_log in error_logs:
            parsed_data = error_log.get('parsed_data', {})
            f5_env = parsed_data.get('f5_bigip_name', 'UNKNOWN')
            f5_pool = parsed_data.get('f5_pool', 'UNKNOWN')
            f5_vs = parsed_data.get('f5_virtualserver', 'UNKNOWN')
            response_time = parsed_data.get('tiempo_respuesta_ms', 0)
            status_code = parsed_data.get('codigo_respuesta', 0)
            
            # Initialize metrics structure
            key = f"{f5_env}|{f5_pool}|{f5_vs}"
            if key not in metrics_data:
                metrics_data[key] = {
                    'f5_env': f5_env,
                    'f5_pool': f5_pool,
                    'f5_vs': f5_vs,
                    'total_requests': 0,
                    'error_requests': 0,
                    'slow_requests': 0,
                    'response_times': [],
                    'status_codes': []
                }
            
            # Aggregate data
            metrics_data[key]['total_requests'] += 1
            metrics_data[key]['response_times'].append(response_time)
            metrics_data[key]['status_codes'].append(status_code)
            
            if str(status_code)[0] in ERROR_STATUS_CODES:
                metrics_data[key]['error_requests'] += 1
            
            if response_time > SLOW_RESPONSE_THRESHOLD_MS:
                metrics_data[key]['slow_requests'] += 1
        
        # Send metrics to CloudWatch
        metric_data = []
        timestamp = datetime.now()
        
        for key, data in metrics_data.items():
            f5_env = data['f5_env']
            f5_pool = data['f5_pool']
            total_requests = data['total_requests']
            error_requests = data['error_requests']
            slow_requests = data['slow_requests']
            response_times = data['response_times']
            
            # Calculate metrics
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            error_rate = (error_requests / total_requests * 100) if total_requests > 0 else 0
            slow_rate = (slow_requests / total_requests * 100) if total_requests > 0 else 0
            
            # Calculate P95 response time
            if response_times:
                sorted_times = sorted(response_times)
                p95_index = int(0.95 * len(sorted_times))
                p95_response_time = sorted_times[p95_index] if p95_index < len(sorted_times) else sorted_times[-1]
            else:
                p95_response_time = 0
            
            # Pool health score (100 - error_rate - slow_rate/2)
            pool_health_score = max(0, 100 - error_rate - (slow_rate / 2))
            
            # Request Count
            metric_data.append({
                'MetricName': 'RequestCount',
                'Dimensions': [
                    {'Name': 'F5Environment', 'Value': f5_env},
                    {'Name': 'Pool', 'Value': f5_pool}
                ],
                'Value': total_requests,
                'Unit': 'Count',
                'Timestamp': timestamp
            })
            
            # Average Response Time
            metric_data.append({
                'MetricName': 'AverageResponseTime',
                'Dimensions': [
                    {'Name': 'F5Environment', 'Value': f5_env},
                    {'Name': 'Pool', 'Value': f5_pool}
                ],
                'Value': avg_response_time,
                'Unit': 'Milliseconds',
                'Timestamp': timestamp
            })
            
            # P95 Response Time
            metric_data.append({
                'MetricName': 'P95ResponseTime',
                'Dimensions': [
                    {'Name': 'F5Environment', 'Value': f5_env},
                    {'Name': 'Pool', 'Value': f5_pool}
                ],
                'Value': p95_response_time,
                'Unit': 'Milliseconds',
                'Timestamp': timestamp
            })
            
            # Error Rate
            metric_data.append({
                'MetricName': 'ErrorRate',
                'Dimensions': [
                    {'Name': 'F5Environment', 'Value': f5_env},
                    {'Name': 'Pool', 'Value': f5_pool}
                ],
                'Value': error_rate,
                'Unit': 'Percent',
                'Timestamp': timestamp
            })
            
            # Pool Health Score
            metric_data.append({
                'MetricName': 'PoolHealthScore',
                'Dimensions': [
                    {'Name': 'F5Environment', 'Value': f5_env},
                    {'Name': 'Pool', 'Value': f5_pool}
                ],
                'Value': pool_health_score,
                'Unit': 'Percent',
                'Timestamp': timestamp
            })
        
        # Send metrics in batches (CloudWatch limit is 20 metrics per request)
        batch_size = 20
        for i in range(0, len(metric_data), batch_size):
            batch = metric_data[i:i + batch_size]
            cloudwatch.put_metric_data(
                Namespace='AGESIC/F5Logs',
                MetricData=batch
            )
        
        print(f"Sent {len(metric_data)} custom metrics to CloudWatch")
        
    except Exception as e:
        print(f"Error sending F5 metrics to CloudWatch: {str(e)}")
        # Don't raise exception to avoid breaking the main flow
