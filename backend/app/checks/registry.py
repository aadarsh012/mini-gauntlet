"""The check registry.

A check is a plain function that looks at ONE resource and returns
(status, details). To add a check, write a function in aws.py / azure.py /
gcp.py and put @register_check(...) on top of it. Nothing else needs to change.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

PASS = "PASS"
FAIL = "FAIL"
CANNOT_SCAN = "CANNOT_SCAN"

SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

# A check function gets the resource and the snapshot time, returns (status, details).
CheckFunction = Callable[[dict, datetime], tuple[str, str]]


class CannotScan(Exception):
    """Raised by a check when a resource's fields can't be evaluated."""


@dataclass
class Check:
    id: str
    title: str
    severity: str
    provider: str
    collection: str
    id_field: str
    run: CheckFunction


CHECKS: list[Check] = []


def register_check(id, title, severity, provider, collection, id_field):
    """Decorator that adds the function below it to CHECKS."""

    def decorator(func: CheckFunction) -> CheckFunction:
        CHECKS.append(Check(id, title, severity, provider, collection, id_field, func))
        return func

    return decorator
