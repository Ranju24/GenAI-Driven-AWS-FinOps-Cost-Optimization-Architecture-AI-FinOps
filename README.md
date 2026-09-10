GenAI-Driven-AWS-FinOps-Cost-Optimization-Architecture-AI-FinOps

Designed and implemented an end-to-end serverless FinOps engine that automates cloud resource auditing, waste identification, and cost-governance reporting across AWS infra

Cloud environments naturally accumulate orphaned and underutilized assets over time—such as unattached storage volumes, unassociated static IP addresses, idle computing instances, and stale snapshots. Left unchecked, these abandoned resources inflate monthly expenditures. To address this, I built an event-driven governance pipeline that continuously monitors resource utilization and translates raw technical metrics into actionable financial intelligence

The architecture operates on a scheduled, automated workflow triggered via Amazon EventBridge. When executed, a serverless AWS Lambda function leverages Python to audit key infrastructure components across the account

Storage Assets:Scans for unattached EBS volumes and unlinked EBS snapshots exceeding defined retention boundaries

Network Components: Identifies unassociated EIPs incurring idle allocation charges

Compute Utilization: Evaluates historical CloudWatch CPU utilization metrics for running EC2 instances to pinpoint low-utilization, idle instances operating well below workload thresholds.

The pipeline integrates directly with Amazon Bedrock using the Nova Lite foundation model via API. The aggregated telemetry is passed to Bedrock, which acts as an autonomous FinOps architect. It processes the resource metadata, calculates estimated monthly waste, and formats the findings into a clean, executive-ready Markdown report. AWS CLI remediation commands to empower to quickly decommission or right-size waste
