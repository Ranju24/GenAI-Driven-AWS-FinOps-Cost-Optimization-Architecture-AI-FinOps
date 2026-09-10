# AWS Cost & Unused Resource Executive Summary

## Executive Summary Table

| Resource Type           | Count | Individual Monthly Cost (USD) | Total Monthly Cost (USD) |
|-------------------------|-------|-------------------------------|---------------------------|
| Unattached EBS Volumes  | 1     | 0.64                          | 0.64                      |
| Unassociated EIPs       | 1     | 3.6                           | 3.6                       |
| Idle EC2 Instances      | 0     | -                             | 0                         |
| Old EBS Snapshots       | 1     | 0.4                           | 0.4                       |
| **Total**               | **3** | **4.64**                      | **4.64**                  |

## Detailed Resource List

### Unattached EBS Volumes

- **Volume ID:** `vol-0bf83a39f3fcd361e`
- **Size:** 8 GB
- **Volume Type:** gp3
- **Availability Zone:** us-east-1c
- **Age:** 11231 minutes
- **Estimated Monthly Cost:** $0.64

### Unassociated EIPs

- **Public IP:** `32.199.226.22`
- **Allocation ID:** `eipalloc-0632369513db630a4`
- **Estimated Monthly Cost:** $3.6

### Old EBS Snapshots

- **Snapshot ID:** `snap-0f92c1c626f65ba03`
- **Volume Size:** 8 GB
- **Age:** 10 minutes
- **Estimated Monthly Cost:** $0.4

## Remediation Steps

### Unattached EBS Volumes

1. **Identify the Volume:**
   ```sh
   aws ec2 describe-volumes --volume-ids vol-0bf83a39f3fcd361e
   ```

2. **Delete the Volume if Unnecessary:**
   ```sh
   aws ec2 delete-volume --volume-id vol-0bf83a39f3fcd361e
   ```

### Unassociated EIPs

1. **Identify the EIP:**
   ```sh
   aws ec2 describe-addresses --allocation-ids eipalloc-0632369513db630a4
   ```

2. **Release the EIP if Unnecessary:**
   ```sh
   aws ec2 release-address --allocation-id eipalloc-0632369513db630a4
   ```

### Old EBS Snapshots

1. **Identify the Snapshot:**
   ```sh
   aws ec2 describe-snapshots --snapshot-ids snap-0f92c1c626f65ba03
   ```

2. **Delete the Snapshot if Unnecessary:**
   ```sh
   aws ec2 delete-snapshot --snapshot-id snap-0f92c1c626f65ba03
   ```

By following these steps, the DevOps team can effectively remediate the identified unused resources, leading to potential cost savings of $4.64 per month.