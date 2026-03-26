"""
User Settings / Appointment Defaults Router
Manages user profile settings and default appointment parameters.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
import os
from datetime import datetime, timezone

import sys
sys.path.append('/app/backend')
from middleware.auth_middleware import get_current_user
from routers.charity_associations import is_valid_association

from database import db
router = APIRouter()


# System constant — must match appointments.py
PLATFORM_COMMISSION_PERCENT = float(os.environ.get('PLATFORM_COMMISSION_PERCENT', '20'))


class AppointmentDefaults(BaseModel):
    """Default settings for appointment creation"""
    # Engagement rules defaults
    default_cancellation_hours: Optional[int] = Field(24, ge=1, le=168, description="Délai d'annulation par défaut (heures)")
    default_late_tolerance_minutes: Optional[int] = Field(15, ge=0, le=60, description="Retard toléré par défaut (minutes)")
    default_penalty_amount: Optional[float] = Field(50.0, ge=0, le=10000, description="Montant de pénalité par défaut (€)")
    default_penalty_currency: Optional[str] = Field("eur", description="Devise de pénalité")
    
    # Distribution defaults (percentages, must sum to 100 with platform)
    default_participant_percent: Optional[float] = Field(70.0, ge=0, le=100, description="Part participant affecté (%)")
    default_charity_percent: Optional[float] = Field(0.0, ge=0, le=100, description="Part don caritatif (%)")
    # Platform percent is calculated: 100 - participant - charity
    
    # Charity association
    default_charity_association_id: Optional[str] = Field(None, description="Association caritative par défaut")


class UserSettingsUpdate(BaseModel):
    """Update user settings including appointment defaults"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    default_workspace_id: Optional[str] = None
    
    # Appointment defaults
    appointment_defaults: Optional[AppointmentDefaults] = None


@router.get("/me")
async def get_user_settings(user: dict = Depends(get_current_user)):
    """
    Get current user's settings including appointment defaults.
    """
    user_data = db.users.find_one(
        {"user_id": user['user_id']},
        {"_id": 0, "password_hash": 0}
    )
    
    if not user_data:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    # Ensure appointment_defaults exists with fallback values
    if "appointment_defaults" not in user_data:
        user_data["appointment_defaults"] = {
            "default_cancellation_hours": 24,
            "default_late_tolerance_minutes": 15,
            "default_penalty_amount": 50.0,
            "default_penalty_currency": "eur",
            "default_participant_percent": 70.0,
            "default_charity_percent": 0.0,
            "default_charity_association_id": None
        }
    
    return user_data


@router.put("/me")
async def update_user_settings(
    settings: UserSettingsUpdate,
    user: dict = Depends(get_current_user)
):
    """
    Update user settings including appointment defaults.
    """
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    # Update basic profile fields
    if settings.first_name is not None:
        update_data["first_name"] = settings.first_name
    if settings.last_name is not None:
        update_data["last_name"] = settings.last_name
    if settings.phone is not None:
        update_data["phone"] = settings.phone
    if settings.default_workspace_id is not None:
        # Verify workspace exists and belongs to user
        ws = db.workspaces.find_one({"workspace_id": settings.default_workspace_id, "owner_id": user['user_id']}, {"_id": 0})
        if not ws:
            raise HTTPException(status_code=400, detail="Workspace introuvable")
        update_data["default_workspace_id"] = settings.default_workspace_id
    
    # Update appointment defaults
    if settings.appointment_defaults:
        defaults = settings.appointment_defaults.dict(exclude_none=True)
        
        # Validate charity association if provided
        if "default_charity_association_id" in defaults:
            assoc_id = defaults["default_charity_association_id"]
            if assoc_id and not is_valid_association(assoc_id):
                raise HTTPException(
                    status_code=400, 
                    detail="Association caritative non valide. Veuillez choisir parmi la liste des associations validées."
                )
        
        # Validate distribution percentages against system platform commission
        participant_pct = defaults.get("default_participant_percent", 70.0)
        charity_pct = defaults.get("default_charity_percent", 0.0)
        max_distributable = 100 - PLATFORM_COMMISSION_PERCENT
        
        total = round(participant_pct + charity_pct, 2)
        if total != max_distributable:
            raise HTTPException(
                status_code=400,
                detail=f"La somme participant ({participant_pct}%) + charité ({charity_pct}%) doit être exactement {max_distributable}%. Commission plateforme fixée à {PLATFORM_COMMISSION_PERCENT}%."
            )
        
        # Merge with existing defaults
        existing_user = db.users.find_one({"user_id": user['user_id']}, {"_id": 0})
        existing_defaults = existing_user.get("appointment_defaults", {}) if existing_user else {}
        
        merged_defaults = {**existing_defaults, **defaults}
        update_data["appointment_defaults"] = merged_defaults
    
    # Perform update
    result = db.users.update_one(
        {"user_id": user['user_id']},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    # Return updated user
    updated_user = db.users.find_one(
        {"user_id": user['user_id']},
        {"_id": 0, "password_hash": 0}
    )
    
    return {
        "success": True,
        "message": "Paramètres mis à jour avec succès",
        "user": updated_user
    }


@router.get("/me/appointment-defaults")
async def get_appointment_defaults(user: dict = Depends(get_current_user)):
    """
    Get only appointment defaults for the current user.
    Used by the appointment wizard to pre-fill values.
    """
    # First verify user exists
    user_exists = db.users.find_one({"user_id": user['user_id']}, {"_id": 0, "user_id": 1})
    
    if not user_exists:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    # Get user data with defaults field
    user_data = db.users.find_one(
        {"user_id": user['user_id']},
        {"_id": 0, "appointment_defaults": 1}
    )
    
    # Return defaults with fallback values
    defaults = user_data.get("appointment_defaults", {}) if user_data else {}
    
    return {
        "default_cancellation_hours": defaults.get("default_cancellation_hours", 24),
        "default_late_tolerance_minutes": defaults.get("default_late_tolerance_minutes", 15),
        "default_penalty_amount": defaults.get("default_penalty_amount", 50.0),
        "default_penalty_currency": defaults.get("default_penalty_currency", "eur"),
        "default_participant_percent": defaults.get("default_participant_percent", 70.0),
        "default_charity_percent": defaults.get("default_charity_percent", 0.0),
        "default_charity_association_id": defaults.get("default_charity_association_id"),
        "platform_commission_percent": PLATFORM_COMMISSION_PERCENT,
        "has_custom_defaults": bool(defaults)
    }


# ────────────────────────────────────────────────────────
#  Default Payment Method (Stripe guarantee card)
# ────────────────────────────────────────────────────────

@router.get("/me/payment-method")
async def get_payment_method(user: dict = Depends(get_current_user)):
    """
    Return the user's saved default payment method for organizer guarantees.
    """
    user_data = db.users.find_one(
        {"user_id": user['user_id']},
        {"_id": 0, "default_payment_method_id": 1, "default_payment_method_last4": 1,
         "default_payment_method_brand": 1, "default_payment_method_exp": 1,
         "payment_method_consent": 1, "payment_method_setup_at": 1,
         "stripe_customer_id": 1}
    )

    if not user_data or not user_data.get("default_payment_method_id"):
        return {"has_payment_method": False}

    return {
        "has_payment_method": True,
        "payment_method": {
            "last4": user_data.get("default_payment_method_last4"),
            "brand": user_data.get("default_payment_method_brand"),
            "exp": user_data.get("default_payment_method_exp"),
            "consent": user_data.get("payment_method_consent", False),
            "setup_at": user_data.get("payment_method_setup_at"),
        }
    }


@router.post("/me/setup-payment-method")
async def setup_payment_method(user: dict = Depends(get_current_user)):
    """
    Initiate Stripe Checkout (setup mode) to save a default payment method.
    Returns a checkout_url to redirect the user to.
    """
    from services.stripe_guarantee_service import StripeGuaranteeService

    user_data = db.users.find_one(
        {"user_id": user['user_id']},
        {"_id": 0, "email": 1, "first_name": 1, "last_name": 1}
    )
    if not user_data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')
    user_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()

    result = StripeGuaranteeService.setup_default_payment_method_session(
        user_id=user['user_id'],
        user_email=user_data['email'],
        user_name=user_name or user_data['email'],
        frontend_url=frontend_url
    )

    if not result.get("success"):
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=result.get("error", "Erreur Stripe"))

    return result


@router.get("/me/payment-method/check-setup")
async def check_payment_setup(session_id: str, user: dict = Depends(get_current_user)):
    """
    Polling endpoint — called by frontend after Stripe redirect to verify
    that the default payment method was saved (webhook may be delayed).
    """
    from services.stripe_guarantee_service import StripeGuaranteeService
    return StripeGuaranteeService.check_default_payment_setup(session_id, user['user_id'])


@router.delete("/me/payment-method")
async def remove_payment_method(user: dict = Depends(get_current_user)):
    """
    Remove the saved default payment method.
    Future guarantees will require Stripe redirect.
    """
    db.users.update_one(
        {"user_id": user['user_id']},
        {"$unset": {
            "default_payment_method_id": "",
            "default_payment_method_last4": "",
            "default_payment_method_brand": "",
            "default_payment_method_exp": "",
            "payment_method_consent": "",
            "payment_method_setup_at": ""
        },
        "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    return {"success": True, "message": "Moyen de paiement supprimé"}
