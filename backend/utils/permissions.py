"""
Centralized Role-Permission Mapping — NLYT

Single source of truth for role-based access control.
The mapping is designed to be easily extensible:
- Adding a new role = adding one entry to ROLE_PERMISSIONS
- Future evolution to multi-role (roles: []) only requires
  changing has_permission() to iterate over a list instead of a single string.
"""
import logging
from fastapi import HTTPException, Request
from middleware.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

ROLE_PERMISSIONS = {
    "admin": ["*"],
    "arbitrator": ["admin:arbitration"],
    "payer": ["admin:payouts", "admin:stale-payouts"],
    "accreditor": ["admin:associations"],
    "user": [],
}

ALL_ROLES = list(ROLE_PERMISSIONS.keys())


def has_permission(role: str, permission: str) -> bool:
    """Check if a role grants a specific permission."""
    perms = ROLE_PERMISSIONS.get(role, [])
    return "*" in perms or permission in perms


def has_any_admin_permission(role: str) -> bool:
    """Check if a role has at least one admin permission (for menu visibility)."""
    perms = ROLE_PERMISSIONS.get(role, [])
    return "*" in perms or any(p.startswith("admin:") for p in perms)


async def require_permission(request: Request, permission: str) -> dict:
    """FastAPI dependency: authenticate + check permission. Returns user dict."""
    user = await get_current_user(request)
    role = user.get("role", "user")
    if not has_permission(role, permission):
        logger.warning(f"[PERMISSION] Denied: {user.get('email')} (role={role}) tried {permission}")
        raise HTTPException(status_code=403, detail="Acces non autorise pour votre role")
    return user
