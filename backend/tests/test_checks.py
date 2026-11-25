"""Unit tests for every check: PASS, FAIL, CANNOT_SCAN and the catalog's edge cases."""

from datetime import datetime, timezone

import pytest

from app.checks import CANNOT_SCAN, CHECKS, FAIL, PASS
from app.scanner import run_check_on_resource

SNAPSHOT = datetime(2026, 10, 1, tzinfo=timezone.utc)
ACCOUNT = {"account_id": "acct-1"}


def run(check_id: str, resource: dict) -> dict:
    """Run one check through the same wrapper the scanner uses."""
    check = next(c for c in CHECKS if c.id == check_id)
    return run_check_on_resource(check, ACCOUNT, resource, SNAPSHOT)


def test_catalog_has_ten_unique_checks():
    ids = [c.id for c in CHECKS]
    assert len(ids) == 10
    assert len(set(ids)) == 10


# ---------- AWS-S3-01 ----------

ALL_ON = {"block_public_acls": True, "ignore_public_acls": True,
          "block_public_policy": True, "restrict_public_buckets": True}


def test_s3_pass():
    assert run("AWS-S3-01", {"name": "b", "public_access_block": ALL_ON})["status"] == PASS


def test_s3_fail_names_the_disabled_flag():
    finding = run("AWS-S3-01", {"name": "b", "public_access_block": {**ALL_ON, "block_public_policy": False}})
    assert finding["status"] == FAIL
    assert "block_public_policy" in finding["details"]


def test_s3_fail_when_block_missing():
    assert run("AWS-S3-01", {"name": "b", "public_access_block": None})["status"] == FAIL


def test_s3_cannot_scan_on_non_bool_flag():
    finding = run("AWS-S3-01", {"name": "b", "public_access_block": {**ALL_ON, "block_public_acls": "yes"}})
    assert finding["status"] == CANNOT_SCAN


# ---------- AWS-EC2-01 ----------

def sg(protocol="tcp", from_port=22, to_port=22, cidrs=("0.0.0.0/0",)):
    return {"group_id": "sg-1", "ingress": [
        {"protocol": protocol, "from_port": from_port, "to_port": to_port, "cidrs": list(cidrs)}]}


def test_sg_fail_ssh_open_to_world():
    finding = run("AWS-EC2-01", sg())
    assert finding["status"] == FAIL
    assert "22" in finding["details"] and "0.0.0.0/0" in finding["details"]


def test_sg_fail_ipv6_any():
    assert run("AWS-EC2-01", sg(cidrs=["::/0"]))["status"] == FAIL


def test_sg_fail_port_range_contains_rdp():
    finding = run("AWS-EC2-01", sg(from_port=3000, to_port=3500))
    assert finding["status"] == FAIL
    assert "3389" in finding["details"]


def test_sg_fail_all_protocols():
    assert run("AWS-EC2-01", sg(protocol="-1", from_port=None, to_port=None))["status"] == FAIL


def test_sg_pass_private_cidr():
    assert run("AWS-EC2-01", sg(cidrs=["203.0.113.0/24"]))["status"] == PASS


def test_sg_pass_other_port():
    assert run("AWS-EC2-01", sg(from_port=443, to_port=443))["status"] == PASS


def test_sg_pass_udp():
    assert run("AWS-EC2-01", sg(protocol="udp", from_port=53, to_port=53))["status"] == PASS


def test_sg_cannot_scan_non_numeric_port():
    finding = run("AWS-EC2-01", sg(from_port="twenty-two"))
    assert finding["status"] == CANNOT_SCAN
    assert "twenty-two" in finding["details"]


# ---------- AWS-IAM-01 ----------

def test_mfa_pass():
    assert run("AWS-IAM-01", {"user_name": "a", "console_access": True, "mfa_enabled": True})["status"] == PASS


def test_mfa_pass_no_console():
    assert run("AWS-IAM-01", {"user_name": "a", "console_access": False, "mfa_enabled": False})["status"] == PASS


def test_mfa_fail():
    assert run("AWS-IAM-01", {"user_name": "a", "console_access": True, "mfa_enabled": False})["status"] == FAIL


def test_mfa_cannot_scan():
    assert run("AWS-IAM-01", {"user_name": "a", "console_access": "maybe"})["status"] == CANNOT_SCAN


# ---------- AWS-IAM-02 ----------

def user_with_key(created_at, status="Active"):
    return {"user_name": "u", "access_keys": [{"key_id": "k1", "status": status, "created_at": created_at}]}


def test_key_exactly_90_days_passes():
    assert run("AWS-IAM-02", user_with_key("2026-07-03T00:00:00Z"))["status"] == PASS


def test_key_91_days_fails():
    finding = run("AWS-IAM-02", user_with_key("2026-07-02T00:00:00Z"))
    assert finding["status"] == FAIL
    assert "k1" in finding["details"] and "91" in finding["details"]


def test_inactive_old_key_passes():
    assert run("AWS-IAM-02", user_with_key("2020-01-01T00:00:00Z", status="Inactive"))["status"] == PASS


def test_no_keys_passes():
    assert run("AWS-IAM-02", {"user_name": "u", "access_keys": []})["status"] == PASS


def test_bad_key_date_cannot_scan():
    assert run("AWS-IAM-02", user_with_key("last tuesday"))["status"] == CANNOT_SCAN


# ---------- AWS-RDS-01 ----------

def test_rds_pass():
    assert run("AWS-RDS-01", {"db_instance_id": "d", "publicly_accessible": False})["status"] == PASS


def test_rds_fail():
    assert run("AWS-RDS-01", {"db_instance_id": "d", "publicly_accessible": True})["status"] == FAIL


def test_rds_cannot_scan():
    assert run("AWS-RDS-01", {"db_instance_id": "d"})["status"] == CANNOT_SCAN


# ---------- AZ-STG-01 ----------

def test_storage_pass():
    assert run("AZ-STG-01", {"name": "s", "allow_blob_public_access": False})["status"] == PASS


def test_storage_fail():
    assert run("AZ-STG-01", {"name": "s", "allow_blob_public_access": True})["status"] == FAIL


def test_storage_cannot_scan():
    assert run("AZ-STG-01", {"name": "s", "allow_blob_public_access": None})["status"] == CANNOT_SCAN


# ---------- AZ-NSG-01 ----------

def nsg(**overrides):
    rule = {"name": "r1", "direction": "Inbound", "access": "Allow", "protocol": "Tcp",
            "source": "Internet", "destination_ports": "22", **overrides}
    return {"name": "nsg", "rules": [rule]}


@pytest.mark.parametrize("source", ["*", "Internet", "0.0.0.0/0", "::/0"])
def test_nsg_fail_for_internet_sources(source):
    finding = run("AZ-NSG-01", nsg(source=source))
    assert finding["status"] == FAIL
    assert "r1" in finding["details"]


def test_nsg_fail_port_range_contains_rdp():
    assert run("AZ-NSG-01", nsg(protocol="*", destination_ports="3380-3400"))["status"] == FAIL


def test_nsg_fail_wildcard_port():
    assert run("AZ-NSG-01", nsg(destination_ports="*"))["status"] == FAIL


def test_nsg_pass_deny_rule():
    assert run("AZ-NSG-01", nsg(access="Deny"))["status"] == PASS


def test_nsg_pass_outbound_rule():
    assert run("AZ-NSG-01", nsg(direction="Outbound", source="*"))["status"] == PASS


def test_nsg_pass_other_port():
    assert run("AZ-NSG-01", nsg(destination_ports="443"))["status"] == PASS


def test_nsg_pass_private_source():
    assert run("AZ-NSG-01", nsg(source="10.0.0.0/8"))["status"] == PASS


def test_nsg_cannot_scan_bad_port():
    assert run("AZ-NSG-01", nsg(destination_ports="ssh"))["status"] == CANNOT_SCAN


# ---------- GCP-GCS-01 ----------

def bucket(members, uniform=True):
    return {"name": "b", "uniform_bucket_level_access": uniform,
            "iam_bindings": [{"role": "roles/storage.objectViewer", "members": members}]}


def test_gcs_public_fail_all_users():
    finding = run("GCP-GCS-01", bucket(["allUsers"]))
    assert finding["status"] == FAIL
    assert "allUsers" in finding["details"]


def test_gcs_public_fail_all_authenticated_users():
    assert run("GCP-GCS-01", bucket(["allAuthenticatedUsers", "user:x@example.com"]))["status"] == FAIL


def test_gcs_public_pass():
    assert run("GCP-GCS-01", bucket(["group:eng@example.com"]))["status"] == PASS


def test_gcs_public_cannot_scan():
    assert run("GCP-GCS-01", {"name": "b", "iam_bindings": "oops"})["status"] == CANNOT_SCAN


# ---------- GCP-GCS-02 ----------

def test_gcs_uniform_pass():
    assert run("GCP-GCS-02", bucket([], uniform=True))["status"] == PASS


def test_gcs_uniform_fail():
    assert run("GCP-GCS-02", bucket([], uniform=False))["status"] == FAIL


def test_gcs_uniform_cannot_scan():
    assert run("GCP-GCS-02", bucket([], uniform="sometimes"))["status"] == CANNOT_SCAN


# ---------- GCP-VPC-01 ----------

def firewall(**overrides):
    rule = {"name": "fw", "direction": "INGRESS", "disabled": False, "source_ranges": ["0.0.0.0/0"],
            "allowed": [{"IPProtocol": "tcp", "ports": ["3389"]}], **overrides}
    return rule


def test_firewall_fail_rdp():
    finding = run("GCP-VPC-01", firewall())
    assert finding["status"] == FAIL
    assert "3389" in finding["details"]


def test_firewall_fail_all_protocols_no_ports():
    assert run("GCP-VPC-01", firewall(allowed=[{"IPProtocol": "all"}]))["status"] == FAIL


def test_firewall_fail_ipv6():
    assert run("GCP-VPC-01", firewall(source_ranges=["::/0"]))["status"] == FAIL


def test_firewall_pass_disabled():
    assert run("GCP-VPC-01", firewall(disabled=True))["status"] == PASS


def test_firewall_pass_egress():
    assert run("GCP-VPC-01", firewall(direction="EGRESS"))["status"] == PASS


def test_firewall_pass_range_without_admin_ports():
    assert run("GCP-VPC-01", firewall(allowed=[{"IPProtocol": "tcp", "ports": ["8000-9000"]}]))["status"] == PASS


def test_firewall_pass_restricted_source():
    assert run("GCP-VPC-01", firewall(source_ranges=["35.235.240.0/20"]))["status"] == PASS


def test_firewall_cannot_scan_bad_port():
    assert run("GCP-VPC-01", firewall(allowed=[{"IPProtocol": "tcp", "ports": ["rdp"]}]))["status"] == CANNOT_SCAN


# ---------- generic robustness ----------

def test_missing_resource_id_is_cannot_scan():
    assert run("AWS-RDS-01", {"publicly_accessible": True})["status"] == CANNOT_SCAN


def test_non_object_resource_is_cannot_scan():
    check = next(c for c in CHECKS if c.id == "AWS-RDS-01")
    assert run_check_on_resource(check, ACCOUNT, "garbage", SNAPSHOT)["status"] == CANNOT_SCAN
