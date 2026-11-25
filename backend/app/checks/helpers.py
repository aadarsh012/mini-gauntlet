"""Small helpers shared by the checks."""

from .registry import CannotScan

# Ports we care about for the "SSH or RDP open to the internet" checks.
ADMIN_PORTS = {22: "SSH", 3389: "RDP"}

# Sources that mean "anyone on the internet".
INTERNET_CIDRS = {"0.0.0.0/0", "::/0"}


def require_bool(resource: dict, field: str) -> bool:
    """Return resource[field], or raise CannotScan if it isn't a true/false value."""
    value = resource.get(field)
    if not isinstance(value, bool):
        raise CannotScan(f"field '{field}' should be true or false, got {value!r}")
    return value


def require_list(value, what: str) -> list:
    if not isinstance(value, list):
        raise CannotScan(f"{what} should be a list, got {value!r}")
    return value


def require_dict(value, what: str) -> dict:
    if not isinstance(value, dict):
        raise CannotScan(f"{what} should be an object, got {value!r}")
    return value


def require_port(value, what: str) -> int:
    """Ports must be real integers (bool is a subclass of int, so exclude it)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise CannotScan(f"{what} is not a number: {value!r}")
    return value


def parse_port_range(text) -> tuple[int, int]:
    """Turn "22" into (22, 22), "3380-3400" into (3380, 3400) and "*" into all ports."""
    if not isinstance(text, str):
        raise CannotScan(f"port {text!r} is not a string")
    text = text.strip()
    if text == "*":
        return (0, 65535)
    parts = text.split("-")
    if len(parts) > 2 or not all(p.strip().isdigit() for p in parts):
        raise CannotScan(f"port {text!r} is not a number or range")
    low = int(parts[0])
    high = int(parts[-1])
    return (low, high)


def admin_ports_in_range(low: int, high: int) -> list[str]:
    """Return e.g. ["22 (SSH)"] for the admin ports inside low..high."""
    return [f"{port} ({name})" for port, name in ADMIN_PORTS.items() if low <= port <= high]
