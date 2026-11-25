"""AWS checks."""

from datetime import datetime

from .helpers import (
    INTERNET_CIDRS,
    admin_ports_in_range,
    require_bool,
    require_dict,
    require_list,
    require_port,
)
from .registry import FAIL, PASS, CannotScan, register_check

PUBLIC_ACCESS_FLAGS = [
    "block_public_acls",
    "ignore_public_acls",
    "block_public_policy",
    "restrict_public_buckets",
]

MAX_KEY_AGE_DAYS = 90


@register_check("AWS-S3-01", "S3 bucket blocks public access", "HIGH",
                "aws", "s3_buckets", "name")
def s3_blocks_public_access(bucket: dict, snapshot_time: datetime):
    block = bucket.get("public_access_block")
    if block is None:
        return FAIL, "No public access block is configured on the bucket"
    block = require_dict(block, "public_access_block")

    disabled = [flag for flag in PUBLIC_ACCESS_FLAGS
                if not require_bool(block, flag)]
    if disabled:
        return FAIL, "Public access block settings are off: " + ", ".join(disabled)
    return PASS, "All four public access block settings are on"


@register_check("AWS-EC2-01", "Security group doesn't expose SSH or RDP to the internet",
                "CRITICAL", "aws", "security_groups", "group_id")
def sg_no_open_admin_ports(group: dict, snapshot_time: datetime):
    problems = []
    for rule in require_list(group.get("ingress"), "ingress"):
        rule = require_dict(rule, "ingress rule")
        protocol = str(rule.get("protocol"))

        if protocol == "-1":  # "-1" means all protocols and all ports
            low, high = 0, 65535
        elif protocol == "tcp":
            low = require_port(rule.get("from_port"), "from_port")
            high = require_port(rule.get("to_port"), "to_port")
        else:
            continue  # udp, icmp, ... can't carry SSH or RDP

        open_cidrs = [c for c in require_list(rule.get("cidrs"), "cidrs") if c in INTERNET_CIDRS]
        ports = admin_ports_in_range(low, high)
        if open_cidrs and ports:
            problems.append(
                f"inbound {protocol} ports {low}-{high} open to {', '.join(open_cidrs)} "
                f"exposes {', '.join(ports)}"
            )

    if problems:
        return FAIL, "; ".join(problems)
    return PASS, "No inbound rule exposes SSH or RDP to the internet"


@register_check("AWS-IAM-01", "Console users have MFA", "HIGH",
                "aws", "iam_users", "user_name")
def iam_console_users_have_mfa(user: dict, snapshot_time: datetime):
    if not require_bool(user, "console_access"):
        return PASS, "User has no console access"
    if not require_bool(user, "mfa_enabled"):
        return FAIL, "User can sign in to the console but has no MFA device"
    return PASS, "Console user has MFA enabled"


@register_check("AWS-IAM-02", "No active access key is older than 90 days", "MEDIUM",
                "aws", "iam_users", "user_name")
def iam_no_old_active_keys(user: dict, snapshot_time: datetime):
    old_keys = []
    for key in require_list(user.get("access_keys"), "access_keys"):
        key = require_dict(key, "access key")
        if key.get("status") != "Active":
            continue
        try:
            created = datetime.fromisoformat(str(key.get("created_at")).replace("Z", "+00:00"))
            age_days = (snapshot_time - created).days
        except (ValueError, TypeError) as error:
            raise CannotScan(f"access key created_at is not a valid date: {key.get('created_at')!r}") from error
        if age_days > MAX_KEY_AGE_DAYS:
            old_keys.append(f"{key.get('key_id')} is {age_days} days old")

    if old_keys:
        return FAIL, f"Active access keys older than {MAX_KEY_AGE_DAYS} days: " + "; ".join(old_keys)
    return PASS, f"No active access key is older than {MAX_KEY_AGE_DAYS} days"


@register_check("AWS-RDS-01", "RDS instance isn't publicly accessible", "HIGH",
                "aws", "rds_instances", "db_instance_id")
def rds_not_public(instance: dict, snapshot_time: datetime):
    if require_bool(instance, "publicly_accessible"):
        return FAIL, "publicly_accessible is true, so the instance has a public endpoint"
    return PASS, "Instance is not publicly accessible"
