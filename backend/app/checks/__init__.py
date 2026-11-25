# Importing the provider modules runs their @register_check decorators,
# which fills CHECKS with every check.
from . import aws, azure, gcp  # noqa: F401
from .registry import CANNOT_SCAN, CHECKS, FAIL, PASS, SEVERITIES, CannotScan, Check

__all__ = ["CHECKS", "Check", "CannotScan", "PASS", "FAIL", "CANNOT_SCAN", "SEVERITIES"]
