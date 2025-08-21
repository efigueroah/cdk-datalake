import boto3
import json
import time
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda function to automatically install F5 Bridge setup and dual agents
    Triggered by EventBridge when new EC2 instance launches in ASG
    """
    
    ssm = boto3.client('ssm')
    autoscaling = boto3.client('autoscaling')
    
    # Get configuration from environment variables
    asg_name = context.function_name.replace('InstallAgentsFunction', 'f5-bridge-asg')
    main_document = context.function_name.replace('InstallAgentsFunction', 'complete-setup')
    agents_document = context.function_name.replace('InstallAgentsFunction', 'install-agents')
    kinesis_stream = 'agesic-dl-poc-streaming-DataStream6F9DAC72-guBUYFNpPRE3'
    
    try:
        logger.info(f"Processing event: {json.dumps(event)}")
        
        # Get instances from ASG
        response = autoscaling.describe_auto_scaling_groups(
            AutoScalingGroupNames=[asg_name]
        )
        
        if not response['AutoScalingGroups']:
            logger.error(f"Auto Scaling Group {asg_name} not found")
            return {
                'statusCode': 404,
                'body': json.dumps(f'Auto Scaling Group {asg_name} not found')
            }
        
        instances = response['AutoScalingGroups'][0]['Instances']
        if not instances:
            logger.info("No instances in ASG")
            return {
                'statusCode': 200,
                'body': json.dumps('No instances in ASG')
            }
        
        # Get the most recent instance
        latest_instance = max(instances, key=lambda x: x.get('LaunchTime', ''))
        instance_id = latest_instance['InstanceId']
        
        logger.info(f"Processing instance: {instance_id}")
        
        # Wait for instance to be ready for SSM
        logger.info("Waiting for instance to be ready...")
        time.sleep(60)
        
        # Run complete F5 Bridge setup
        logger.info("Running complete F5 Bridge setup...")
        setup_response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName=main_document,
            Parameters={
                'kinesisStreamName': [kinesis_stream],
                'sourceBucket': ['rawdata-analytics-poc-voh9ai'],
                'sourceFile': ['extracto_logs_acceso_f5_portalgubuy.txt']
            },
            Comment='Automated F5 Bridge setup via Lambda'
        )
        
        setup_command_id = setup_response['Command']['CommandId']
        logger.info(f"Setup command initiated: {setup_command_id}")
        
        # Install dual agents
        logger.info("Installing dual agents...")
        agents_response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName=agents_document,
            Parameters={
                'kinesisStreamName': [kinesis_stream],
                'agentType': ['both']
            },
            Comment='Automated dual agents installation via Lambda'
        )
        
        agents_command_id = agents_response['Command']['CommandId']
        logger.info(f"Agents command initiated: {agents_command_id}")
        
        result = {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'F5 Bridge setup and agents installation initiated successfully',
                'instance_id': instance_id,
                'setup_command_id': setup_command_id,
                'agents_command_id': agents_command_id,
                'asg_name': asg_name
            })
        }
        
        logger.info(f"Success: {result}")
        return result
        
    except Exception as e:
        error_msg = f'Error processing instance launch: {str(e)}'
        logger.error(error_msg)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': error_msg,
                'event': event
            })
        }
