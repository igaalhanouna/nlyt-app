"""
Result Cards — Shareable viral cards post-engagement.
3 types: engagement_respected, compensation_received, charity_donation.
"""
from fastapi import APIRouter, HTTPException, Request
from database import db
from middleware.auth_middleware import get_current_user
from utils.date_utils import now_utc
import uuid

router = APIRouter()


@router.post("")
async def create_result_card(request: Request):
    """Generate a shareable result card from an appointment outcome."""
    user = await get_current_user(request)
    body = await request.json()

    appointment_id = body.get("appointment_id")
    card_type = body.get("card_type")

    if card_type not in ("engagement_respected", "compensation_received", "charity_donation"):
        raise HTTPException(status_code=400, detail="Type de carte invalide")

    if not appointment_id:
        raise HTTPException(status_code=400, detail="appointment_id requis")

    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        raise HTTPException(status_code=404, detail="Engagement introuvable")

    user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()

    # Idempotence: check if card already exists for this user+appointment+type
    existing = db.result_cards.find_one({
        "user_id": user["user_id"],
        "appointment_id": appointment_id,
        "card_type": card_type,
    }, {"_id": 0})
    if existing:
        return existing

    card = {
        "card_id": str(uuid.uuid4()),
        "card_type": card_type,
        "user_id": user["user_id"],
        "user_name": user_name,
        "appointment_id": appointment_id,
        "appointment_title": appointment.get("title", ""),
        "appointment_date": appointment.get("start_datetime", ""),
        "appointment_timezone": appointment.get("appointment_timezone", "Europe/Paris"),
        "amount_cents": 0,
        "currency": appointment.get("penalty_currency", "eur").upper(),
        "association_name": None,
        "view_count": 0,
        "created_at": now_utc().isoformat(),
    }

    # Enrich based on card type
    if card_type == "engagement_respected":
        record = db.attendance_records.find_one({
            "appointment_id": appointment_id,
            "participant_email": user.get("email"),
            "outcome": {"$in": ["on_time", "late"]},
        }, {"_id": 0})
        if not record:
            # Also check if user is the organizer who was present
            is_organizer = appointment.get("organizer_id") == user["user_id"]
            if not is_organizer:
                raise HTTPException(status_code=400, detail="Aucune preuve de présence trouvée")

    elif card_type == "compensation_received":
        dist = db.distributions.find_one({
            "appointment_id": appointment_id,
            "beneficiaries.user_id": user["user_id"],
            "beneficiaries.role": "compensation",
        }, {"_id": 0})
        if dist:
            for b in dist.get("beneficiaries", []):
                if b.get("user_id") == user["user_id"] and b.get("role") == "compensation":
                    card["amount_cents"] = b.get("amount_cents", 0)
                    card["currency"] = dist.get("capture_currency", "eur").upper()
                    break
        else:
            raise HTTPException(status_code=400, detail="Aucune compensation trouvée")

    elif card_type == "charity_donation":
        dist = db.distributions.find_one({
            "appointment_id": appointment_id,
            "beneficiaries.role": "charity",
        }, {"_id": 0})
        if dist:
            for b in dist.get("beneficiaries", []):
                if b.get("role") == "charity":
                    card["amount_cents"] = b.get("amount_cents", 0)
                    card["currency"] = dist.get("capture_currency", "eur").upper()
                    # Find association name
                    assoc_id = b.get("user_id")
                    if assoc_id:
                        assoc = db.charity_associations.find_one({"association_id": assoc_id}, {"_id": 0, "name": 1})
                        card["association_name"] = assoc.get("name") if assoc else None
                    break
        # Allow charity card even without distribution (organizer perspective)

    db.result_cards.insert_one(card)
    # Remove _id that MongoDB adds
    card.pop("_id", None)

    return card


@router.get("/my-cards")
async def list_my_cards(request: Request):
    """List all result cards for the current user."""
    user = await get_current_user(request)
    cards = list(db.result_cards.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1))
    return cards


@router.get("/{card_id}")
async def get_result_card(card_id: str):
    """Public endpoint — no auth required. Returns card data for rendering."""
    card = db.result_cards.find_one({"card_id": card_id}, {"_id": 0})
    if not card:
        raise HTTPException(status_code=404, detail="Carte introuvable")

    # Increment view count
    db.result_cards.update_one({"card_id": card_id}, {"$inc": {"view_count": 1}})

    return card
