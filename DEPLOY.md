# Deploying Mini Gauntlet on AWS

This is a design note. Nothing here is deployed.

## Compute
- **API:** the existing `backend` image on **ECS Fargate**: one service with two or more tasks spread across two AZs, behind an internal target group. Fargate means no servers to patch, and tasks run as the image's non-root user.
- **Dashboard:** the static build goes to a private **S3 bucket** served by **CloudFront** with Origin Access Control. CloudFront routes `/api/*` to the ALB, so the browser still sees a single origin and no CORS is needed.
- **Scans:** today scans run in an in-process thread. In production, `POST /api/scans` would put a message on **SQS**, and a separate Fargate worker service (same image, different command) would run the scan. A deploy or crash then can't lose a running scan, and workers can scale on queue depth.

## Database
- **RDS for PostgreSQL** (Multi-AZ, encrypted with KMS, automated backups, 7–30 day PITR). SQLite is replaced by Postgres behind the same small `db.py` interface. Schema changes would move to Alembic migrations.

## Networking
- A VPC with public subnets (ALB only) and private subnets (Fargate tasks, RDS). No task has a public IP. Outbound traffic goes through NAT, or VPC endpoints for ECR, S3, Secrets Manager, CloudWatch Logs and STS.
- Security groups: ALB ← CloudFront managed prefix list on 443. Tasks ← ALB only on 8000. RDS ← tasks only on 5432.
- AWS WAF on CloudFront with the managed common rule set and rate limiting.

## Secrets
- The DB password lives in **Secrets Manager** with rotation and is injected into the task as an ECS secret, never baked into an image or committed. Customer cloud access uses **cross-account IAM roles** with an `ExternalId`, so the scanner never stores customer keys.

## Logs and monitoring
- Containers log to stdout, which goes to **CloudWatch Logs** through the `awslogs` driver (30–90 day retention). CloudWatch alarms watch ALB 5xx rate, task health, RDS CPU and storage, and SQS queue age. CloudTrail is on for the account.

## CI/CD without long-lived keys
- GitHub Actions authenticates with **OIDC**. An IAM role trusts `token.actions.githubusercontent.com`, restricted to `repo:<org>/mini-gauntlet:ref:refs/heads/main`. The workflow uses `aws-actions/configure-aws-credentials` to get short-lived credentials.
- On `main`, after lint, tests and image builds pass: push images to **ECR** (tagged with the commit SHA, scan-on-push on), register new task definitions, run `aws ecs update-service` (rolling deploy with circuit-breaker rollback), `aws s3 sync` the dashboard build, and invalidate CloudFront. The deploy role can only push to those ECR repos, update those two services, `iam:PassRole` the two task roles, and write to that one bucket.

## Least-privilege, read-only permissions for a live scanner

Each customer account grants a read-only role that the scanner assumes.

**AWS** (IAM policy on the cross-account role):

| Check | Actions |
|---|---|
| AWS-S3-01 | `s3:ListAllMyBuckets`, `s3:GetBucketLocation`, `s3:GetBucketPublicAccessBlock` |
| AWS-EC2-01 | `ec2:DescribeRegions`, `ec2:DescribeSecurityGroups` |
| AWS-IAM-01 | `iam:ListUsers`, `iam:GetLoginProfile`, `iam:ListMFADevices` |
| AWS-IAM-02 | `iam:ListUsers`, `iam:ListAccessKeys` |
| AWS-RDS-01 | `rds:DescribeDBInstances` |

**Azure** (a custom role assigned at subscription scope, instead of the broad built-in Reader):
- AZ-STG-01: `Microsoft.Storage/storageAccounts/read`
- AZ-NSG-01: `Microsoft.Network/networkSecurityGroups/read`
- Both: `Microsoft.Resources/subscriptions/resourceGroups/read`

**Google Cloud** (a custom role on the project, bound to the scanner's service account through Workload Identity Federation, so no JSON keys):
- GCP-GCS-01/02: `storage.buckets.list`, `storage.buckets.get`, `storage.buckets.getIamPolicy`
- GCP-VPC-01: `compute.firewalls.list`
