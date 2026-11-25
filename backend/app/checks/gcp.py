"""Google Cloud checks."""

from datetime import datetime

from .helpers import (
    INTERNET_CIDRS,
    admin_ports_in_range,
    parse_port_range,
    require_bool,
    require_dict,
    require_list,
)
from .registry import FAIL, PASS, register_check

PUBLIC_MEMBERS = {"allUsers", "allAuthenticatedUsers"}


@register_check("GCP-GCS-01", "Bucket isn't public", "HIGH",
                "gcp", "gcs_buckets", "name")
def gcs_not_public(bucket: dict, snapshot_time: datetime):
    problems = []
    for binding in require_list(bucket.get("iam_bindings", []), "iam_bindings"):
        binding = require_dict(binding, "iam binding")
        for member in require_list(binding.get("members"), "members"):
            if member in PUBLIC_MEMBERS:
                problems.append(f"{binding.get('role')} is granted to {member}")

    if problems:
        return FAIL, "Bucket is public: " + "; ".join(problems)
    return PASS, "No IAM binding grants access to allUsers or allAuthenticatedUsers"


@register_check("GCP-GCS-02", "Bucket uses uniform bucket-level access", "LOW",
                "gcp", "gcs_buckets", "name")
def gcs_uniform_access(bucket: dict, snapshot_time: datetime):
    if not require_bool(bucket, "uniform_bucket_level_access"):
        return FAIL, "uniform_bucket_level_access is off, so per-object ACLs are allowed"
    return PASS, "Uniform bucket-level access is on"


@register_check("GCP-VPC-01", "Firewall rule doesn't expose SSH or RDP to the internet",
                "CRITICAL", "gcp", "firewall_rules", "name")
def firewall_no_open_admin_ports(rule: dict, snapshot_time: datetime):
    if str(rule.get("direction")).upper() != "INGRESS":
        return PASS, "Rule is not an ingress rule"
    if require_bool(rule, "disabled"):
        return PASS, "Rule is disabled"

    sources = require_list(rule.get("source_ranges"), "source_ranges")
    open_sources = [s for s in sources if s in INTERNET_CIDRS]
    if not open_sources:
        return PASS, "Rule does not allow traffic from the whole internet"

    problems = []
    for allowed in require_list(rule.get("allowed"), "allowed"):
        allowed = require_dict(allowed, "allowed entry")
        protocol = str(allowed.get("IPProtocol")).lower()
        if protocol not in ("tcp", "all"):
            continue
        # No "ports" (or protocol "all") means every port.
        port_specs = allowed.get("ports") or ["0-65535"]
        for spec in require_list(port_specs, "ports"):
            low, high = parse_port_range(spec)
            ports = admin_ports_in_range(low, high)
            if ports:
                problems.append(
                    f"allows {protocol} ports {spec} from {', '.join(open_sources)}, "
                    f"exposing {', '.join(ports)}"
                )

    if problems:
        return FAIL, "; ".join(problems)
    return PASS, "Rule does not expose SSH or RDP"
