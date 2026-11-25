"""Azure checks."""

from datetime import datetime

from .helpers import admin_ports_in_range, parse_port_range, require_bool, require_dict, require_list
from .registry import FAIL, PASS, register_check

# Azure NSG source values that mean "anyone on the internet".
INTERNET_SOURCES = {"*", "internet", "any", "0.0.0.0/0", "::/0"}


@register_check("AZ-STG-01", "Storage account blocks public blob access", "HIGH",
                "azure", "storage_accounts", "name")
def storage_blocks_public_blobs(account: dict, snapshot_time: datetime):
    if require_bool(account, "allow_blob_public_access"):
        return FAIL, "allow_blob_public_access is true, so blobs can be made public"
    return PASS, "Public blob access is disabled"


@register_check("AZ-NSG-01", "NSG doesn't expose SSH or RDP to the internet", "CRITICAL",
                "azure", "network_security_groups", "name")
def nsg_no_open_admin_ports(nsg: dict, snapshot_time: datetime):
    problems = []
    for rule in require_list(nsg.get("rules"), "rules"):
        rule = require_dict(rule, "rule")

        # Only inbound "Allow" rules can open a port. Deny and Outbound rules are skipped.
        if str(rule.get("direction")).lower() != "inbound":
            continue
        if str(rule.get("access")).lower() != "allow":
            continue
        if str(rule.get("protocol")).lower() not in ("tcp", "*"):
            continue
        source = str(rule.get("source"))
        if source.lower() not in INTERNET_SOURCES:
            continue

        # destination_ports can be "22", "3380-3400", "*" or "22,3389".
        port_text = rule.get("destination_ports")
        port_specs = port_text if isinstance(port_text, list) else str(port_text).split(",")
        for spec in port_specs:
            low, high = parse_port_range(spec)
            ports = admin_ports_in_range(low, high)
            if ports:
                problems.append(
                    f"rule '{rule.get('name')}' allows inbound ports {spec.strip()} "
                    f"from '{source}', exposing {', '.join(ports)}"
                )

    if problems:
        return FAIL, "; ".join(problems)
    return PASS, "No inbound allow rule exposes SSH or RDP to the internet"
