import json
import os
from datetime import datetime, timedelta, timezone
import boto3
from botocore.exceptions import ClientError

# Configuration & Environment Variables
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "finops-cost-reports-755905325526")
SNS_TOPIC_ARN = os.environ.get(
    "SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:755905325526:FinOps-Cost-Alerts"
)
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")

# Initialize AWS Clients
ec2_client = boto3.client("ec2", region_name=AWS_REGION)
cloudwatch_client = boto3.client("cloudwatch", region_name=AWS_REGION)
bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
s3_client = boto3.client("s3", region_name=AWS_REGION)
sns_client = boto3.client("sns", region_name=AWS_REGION)


def get_idle_resources():
  """Scans EC2 resources for unattached EBS, unassociated EIPs, idle EC2 (<5% CPU), and snapshots older than 5 minutes."""
  now = datetime.now(timezone.utc)
  threshold_5m = now - timedelta(minutes=5)

  unused_resources = {
      "unattached_ebs": [],
      "unassociated_eips": [],
      "idle_ec2_instances": [],
      "old_ebs_snapshots": [],
  }

  # 1. Unattached EBS Volumes (>5 minutes old)
  paginator_ebs = ec2_client.get_paginator("describe_volumes")
  for page in paginator_ebs.paginate(
      Filters=[{"Name": "status", "Values": ["available"]}]
  ):
    for vol in page.get("Volumes", []):
      create_time = vol["CreateTime"]
      if create_time < threshold_5m:
        age_minutes = int((now - create_time).total_seconds() // 60)
        unused_resources["unattached_ebs"].append({
            "VolumeId": vol["VolumeId"],
            "SizeGB": vol["Size"],
            "VolumeType": vol["VolumeType"],
            "AvailabilityZone": vol["AvailabilityZone"],
            "AgeMinutes": age_minutes,
            "EstimatedMonthlyCostUSD": round(vol["Size"] * 0.08, 2),
        })

  # 2. Unassociated Elastic IPs
  eip_response = ec2_client.describe_addresses()
  for addr in eip_response.get("Addresses", []):
    if "InstanceId" not in addr and "NetworkInterfaceId" not in addr:
      unused_resources["unassociated_eips"].append({
          "PublicIp": addr.get("PublicIp", "N/A"),
          "AllocationId": addr.get("AllocationId", "N/A"),
          "EstimatedMonthlyCostUSD": 3.60,
      })

  # 3. Idle EC2 Instances (<5.0% CPU evaluated over the last 15 minutes)
  # Lookback remains 15 mins for CloudWatch API to guarantee metric data points exist
  threshold_cw = now - timedelta(minutes=15)
  paginator_ec2 = ec2_client.get_paginator("describe_instances")
  for page in paginator_ec2.paginate(
      Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
  ):
    for reservation in page.get("Reservations", []):
      for inst in reservation.get("Instances", []):
        instance_id = inst["InstanceId"]
        instance_type = inst["InstanceType"]

        stats = cloudwatch_client.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            StartTime=threshold_cw,
            EndTime=now,
            Period=300,  # 5-minute aggregation buckets
            Statistics=["Average"],
        )

        datapoints = stats.get("Datapoints", [])

        if not datapoints:
          print(
              f"Warning: No CloudWatch metrics found for instance {instance_id}."
          )
          continue

        avg_cpu = sum(dp["Average"] for dp in datapoints) / len(datapoints)
        print(
            f"Evaluated Instance {instance_id} ({instance_type}): Avg CPU ="
            f" {avg_cpu:.2f}%"
        )

        if avg_cpu < 5.0:
          unused_resources["idle_ec2_instances"].append({
              "InstanceId": instance_id,
              "InstanceType": instance_type,
              "AvgCpuUtilization": round(avg_cpu, 2),
              "State": "running",
          })

  # 4. EBS Snapshots (>5 minutes old)
  paginator_snap = ec2_client.get_paginator("describe_snapshots")
  for page in paginator_snap.paginate(OwnerIds=["self"]):
    for snap in page.get("Snapshots", []):
      start_time = snap["StartTime"]
      if start_time < threshold_5m:
        age_minutes = int((now - start_time).total_seconds() // 60)
        volume_size = snap.get("VolumeSize", 0)
        unused_resources["old_ebs_snapshots"].append({
            "SnapshotId": snap["SnapshotId"],
            "VolumeSizeGB": volume_size,
            "AgeMinutes": age_minutes,
            "EstimatedMonthlyCostUSD": round(volume_size * 0.05, 2),
        })

  return unused_resources


def generate_markdown_report_with_bedrock(unused_data):
  """Sends JSON data to Bedrock Nova Lite to generate an executive Markdown report."""
  prompt = f"""
    You are an expert AWS FinOps Cloud Architect.
    Strictly analyze the provided JSON data containing unattached, unused, or idle AWS resources and create a professional Markdown report.

    Resource Data:
    {json.dumps(unused_data, indent=2)}

    Formatting Guidelines:
    1. Title: AWS Cost & Unused Resource Executive Summary
    2. Executive Summary Table: Count every item strictly according to the JSON data provided above. Calculate individual and total monthly savings accurately.
    3. Detailed Resource List: Explicitly list IP addresses, Volume IDs, Instance IDs, and Snapshot IDs found in the input. Include age in minutes for EBS volumes and snapshots.
    4. Provide clear, step-by-step remediation commands/actions for the DevOps team.
    5. Do NOT output markdown code blocks (```markdown).
    """

  payload = {
      "messages": [{"role": "user", "content": [{"text": prompt}]}],
      "inferenceConfig": {"maxTokens": 1200, "temperature": 0.2},
  }

  try:
    response = bedrock_client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(payload),
    )

    response_body = json.loads(response["body"].read())
    return response_body["output"]["message"]["content"][0]["text"]
  except Exception as e:
    print(f"Error invoking Bedrock model: {str(e)}")
    raise e


def save_report_to_s3(report_content):
  """Saves the Markdown report to S3 with a timestamped key."""
  timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
  file_key = f"reports/FinOps_Cost_Report_{timestamp}.md"

  s3_client.put_object(
      Bucket=S3_BUCKET_NAME,
      Key=file_key,
      Body=report_content,
      ContentType="text/markdown",
  )
  print(f"Uploaded report to S3: s3://{S3_BUCKET_NAME}/{file_key}")
  return file_key


def send_notification_via_sns(report_content):
  """Publishes the generated report content directly to SNS."""
  date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
  subject_str = f"AWS FinOps Cost Report ({date_str})"

  if len(subject_str) > 100:
    subject_str = subject_str[:97] + "..."

  try:
    response = sns_client.publish(
        TopicArn=SNS_TOPIC_ARN, Subject=subject_str, Message=report_content
    )
    print(
        f"SNS Published successfully. MessageId: {response.get('MessageId')}"
    )
  except ClientError as e:
    print(f"Failed to publish to SNS: {e.response['Error']['Message']}")
    raise e


def lambda_handler(event, context):
  print("Starting AWS FinOps Cost Optimization Scanner...")

  unused_resources = get_idle_resources()

  ebs_count = len(unused_resources["unattached_ebs"])
  eip_count = len(unused_resources["unassociated_eips"])
  ec2_count = len(unused_resources["idle_ec2_instances"])
  snap_count = len(unused_resources["old_ebs_snapshots"])

  total_found = ebs_count + eip_count + ec2_count + snap_count
  print(f"Scan Finished. Total Resources Found: {total_found}")

  if total_found == 0:
    print("No orphaned or idle resources detected. Exiting.")
    return {
        "statusCode": 200,
        "body": json.dumps("No orphaned or idle resources detected."),
    }

  print("Generating report via Bedrock Nova Lite...")
  markdown_report = generate_markdown_report_with_bedrock(unused_resources)

  s3_key = save_report_to_s3(markdown_report)
  send_notification_via_sns(markdown_report)

  return {
      "statusCode": 200,
      "body": json.dumps({
          "message": "FinOps automation executed successfully.",
          "s3_key": s3_key,
          "ebs_found": ebs_count,
          "eip_found": eip_count,
          "idle_ec2_found": ec2_count,
          "old_snapshots_found": snap_count,
      }),
  }