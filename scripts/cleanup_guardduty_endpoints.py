#!/usr/bin/env python3
"""
GuardDuty VPC Endpoints Cleanup Script
Removes GuardDuty-managed VPC endpoints that prevent subnet deletion
"""

import boto3
import sys
import argparse
from botocore.exceptions import ClientError

def cleanup_guardduty_endpoints(vpc_id, profile=None, region=None, dry_run=False):
    """Clean up GuardDuty VPC endpoints in the specified VPC"""
    
    # Create session with profile if specified
    if profile:
        session = boto3.Session(profile_name=profile)
        ec2 = session.client('ec2', region_name=region)
    else:
        ec2 = boto3.client('ec2', region_name=region)
    
    try:
        print(f"🔍 Searching for GuardDuty VPC endpoints in VPC: {vpc_id}")
        
        # Find all VPC endpoints in the VPC
        response = ec2.describe_vpc_endpoints(
            Filters=[
                {'Name': 'vpc-id', 'Values': [vpc_id]},
                {'Name': 'vpc-endpoint-type', 'Values': ['Interface']}
            ]
        )
        
        guardduty_endpoints = []
        
        for endpoint in response['VpcEndpoints']:
            endpoint_id = endpoint['VpcEndpointId']
            service_name = endpoint.get('ServiceName', '')
            groups = endpoint.get('Groups', [])
            
            # Check if this is a GuardDuty managed endpoint
            is_guardduty = False
            for group in groups:
                group_name = group.get('GroupName', '')
                if 'GuardDutyManagedSecurityGroup' in group_name:
                    is_guardduty = True
                    break
            
            if is_guardduty:
                guardduty_endpoints.append({
                    'id': endpoint_id,
                    'service': service_name,
                    'subnets': endpoint.get('SubnetIds', [])
                })
                print(f"  📍 Found GuardDuty endpoint: {endpoint_id}")
                print(f"     Service: {service_name}")
                print(f"     Subnets: {', '.join(endpoint.get('SubnetIds', []))}")
        
        if not guardduty_endpoints:
            print("✅ No GuardDuty VPC endpoints found")
            return True
        
        print(f"\n🎯 Found {len(guardduty_endpoints)} GuardDuty VPC endpoints to clean up")
        
        if dry_run:
            print("🔍 DRY RUN MODE - No endpoints will be deleted")
            for endpoint in guardduty_endpoints:
                print(f"  Would delete: {endpoint['id']} ({endpoint['service']})")
            return True
        
        # Delete GuardDuty endpoints
        deleted_count = 0
        failed_count = 0
        
        for endpoint in guardduty_endpoints:
            endpoint_id = endpoint['id']
            try:
                print(f"🗑️  Deleting GuardDuty endpoint: {endpoint_id}")
                ec2.delete_vpc_endpoints(VpcEndpointIds=[endpoint_id])
                print(f"✅ Successfully deleted: {endpoint_id}")
                deleted_count += 1
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                error_message = e.response['Error']['Message']
                print(f"❌ Failed to delete {endpoint_id}: {error_code} - {error_message}")
                failed_count += 1
                
                if error_code == 'UnauthorizedOperation':
                    print("   💡 Tip: Check if you have ec2:DeleteVpcEndpoint permissions")
                elif error_code == 'InvalidVpcEndpointId.NotFound':
                    print("   💡 Endpoint may have been deleted already")
        
        print(f"\n📊 Cleanup Summary:")
        print(f"   ✅ Deleted: {deleted_count}")
        print(f"   ❌ Failed: {failed_count}")
        print(f"   📝 Total: {len(guardduty_endpoints)}")
        
        if failed_count == 0:
            print("🎉 All GuardDuty endpoints cleaned up successfully!")
            return True
        else:
            print("⚠️  Some endpoints could not be deleted. Check permissions and try again.")
            return False
            
    except ClientError as e:
        print(f"❌ Error accessing AWS: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def find_vpc_by_name(vpc_name, profile=None, region=None):
    """Find VPC ID by name tag"""
    
    if profile:
        session = boto3.Session(profile_name=profile)
        ec2 = session.client('ec2', region_name=region)
    else:
        ec2 = boto3.client('ec2', region_name=region)
    
    try:
        response = ec2.describe_vpcs(
            Filters=[
                {'Name': 'tag:Name', 'Values': [vpc_name]},
                {'Name': 'state', 'Values': ['available']}
            ]
        )
        
        if response['Vpcs']:
            return response['Vpcs'][0]['VpcId']
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error finding VPC: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(
        description='Clean up GuardDuty VPC endpoints that prevent subnet deletion'
    )
    parser.add_argument(
        '--vpc-id', 
        help='VPC ID to clean up (e.g., vpc-1234567890abcdef0)'
    )
    parser.add_argument(
        '--vpc-name', 
        help='VPC Name tag to find and clean up (e.g., agesic-dl-poc-vpc)'
    )
    parser.add_argument(
        '--profile', 
        default='agesicUruguay-699019841929',
        help='AWS profile to use (default: agesicUruguay-699019841929)'
    )
    parser.add_argument(
        '--region', 
        default='us-east-2',
        help='AWS region (default: us-east-2)'
    )
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    
    args = parser.parse_args()
    
    if not args.vpc_id and not args.vpc_name:
        print("❌ Error: Must specify either --vpc-id or --vpc-name")
        parser.print_help()
        sys.exit(1)
    
    print("🧹 GuardDuty VPC Endpoints Cleanup Script")
    print("=" * 50)
    
    vpc_id = args.vpc_id
    
    # Find VPC by name if needed
    if args.vpc_name and not vpc_id:
        print(f"🔍 Looking for VPC with name: {args.vpc_name}")
        vpc_id = find_vpc_by_name(args.vpc_name, args.profile, args.region)
        if not vpc_id:
            print(f"❌ VPC with name '{args.vpc_name}' not found")
            sys.exit(1)
        print(f"✅ Found VPC: {vpc_id}")
    
    print(f"🎯 Target VPC: {vpc_id}")
    print(f"🌍 Region: {args.region}")
    print(f"👤 Profile: {args.profile}")
    
    if args.dry_run:
        print("🔍 Mode: DRY RUN (no changes will be made)")
    else:
        print("⚠️  Mode: LIVE (endpoints will be deleted)")
        response = input("Continue? (y/N): ")
        if response.lower() != 'y':
            print("❌ Aborted by user")
            sys.exit(0)
    
    print()
    
    success = cleanup_guardduty_endpoints(
        vpc_id=vpc_id,
        profile=args.profile,
        region=args.region,
        dry_run=args.dry_run
    )
    
    if success:
        print("\n✅ Cleanup completed successfully!")
        if not args.dry_run:
            print("💡 You can now retry the stack deletion")
        sys.exit(0)
    else:
        print("\n❌ Cleanup failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
