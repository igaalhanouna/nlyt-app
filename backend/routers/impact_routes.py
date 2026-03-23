"""
Public Impact API — NLYT

GET /api/impact → Aggregated public impact statistics (no auth required)
"""
import sys
sys.path.append('/app/backend')

from fastapi import APIRouter
from services.distribution_service import get_public_impact

router = APIRouter()


@router.get("")
@router.get("/")
async def public_impact():
    """Public endpoint: returns cached global impact statistics."""
    return get_public_impact()
