"""
Shared rate limiter — single instance used across all routers.
Import this in any router that needs rate limiting.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _get_real_ip(request: Request) -> str:
    """
    Extract real client IP from proxy headers.
    Priority: X-Real-IP > X-Forwarded-For > request.client.host
    """
    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip

    x_forwarded = request.headers.get("x-forwarded-for")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()

    return get_remote_address(request)


limiter = Limiter(
    key_func=_get_real_ip,
    default_limits=["200/minute"],
    storage_uri="memory://",
)
