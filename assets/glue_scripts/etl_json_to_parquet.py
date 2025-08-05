import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.sql import functions as F
from pyspark.sql.types import *
import re
from datetime import datetime

# Initialize Glue context
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'raw_bucket',
    'processed_bucket',
    'solution_name'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# HTTP Combined Log Format regex pattern
COMBINED_LOG_PATTERN = r'(?P<ip>\S+) \S+ \S+ \[(?P<timestamp>[^\]]+)\] "(?P<method>\S+) (?P<path>\S+) (?P<protocol>\S+)" (?P<status>\d+) (?P<size>\S+) "(?P<referer>[^"]*)" "(?P<user_agent>[^"]*)"'

def parse_http_log(log_line):
    """
    Parse HTTP Combined Log Format
    """
    if not log_line:
        return None
    
    try:
        match = re.match(COMBINED_LOG_PATTERN, log_line)
        if match:
            data = match.groupdict()
            
            # Parse timestamp
            try:
                # Convert Apache timestamp format to ISO format
                timestamp_str = data['timestamp']
                # Example: 10/Oct/2000:13:55:36 -0700
                dt = datetime.strptime(timestamp_str.split(' ')[0], '%d/%b/%Y:%H:%M:%S')
                data['parsed_timestamp'] = dt.isoformat()
                data['year'] = dt.year
                data['month'] = dt.month
                data['day'] = dt.day
                data['hour'] = dt.hour
            except:
                data['parsed_timestamp'] = None
                data['year'] = None
                data['month'] = None
                data['day'] = None
                data['hour'] = None
            
            # Convert numeric fields
            try:
                data['status'] = int(data['status'])
            except:
                data['status'] = None
            
            try:
                data['size'] = int(data['size']) if data['size'] != '-' else 0
            except:
                data['size'] = 0
            
            # Add derived fields
            data['is_error'] = data['status'] >= 400 if data['status'] else False
            data['status_category'] = (
                'success' if data['status'] and 200 <= data['status'] < 300 else
                'redirect' if data['status'] and 300 <= data['status'] < 400 else
                'client_error' if data['status'] and 400 <= data['status'] < 500 else
                'server_error' if data['status'] and data['status'] >= 500 else
                'unknown'
            )
            
            return data
    except Exception as e:
        print(f"Error parsing log line: {str(e)}")
    
    return None

def process_raw_data():
    """
    Process raw data from S3 and convert to structured Parquet format
    """
    
    # Read raw data from S3
    raw_path = f"s3://{args['raw_bucket']}/{args['solution_name']}/"
    
    try:
        # Create dynamic frame from raw data
        raw_dynamic_frame = glueContext.create_dynamic_frame.from_options(
            format_options={
                "multiline": False,
                "withHeader": False
            },
            connection_type="s3",
            format="json",
            connection_options={
                "paths": [raw_path],
                "recurse": True
            },
            transformation_ctx="raw_dynamic_frame"
        )
        
        print(f"Raw records count: {raw_dynamic_frame.count()}")
        
        if raw_dynamic_frame.count() == 0:
            print("No data found in raw bucket")
            return
        
        # Convert to DataFrame for processing
        raw_df = raw_dynamic_frame.toDF()
        
        # Process log lines
        def parse_log_udf(log_line):
            return parse_http_log(log_line)
        
        # Register UDF
        from pyspark.sql.functions import udf
        parse_udf = udf(parse_log_udf, MapType(StringType(), StringType()))
        
        # Apply parsing to log data
        # Assuming the raw data has a 'message' or 'log' field
        if 'message' in raw_df.columns:
            log_column = 'message'
        elif 'log' in raw_df.columns:
            log_column = 'log'
        else:
            # Take the first string column
            string_columns = [field.name for field in raw_df.schema.fields if field.dataType == StringType()]
            if string_columns:
                log_column = string_columns[0]
            else:
                print("No suitable log column found")
                return
        
        # Parse logs and create structured data
        parsed_df = raw_df.select(
            F.col(log_column).alias("raw_log"),
            parse_udf(F.col(log_column)).alias("parsed_data")
        ).filter(
            F.col("parsed_data").isNotNull()
        )
        
        # Expand parsed data into columns
        structured_df = parsed_df.select(
            F.col("raw_log"),
            F.col("parsed_data.ip").alias("client_ip"),
            F.col("parsed_data.timestamp").alias("original_timestamp"),
            F.col("parsed_data.parsed_timestamp").alias("timestamp"),
            F.col("parsed_data.method").alias("http_method"),
            F.col("parsed_data.path").alias("request_path"),
            F.col("parsed_data.protocol").alias("http_protocol"),
            F.col("parsed_data.status").cast(IntegerType()).alias("status_code"),
            F.col("parsed_data.size").cast(LongType()).alias("response_size"),
            F.col("parsed_data.referer").alias("referer"),
            F.col("parsed_data.user_agent").alias("user_agent"),
            F.col("parsed_data.is_error").cast(BooleanType()).alias("is_error"),
            F.col("parsed_data.status_category").alias("status_category"),
            F.col("parsed_data.year").cast(IntegerType()).alias("year"),
            F.col("parsed_data.month").cast(IntegerType()).alias("month"),
            F.col("parsed_data.day").cast(IntegerType()).alias("day"),
            F.col("parsed_data.hour").cast(IntegerType()).alias("hour"),
            F.current_timestamp().alias("processed_at")
        )
        
        print(f"Structured records count: {structured_df.count()}")
        
        # Convert back to DynamicFrame
        structured_dynamic_frame = DynamicFrame.fromDF(
            structured_df,
            glueContext,
            "structured_dynamic_frame"
        )
        
        # Write to processed bucket in Parquet format with partitioning
        processed_path = f"s3://{args['processed_bucket']}/{args['solution_name']}/"
        
        glueContext.write_dynamic_frame.from_options(
            frame=structured_dynamic_frame,
            connection_type="s3",
            format="glueparquet",
            connection_options={
                "path": processed_path,
                "partitionKeys": ["year", "month", "day", "hour"]
            },
            format_options={
                "compression": "snappy"
            },
            transformation_ctx="write_processed_data"
        )
        
        print(f"Successfully processed and wrote data to {processed_path}")
        
    except Exception as e:
        print(f"Error processing data: {str(e)}")
        raise

# Main execution
if __name__ == "__main__":
    process_raw_data()
    job.commit()
