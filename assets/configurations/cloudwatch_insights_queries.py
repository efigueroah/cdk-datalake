# CLOUDWATCH INSIGHTS QUERIES FOR AGESIC DATA LAKE POC

# Query 1: Error Analysis
ERROR_ANALYSIS_INSIGHTS_QUERY = """
fields @timestamp, parsed_data.status_code, parsed_data.client_ip, parsed_data.request_path
| filter parsed_data.is_error = true
| stats count() by parsed_data.status_code
| sort count desc
"""

# Query 2: Top Error IPs
TOP_ERROR_IPS_INSIGHTS_QUERY = """
fields @timestamp, parsed_data.client_ip, parsed_data.status_code, parsed_data.request_path
| filter parsed_data.is_error = true
| stats count() by parsed_data.client_ip
| sort count desc
| limit 20
"""

# Query 3: Error Timeline
ERROR_TIMELINE_INSIGHTS_QUERY = """
fields @timestamp, parsed_data.status_code, parsed_data.status_category
| filter parsed_data.is_error = true
| stats count() by bin(5m)
| sort @timestamp desc
"""
