"""Score and count helpers."""

from .checks import CANNOT_SCAN, FAIL, PASS, SEVERITIES


def score(passed: int, failed: int) -> float | None:
    """100 * PASS / (PASS + FAIL), one decimal. None when there is nothing to score."""
    if passed + failed == 0:
        return None
    return round(100 * passed / (passed + failed), 1)


def status_counts(findings: list[dict]) -> dict:
    counts = {PASS: 0, FAIL: 0, CANNOT_SCAN: 0}
    for finding in findings:
        counts[finding["status"]] += 1
    return counts


def fail_counts_by_severity(findings: list[dict]) -> dict:
    counts = {severity: 0 for severity in SEVERITIES}
    for finding in findings:
        if finding["status"] == FAIL:
            counts[finding["severity"]] += 1
    return counts


def score_of(findings: list[dict]) -> float | None:
    counts = status_counts(findings)
    return score(counts[PASS], counts[FAIL])
