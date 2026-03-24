"""
Public Impact API — NLYT

GET /api/impact          → Aggregated public impact statistics (no auth required)
GET /api/impact/charity  → Charity-focused impact with contribution history (no auth required)
"""
import sys
sys.path.append('/app/backend')

from fastapi import APIRouter, Query
from services.distribution_service import get_public_impact, get_public_charity_details

router = APIRouter()


@router.get("")
@router.get("/")
async def public_impact():
    """Public endpoint: returns cached global impact statistics."""
    return get_public_impact()


@router.get("/charity")
async def public_charity_impact(
    limit: int = Query(default=20, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
):
    """Public endpoint: charity-focused impact with paginated contribution history."""
    return get_public_charity_details(limit=limit, skip=skip)
