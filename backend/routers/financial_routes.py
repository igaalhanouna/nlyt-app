"""
Financial Results API — User-centric engagement results and solidarity impact.

GET /api/financial/my-results → Aggregated financial synthesis for the logged-in user
"""
import sys
sys.path.append('/app/backend')

from fastapi import APIRouter, Request
from middleware.auth_middleware import get_current_user
from database import db

router = APIRouter()


@router.get("/my-results")
async def get_my_financial_results(request: Request):
    """
    Aggregated financial results for the logged-in user.
    Returns:
      - synthesis: total_received_cents, total_paid_cents, net_balance_cents
      - engagements: per-appointment financial impact items
      - solidarity: total donated + per-association breakdown
    """
    user = await get_current_user(request)
    user_id = user["user_id"]

    # Fetch all non-cancelled distributions involving this user
    distributions = list(db.distributions.find(
        {
            "status": {"$nin": ["cancelled"]},
            "$or": [
                {"no_show_user_id": user_id},
                {"beneficiaries.user_id": user_id},
            ],
        },
        {"_id": 0},
    ).sort("created_at", -1))

    # Collect all appointment IDs for enrichment
    apt_ids = list({d["appointment_id"] for d in distributions if d.get("appointment_id")})
    apt_map = {}
    if apt_ids:
        for a in db.appointments.find(
            {"appointment_id": {"$in": apt_ids}},
            {"_id": 0, "appointment_id": 1, "title": 1, "start_datetime": 1,
             "appointment_type": 1, "penalty_currency": 1,
             "charity_association_id": 1, "charity_association_name": 1},
        ):
            apt_map[a["appointment_id"]] = a

    # Collect charity association names
    charity_ids = {a.get("charity_association_id") for a in apt_map.values() if a.get("charity_association_id")}
    charity_names = {}
    if charity_ids:
        for ca in db.charity_associations.find(
            {"association_id": {"$in": list(charity_ids)}},
            {"_id": 0, "association_id": 1, "name": 1},
        ):
            charity_names[ca["association_id"]] = ca.get("name", "Association")

    # Aggregate per-appointment
    total_received_cents = 0
    total_paid_cents = 0
    total_charity_cents = 0
    charity_by_association = {}  # assoc_id → {name, total_cents, count}
    engagements_map = {}  # appointment_id → engagement item

    for dist in distributions:
        apt_id = dist.get("appointment_id", "")
        apt = apt_map.get(apt_id, {})
        currency = dist.get("capture_currency", apt.get("penalty_currency", "eur"))

        # Initialize engagement entry
        if apt_id not in engagements_map:
            engagements_map[apt_id] = {
                "appointment_id": apt_id,
                "title": apt.get("title", "Engagement"),
                "date": apt.get("start_datetime", ""),
                "appointment_type": apt.get("appointment_type", "physical"),
                "currency": currency,
                "received_cents": 0,
                "paid_cents": 0,
                "charity_cents": 0,
                "charity_association_name": None,
                "type": None,  # "paid" | "received" | "both" | "neutral"
            }
        eng = engagements_map[apt_id]

        # Check if user was the no_show (they paid)
        if dist.get("no_show_user_id") == user_id:
            capture = dist.get("capture_amount_cents", 0)
            eng["paid_cents"] += capture
            total_paid_cents += capture

        # Check if user received compensation as a beneficiary
        for b in dist.get("beneficiaries", []):
            if b.get("user_id") == user_id and b.get("role") in ("organizer", "affected"):
                amt = b.get("amount_cents", 0)
                eng["received_cents"] += amt
                total_received_cents += amt

            # Track charity contributions (regardless of user role)
            if b.get("role") == "charity" and b.get("amount_cents", 0) > 0:
                c_amt = b["amount_cents"]
                eng["charity_cents"] += c_amt
                total_charity_cents += c_amt

                assoc_id = b.get("user_id", "unknown")
                assoc_name = apt.get("charity_association_name") or charity_names.get(assoc_id, "Association")
                eng["charity_association_name"] = assoc_name

                if assoc_id not in charity_by_association:
                    charity_by_association[assoc_id] = {
                        "association_id": assoc_id,
                        "name": assoc_name,
                        "total_cents": 0,
                        "count": 0,
                    }
                charity_by_association[assoc_id]["total_cents"] += c_amt
                charity_by_association[assoc_id]["count"] += 1

    # Determine engagement type and build wording
    engagements = []
    for eng in engagements_map.values():
        if eng["paid_cents"] > 0 and eng["received_cents"] > 0:
            eng["type"] = "both"
        elif eng["paid_cents"] > 0:
            eng["type"] = "paid"
        elif eng["received_cents"] > 0:
            eng["type"] = "received"
        else:
            eng["type"] = "neutral"
        engagements.append(eng)

    # Sort by date descending (most recent first)
    engagements.sort(key=lambda e: e.get("date", ""), reverse=True)

    net_balance_cents = total_received_cents - total_paid_cents

    # Charity associations sorted by total
    associations = sorted(
        charity_by_association.values(),
        key=lambda a: a["total_cents"],
        reverse=True,
    )

    return {
        "synthesis": {
            "total_received_cents": total_received_cents,
            "total_paid_cents": total_paid_cents,
            "net_balance_cents": net_balance_cents,
            "currency": "eur",
            "engagement_count": len(engagements),
        },
        "engagements": engagements,
        "solidarity": {
            "total_charity_cents": total_charity_cents,
            "associations": associations,
        },
    }
