"""
utils.py — Shared utility helpers for the HTTP DMS Server.

Keeps cross-cutting concerns (IP extraction, timing) out of both
the route and service layers. All functions are pure and stateless.
"""

import time
from typing import Optional

from flask import Request


def get_client_ip(request: Request) -> str:
    """
    Extracts the real client IP address from an HTTP request.

    When the server sits behind a reverse proxy (Nginx, HAProxy, AWS ALB),
    the actual client IP is forwarded in the 'X-Forwarded-For' header rather
    than the direct socket address. Only the leftmost (original) IP is used
    to prevent header spoofing by intermediate proxies.

    Falls back to request.remote_addr when the header is absent (direct
    connections, development, or Waitress without a reverse proxy).

    Args:
        request: The Flask Request object for the current HTTP request.

    Returns:
        The client IP address string (IPv4 or IPv6).
    """
    forwarded_for: Optional[str] = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For may contain a comma-separated chain of IPs.
        # The leftmost entry is the original client IP.
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "unknown"


def elapsed_ms(start_time: float) -> float:
    """
    Computes elapsed milliseconds since a monotonic start timestamp.

    Args:
        start_time: Value returned by time.monotonic() at request start.

    Returns:
        Elapsed time in milliseconds, rounded to 2 decimal places.
    """
    return round((time.monotonic() - start_time) * 1000, 2)
