"""
Invitation Router
Handles public invitation viewing and participant responses (accept/decline)
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
import sys
sys.path.append('/app/backend')
from utils.date_utils import now_utc, now_utc_iso, format_datetime_fr, parse_iso_datetime, normalize_to_utc
from datetime import datetime, timezone, timedelta
from rate_limiter import limiter

from database import db
router = APIRouter()



async def send_confirmation_email_once(participant: dict, appointment: dict):
    """
    Send the definitive confirmation email exactly ONCE after engagement is finalized.
    Uses 'confirmation_email_sent' flag on participant for idempotence.
    Called from both the webhook path and the polling-fallback path.
    """
    pid = participant.get('participant_id')

    # Idempotence: skip if already sent
    if participant.get('confirmation_email_sent'):
        return False

    # Atomic flag: set confirmation_email_sent=True BEFORE sending
    # so a concurrent call won't send a duplicate
    result = db.participants.update_one(
        {"participant_id": pid, "confirmation_email_sent": {"$ne": True}},
        {"$set": {"confirmation_email_sent": True, "confirmation_email_sent_at": now_utc_iso()}}
    )
    if result.modified_count == 0:
        return False  # Another path already claimed it

    try:
        from services.email_service import EmailService

        organizer = db.users.find_one(
            {"user_id": appointment.get('organizer_id')}, {"_id": 0}
        )
        organizer_name = (
            f"{organizer.get('first_name', '')} {organizer.get('last_name', '')}".strip()
            if organizer else "L'organisateur"
        )

        p_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()
        if not p_name:
            p_name = participant.get('email', '').split('@')[0]

        frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')
        apt_id = appointment['appointment_id']
        token = participant.get('invitation_token', '')

        ics_link = f"{frontend_url}/api/calendar/export/ics/{apt_id}?token={token}"
        invitation_link = f"{frontend_url}/invitation/{token}"

        # Proof link for video, invitation link (with check-in anchor) for physical
        proof_link = None
        if appointment.get('appointment_type') == 'video':
            proof_link = f"{frontend_url}/proof/{apt_id}?token={token}"

        await EmailService.send_acceptance_confirmation_email(
            to_email=participant.get('email', ''),
            to_name=p_name,
            organizer_name=organizer_name,
            appointment_title=appointment.get('title', ''),
            appointment_datetime=appointment.get('start_datetime', ''),
            location=appointment.get('location'),
            penalty_amount=appointment.get('penalty_amount'),
            penalty_currency=appointment.get('penalty_currency', 'EUR'),
            cancellation_deadline_hours=appointment.get('cancellation_deadline_hours'),
            ics_link=ics_link,
            invitation_link=invitation_link,
            appointment_timezone=appointment.get('appointment_timezone', 'Europe/Paris'),
            proof_link=proof_link,
            appointment_type=appointment.get('appointment_type', 'physical'),
            meeting_provider=appointment.get('meeting_provider'),
        )
        print(f"[EMAIL] Confirmation email sent to {participant.get('email')} for appointment {apt_id}")
        return True
    except Exception as e:
        print(f"[EMAIL] Failed to send confirmation email to {participant.get('email')}: {e}")
        # Roll back the flag so the other path can retry
        db.participants.update_one(
            {"participant_id": pid},
            {"$unset": {"confirmation_email_sent": "", "confirmation_email_sent_at": ""}}
        )
        return False


class InvitationResponse(BaseModel):
    action: str  # "accept" or "decline"


@router.get("/{token}")
@limiter.limit("30/minute")
async def get_invitation_details(request: Request, token: str):
    """
    Public endpoint to view invitation details via secure token.
    No authentication required.
    """
    # Find participant by invitation token
    participant = db.participants.find_one(
        {"invitation_token": token},
        {"_id": 0}
    )
    
    if not participant:
        raise HTTPException(status_code=404, detail="Invitation non trouvée ou expirée")
    
    # Get appointment details
    appointment = db.appointments.find_one(
        {"appointment_id": participant['appointment_id']},
        {"_id": 0}
    )
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous associé introuvable")
    
    # Get organizer info (limited for privacy)
    organizer = db.users.find_one(
        {"user_id": appointment['organizer_id']},
        {"_id": 0, "first_name": 1, "last_name": 1}
    )
    organizer_name = "Organisateur"
    if organizer:
        organizer_name = f"{organizer.get('first_name', '')} {organizer.get('last_name', '')}".strip()
    
    # Get policy snapshot for rules
    policy_snapshot = None
    if appointment.get('policy_snapshot_id'):
        policy_snapshot = db.policy_snapshots.find_one(
            {"snapshot_id": appointment['policy_snapshot_id']},
            {"_id": 0}
        )
    
    # Get other participants (limited info - just count and names)
    other_participants = list(db.participants.find(
        {
            "appointment_id": participant['appointment_id'],
            "participant_id": {"$ne": participant['participant_id']}
        },
        {"_id": 0, "first_name": 1, "last_name": 1, "status": 1}
    ))
    
    # Parse date for display (in French) — convert UTC to Europe/Paris for formatted_date
    start_dt = parse_iso_datetime(appointment.get('start_datetime', ''))
    formatted_date = None
    if start_dt:
        formatted_date = format_datetime_fr(start_dt, 'Europe/Paris')

    # Calculate cancellation deadline
    cancellation_deadline = None
    cancellation_deadline_dt = None
    can_cancel = False
    deadline_passed = False

    if start_dt and appointment.get('cancellation_deadline_hours'):
        cancellation_deadline_dt = start_dt - timedelta(hours=appointment['cancellation_deadline_hours'])
        cancellation_deadline = format_datetime_fr(cancellation_deadline_dt, 'Europe/Paris')
        
        # Check if participant can still cancel (deadline not passed)
        now = datetime.now(timezone.utc)
        deadline_passed = now >= cancellation_deadline_dt
        
        # Can cancel if: accepted (with or without guarantee) AND deadline not passed
        if participant.get('status') in ('accepted', 'accepted_guaranteed') and not deadline_passed:
            can_cancel = True
    
    # Normalize start_datetime to UTC for consistent frontend display
    utc_start = normalize_to_utc(appointment.get('start_datetime', ''))

    # Check guarantee revalidation status
    guarantee_revalidation = None
    if participant.get('guarantee_id'):
        guarantee = db.payment_guarantees.find_one(
            {"guarantee_id": participant['guarantee_id']},
            {"_id": 0, "requires_revalidation": 1, "revalidation_reason": 1,
             "revalidation_flagged_at": 1, "capture_deadline": 1, "status": 1}
        )
        if guarantee and guarantee.get('requires_revalidation'):
            guarantee_revalidation = {
                "requires_revalidation": True,
                "reason": guarantee.get('revalidation_reason', ''),
                "flagged_at": guarantee.get('revalidation_flagged_at'),
                "guarantee_status": guarantee.get('status')
            }

    # ACCESS CONTROL: Only expose meeting details once engagement is finalized.
    # 'accepted' = no guarantee required; 'accepted_guaranteed' = guarantee paid.
    participant_status = participant.get('status', 'invited')
    is_engagement_finalized = participant_status in ('accepted', 'accepted_guaranteed')

    # Build response with limited, privacy-conscious data
    return {
        "invitation_token": token,
        "participant": {
            "participant_id": participant['participant_id'],
            "first_name": participant.get('first_name', ''),
            "last_name": participant.get('last_name', ''),
            "email": participant.get('email', ''),
            "status": participant_status,
            "accepted_at": participant.get('accepted_at'),
            "declined_at": participant.get('declined_at'),
            "cancelled_at": participant.get('cancelled_at'),
            "guaranteed_at": participant.get('guaranteed_at'),
            "guarantee_id": participant.get('guarantee_id')
        },
        "appointment": {
            "appointment_id": appointment['appointment_id'],
            "title": appointment.get('title', ''),
            "appointment_type": appointment.get('appointment_type', ''),
            "location": appointment.get('location', ''),
            "meeting_provider": appointment.get('meeting_provider', ''),
            "meeting_join_url": appointment.get('meeting_join_url', '') if is_engagement_finalized else '',
            "start_datetime": utc_start,
            "formatted_date": formatted_date,
            "duration_minutes": appointment.get('duration_minutes', 60),
            "tolerated_delay_minutes": appointment.get('tolerated_delay_minutes', 0),
            "status": appointment.get('status', '')
        },
        "organizer": {
            "name": organizer_name
        },
        "engagement_rules": {
            "cancellation_deadline_hours": appointment.get('cancellation_deadline_hours', 24),
            "cancellation_deadline_formatted": cancellation_deadline,
            "cancellation_deadline_passed": deadline_passed,
            "can_cancel": can_cancel,
            "tolerated_delay_minutes": appointment.get('tolerated_delay_minutes', 0),
            "penalty_amount": appointment.get('penalty_amount', 0),
            "penalty_currency": appointment.get('penalty_currency', 'EUR').upper(),
            "affected_compensation_percent": appointment.get('affected_compensation_percent', 70),
            "platform_commission_percent": appointment.get('platform_commission_percent', 30),
            "charity_percent": appointment.get('charity_percent', 0),
            "charity_association_name": appointment.get('charity_association_name', None)
        },
        "other_participants": [
            {
                "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or "Participant",
                "status": p.get('status', 'invited')
            }
            for p in other_participants
        ],
        "policy_summary": policy_snapshot.get('summary') if policy_snapshot else None,
        "guarantee_revalidation": guarantee_revalidation,
        "has_existing_account": db.users.count_documents({"email": participant.get('email', ''), "is_verified": True}) > 0
    }


@router.post("/{token}/respond")
@limiter.limit("10/minute")
async def respond_to_invitation(request: Request, token: str, response: InvitationResponse):
    """
    Public endpoint to accept or decline an invitation.
    
    For acceptance:
    - If penalty_amount > 0: Creates Stripe session for guarantee, returns checkout_url
    - If penalty_amount = 0: Directly accepts without Stripe
    
    For decline: Directly declines
    """
    if response.action not in ["accept", "decline"]:
        raise HTTPException(status_code=400, detail="Action invalide. Utilisez 'accept' ou 'decline'.")
    
    # Find participant by token
    participant = db.participants.find_one(
        {"invitation_token": token},
        {"_id": 0}
    )
    
    if not participant:
        raise HTTPException(status_code=404, detail="Invitation non trouvée ou expirée")
    
    # Check if already responded
    current_status = participant.get('status', 'invited')
    if current_status in ['accepted', 'accepted_guaranteed', 'accepted_pending_guarantee', 'declined']:
        raise HTTPException(
            status_code=400, 
            detail=f"Vous avez déjà répondu à cette invitation (statut actuel: {current_status})"
        )
    
    # Get appointment to check if still valid
    appointment = db.appointments.find_one(
        {"appointment_id": participant['appointment_id']},
        {"_id": 0}
    )
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous associé introuvable")
    
    # Check if appointment is still active
    if appointment.get('status') in ['cancelled', 'completed']:
        raise HTTPException(status_code=400, detail="Ce rendez-vous n'est plus actif")
    
    # Check if appointment hasn't started yet
    start_dt = parse_iso_datetime(appointment.get('start_datetime', ''))
    if start_dt and datetime.now(timezone.utc) >= start_dt:
        raise HTTPException(status_code=400, detail="Ce rendez-vous a déjà commencé")
    
    now = now_utc_iso()
    
    if response.action == "accept":
        penalty_amount = appointment.get('penalty_amount', 0)
        
        # If there's a penalty, require Stripe guarantee
        if penalty_amount and penalty_amount > 0:
            from services.stripe_guarantee_service import StripeGuaranteeService
            
            # ── Check if user has a saved card → skip Checkout ──
            user_id = participant.get("user_id")
            if not user_id:
                user_doc = db.users.find_one({"email": participant.get("email")}, {"_id": 0, "user_id": 1})
                if user_doc:
                    user_id = user_doc["user_id"]

            if user_id:
                user_pm = db.users.find_one(
                    {"user_id": user_id, "default_payment_method_id": {"$exists": True, "$ne": None}},
                    {"_id": 0, "default_payment_method_id": 1, "stripe_customer_id": 1}
                )
                if user_pm and user_pm.get("default_payment_method_id") and user_pm.get("stripe_customer_id"):
                    reuse_result = StripeGuaranteeService.create_guarantee_with_saved_card(
                        participant_id=participant["participant_id"],
                        appointment_id=appointment["appointment_id"],
                        invitation_token=token,
                        penalty_amount=float(penalty_amount),
                        penalty_currency=appointment.get("penalty_currency", "eur"),
                        user_id=user_id,
                        stripe_customer_id=user_pm["stripe_customer_id"],
                        payment_method_id=user_pm["default_payment_method_id"],
                    )
                    if reuse_result.get("success"):
                        return {
                            "success": True,
                            "requires_guarantee": False,
                            "reused_card": True,
                            "message": "Garantie confirmée avec votre carte enregistrée",
                            "status": "accepted_guaranteed",
                            "guarantee_id": reuse_result["guarantee_id"],
                        }

            # ── No saved card → standard Checkout flow ──
            # Update status to pending guarantee
            db.participants.update_one(
                {"invitation_token": token},
                {"$set": {
                    "status": "accepted_pending_guarantee",
                    "accept_initiated_at": now,
                    "updated_at": now
                }}
            )
            
            # Get frontend URL
            frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')
            if not frontend_url:
                frontend_url = str(request.base_url).rstrip('/')
            
            # Create Stripe guarantee session
            participant_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()
            if not participant_name:
                participant_name = participant.get('email', '').split('@')[0]
            
            result = StripeGuaranteeService.create_guarantee_session(
                participant_id=participant['participant_id'],
                appointment_id=appointment['appointment_id'],
                participant_email=participant.get('email', ''),
                participant_name=participant_name,
                appointment_title=appointment.get('title', 'Rendez-vous'),
                penalty_amount=float(penalty_amount),
                penalty_currency=appointment.get('penalty_currency', 'eur'),
                frontend_url=frontend_url,
                invitation_token=token
            )
            
            if not result.get('success'):
                # Revert status if Stripe session creation failed
                db.participants.update_one(
                    {"invitation_token": token},
                    {"$set": {"status": "invited", "updated_at": now}}
                )
                raise HTTPException(
                    status_code=500, 
                    detail=f"Erreur lors de la création de la session de paiement: {result.get('error')}"
                )
            
            # Write guarantee_id to participant immediately (don't wait for webhook)
            db.participants.update_one(
                {"invitation_token": token},
                {"$set": {
                    "guarantee_id": result['guarantee_id'],
                    "stripe_session_id": result['session_id']
                }}
            )
            
            return {
                "success": True,
                "requires_guarantee": True,
                "message": "Une garantie financière est requise pour confirmer votre participation",
                "checkout_url": result['checkout_url'],
                "session_id": result['session_id'],
                "guarantee_id": result['guarantee_id'],
                "status": "accepted_pending_guarantee"
            }
        
        # No penalty - direct acceptance
        update_data = {
            "status": "accepted",
            "accepted_at": now,
            "updated_at": now
        }
        message = "Invitation acceptée avec succès"
    else:
        update_data = {
            "status": "declined",
            "declined_at": now,
            "updated_at": now
        }
        message = "Invitation déclinée"
    
    # Update participant status
    db.participants.update_one(
        {"invitation_token": token},
        {"$set": update_data}
    )
    
    # Get updated participant
    updated_participant = db.participants.find_one(
        {"invitation_token": token},
        {"_id": 0}
    )
    
    # Send confirmation email if accepted (idempotent helper)
    if response.action == "accept":
        # For direct accept (no guarantee), only send if status is 'accepted' (not pending_guarantee)
        if updated_participant.get('status') == 'accepted':
            await send_confirmation_email_once(updated_participant, appointment)
    
    return {
        "success": True,
        "message": message,
        "status": update_data['status'],
        "participant": {
            "participant_id": updated_participant['participant_id'],
            "first_name": updated_participant.get('first_name', ''),
            "last_name": updated_participant.get('last_name', ''),
            "status": updated_participant['status'],
            "accepted_at": updated_participant.get('accepted_at'),
            "declined_at": updated_participant.get('declined_at')
        }
    }



class AcceptWithAccountRequest(BaseModel):
    password: str
    action: str = "accept"

class LoginAndAcceptRequest(BaseModel):
    password: str
    action: str = "accept"


@router.post("/{token}/accept-with-account")
@limiter.limit("5/minute")
async def accept_with_account(request: Request, token: str, body: AcceptWithAccountRequest):
    """
    Transactional: create account + accept invitation in one atomic operation.
    Auto-verifies email because the invitation token proves email ownership.
    Only works for the exact email carried by the invitation.
    """
    import uuid
    from utils.password_utils import hash_password
    from utils.jwt_utils import create_access_token
    from services.workspace_service import WorkspaceService
    from services.wallet_service import create_wallet

    # 1. Validate invitation token
    participant = db.participants.find_one({"invitation_token": token}, {"_id": 0})
    if not participant:
        raise HTTPException(status_code=404, detail="Invitation non trouvée ou expirée")

    email = participant.get('email', '')
    if not email:
        raise HTTPException(status_code=400, detail="Email manquant sur cette invitation")

    # 2. Check participant hasn't already responded
    if participant.get('status') in ['accepted', 'accepted_guaranteed', 'accepted_pending_guarantee', 'declined']:
        raise HTTPException(status_code=400, detail="Vous avez déjà répondu à cette invitation")

    # 3. Check no existing account for this email
    if db.users.find_one({"email": email}, {"_id": 0}):
        raise HTTPException(status_code=400, detail="Un compte existe déjà avec cet email. Utilisez la connexion.")

    # 4. Validate appointment
    appointment = db.appointments.find_one({"appointment_id": participant['appointment_id']}, {"_id": 0})
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    if appointment.get('status') in ['cancelled', 'completed']:
        raise HTTPException(status_code=400, detail="Ce rendez-vous n'est plus actif")
    start_dt = parse_iso_datetime(appointment.get('start_datetime', ''))
    if start_dt and datetime.now(timezone.utc) >= start_dt:
        raise HTTPException(status_code=400, detail="Ce rendez-vous a déjà commencé")

    # 5. Create account (auto-verified — invitation token proves email ownership)
    user_id = str(uuid.uuid4())
    now = now_utc_iso()
    user = {
        "user_id": user_id,
        "email": email,
        "password_hash": hash_password(body.password),
        "first_name": participant.get('first_name', ''),
        "last_name": participant.get('last_name', ''),
        "phone": None,
        "is_verified": True,
        "verified_via": "invitation_token",
        "invitation_token_used": token,
        "created_at": now,
        "updated_at": now,
    }
    try:
        db.users.insert_one(user)
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur lors de la création du compte")

    # 6. Create workspace + wallet
    WorkspaceService.create_default_workspace(user_id, user['first_name'], user['last_name'])
    create_wallet(user_id)

    # 7. Attach participant to user
    db.participants.update_one(
        {"invitation_token": token},
        {"$set": {"user_id": user_id, "updated_at": now}}
    )

    # 8. Generate JWT
    access_token = create_access_token({"sub": email, "user_id": user_id})

    # 9. Accept invitation (reuse existing logic)
    penalty_amount = appointment.get('penalty_amount', 0)
    accept_result = {}

    if penalty_amount and penalty_amount > 0:
        from services.stripe_guarantee_service import StripeGuaranteeService

        db.participants.update_one(
            {"invitation_token": token},
            {"$set": {"status": "accepted_pending_guarantee", "accept_initiated_at": now, "updated_at": now}}
        )

        frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/') or str(request.base_url).rstrip('/')
        participant_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()

        result = StripeGuaranteeService.create_guarantee_session(
            participant_id=participant['participant_id'],
            appointment_id=appointment['appointment_id'],
            participant_email=email,
            participant_name=participant_name or email.split('@')[0],
            appointment_title=appointment.get('title', 'Rendez-vous'),
            penalty_amount=float(penalty_amount),
            penalty_currency=appointment.get('penalty_currency', 'eur'),
            frontend_url=frontend_url,
            invitation_token=token
        )

        if not result.get('success'):
            db.participants.update_one(
                {"invitation_token": token},
                {"$set": {"status": "invited", "updated_at": now}}
            )
            raise HTTPException(status_code=500, detail="Erreur Stripe")

        db.participants.update_one(
            {"invitation_token": token},
            {"$set": {"guarantee_id": result['guarantee_id'], "stripe_session_id": result['session_id']}}
        )

        accept_result = {
            "requires_guarantee": True,
            "checkout_url": result['checkout_url'],
            "session_id": result['session_id'],
            "status": "accepted_pending_guarantee",
        }
    else:
        db.participants.update_one(
            {"invitation_token": token},
            {"$set": {"status": "accepted", "accepted_at": now, "updated_at": now}}
        )
        accept_result = {"requires_guarantee": False, "status": "accepted"}

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"user_id": user_id, "email": email, "first_name": user['first_name'], "last_name": user['last_name']},
        **accept_result,
    }


@router.post("/{token}/login-and-accept")
@limiter.limit("10/minute")
async def login_and_accept(request: Request, token: str, body: LoginAndAcceptRequest):
    """
    Transactional: login existing user + accept invitation.
    """
    from utils.password_utils import verify_password
    from utils.jwt_utils import create_access_token

    # 1. Validate invitation
    participant = db.participants.find_one({"invitation_token": token}, {"_id": 0})
    if not participant:
        raise HTTPException(status_code=404, detail="Invitation non trouvée")
    if participant.get('status') in ['accepted', 'accepted_guaranteed', 'accepted_pending_guarantee', 'declined']:
        raise HTTPException(status_code=400, detail="Vous avez déjà répondu à cette invitation")

    email = participant.get('email', '')
    user = db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Aucun compte trouvé avec cet email")
    if not verify_password(body.password, user.get('password_hash', '')):
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")

    user_id = user['user_id']
    now = now_utc_iso()

    # 2. Attach participant to user
    db.participants.update_one(
        {"invitation_token": token},
        {"$set": {"user_id": user_id, "updated_at": now}}
    )

    # 3. Generate JWT
    access_token = create_access_token({"sub": email, "user_id": user_id})

    # 4. Accept invitation
    appointment = db.appointments.find_one({"appointment_id": participant['appointment_id']}, {"_id": 0})
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    if appointment.get('status') in ['cancelled', 'completed']:
        raise HTTPException(status_code=400, detail="Rendez-vous plus actif")

    penalty_amount = appointment.get('penalty_amount', 0)
    accept_result = {}

    if penalty_amount and penalty_amount > 0:
        from services.stripe_guarantee_service import StripeGuaranteeService

        # ── Check if logged-in user has a saved card → skip Checkout ──
        user_pm_login = db.users.find_one(
            {"user_id": user_id, "default_payment_method_id": {"$exists": True, "$ne": None}},
            {"_id": 0, "default_payment_method_id": 1, "stripe_customer_id": 1}
        )
        if user_pm_login and user_pm_login.get("default_payment_method_id") and user_pm_login.get("stripe_customer_id"):
            reuse_login = StripeGuaranteeService.create_guarantee_with_saved_card(
                participant_id=participant["participant_id"],
                appointment_id=appointment["appointment_id"],
                invitation_token=token,
                penalty_amount=float(penalty_amount),
                penalty_currency=appointment.get("penalty_currency", "eur"),
                user_id=user_id,
                stripe_customer_id=user_pm_login["stripe_customer_id"],
                payment_method_id=user_pm_login["default_payment_method_id"],
            )
            if reuse_login.get("success"):
                accept_result = {
                    "requires_guarantee": False,
                    "reused_card": True,
                    "message": "Garantie confirmée avec votre carte enregistrée",
                    "status": "accepted_guaranteed",
                    "guarantee_id": reuse_login["guarantee_id"],
                }

        if not accept_result:
            db.participants.update_one(
                {"invitation_token": token},
                {"$set": {"status": "accepted_pending_guarantee", "accept_initiated_at": now, "updated_at": now}}
            )

            frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/') or str(request.base_url).rstrip('/')
            participant_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()

            result = StripeGuaranteeService.create_guarantee_session(
                participant_id=participant['participant_id'],
                appointment_id=appointment['appointment_id'],
                participant_email=email,
                participant_name=participant_name or email.split('@')[0],
                appointment_title=appointment.get('title', 'Rendez-vous'),
                penalty_amount=float(penalty_amount),
                penalty_currency=appointment.get('penalty_currency', 'eur'),
                frontend_url=frontend_url,
                invitation_token=token
            )

            if not result.get('success'):
                db.participants.update_one(
                    {"invitation_token": token},
                    {"$set": {"status": "invited", "updated_at": now}}
                )
                raise HTTPException(status_code=500, detail="Erreur Stripe")

            db.participants.update_one(
                {"invitation_token": token},
                {"$set": {"guarantee_id": result['guarantee_id'], "stripe_session_id": result['session_id']}}
            )
            accept_result = {
                "requires_guarantee": True,
                "checkout_url": result['checkout_url'],
                "status": "accepted_pending_guarantee",
            }
    else:
        db.participants.update_one(
            {"invitation_token": token},
            {"$set": {"status": "accepted", "accepted_at": now, "updated_at": now}}
        )
        accept_result = {"requires_guarantee": False, "status": "accepted"}

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"user_id": user_id, "email": email, "first_name": user['first_name'], "last_name": user['last_name']},
        **accept_result,
    }



@router.get("/{token}/guarantee-status")
@limiter.limit("30/minute")
async def check_guarantee_status(request: Request, token: str, session_id: str = None):
    """
    Check the status of a payment guarantee for an invitation.
    Used after Stripe redirect to verify completion.
    """
    participant = db.participants.find_one(
        {"invitation_token": token},
        {"_id": 0}
    )
    
    if not participant:
        raise HTTPException(status_code=404, detail="Invitation non trouvée")
    
    status = participant.get('status', 'invited')
    guarantee_id = participant.get('guarantee_id')
    
    # If session_id provided, check Stripe session
    if session_id:
        from services.stripe_guarantee_service import StripeGuaranteeService
        result = StripeGuaranteeService.get_guarantee_status(session_id)
        
        if result.get('success') and result.get('status') == 'completed':
            status = 'accepted_guaranteed'

            # Send confirmation email (idempotent — only sends once)
            fresh_participant = db.participants.find_one(
                {"invitation_token": token}, {"_id": 0}
            )
            if fresh_participant and not fresh_participant.get('confirmation_email_sent'):
                appointment = db.appointments.find_one(
                    {"appointment_id": fresh_participant.get('appointment_id')}, {"_id": 0}
                )
                if appointment:
                    await send_confirmation_email_once(fresh_participant, appointment)
    
    return {
        "status": status,
        "guarantee_id": guarantee_id,
        "is_guaranteed": status == "accepted_guaranteed",
        "participant_id": participant.get('participant_id')
    }


@router.post("/{token}/reconfirm-guarantee")
@limiter.limit("5/minute")
async def reconfirm_guarantee(request: Request, token: str):
    """
    Create a new Stripe checkout session to reconfirm a guarantee
    after a major modification flagged it for revalidation.
    """
    participant = db.participants.find_one({"invitation_token": token}, {"_id": 0})
    if not participant:
        raise HTTPException(status_code=404, detail="Invitation non trouvée")

    if participant.get('status') not in ('accepted_guaranteed', 'accepted_pending_guarantee'):
        raise HTTPException(status_code=400, detail="Pas de garantie active à reconfirmer")

    guarantee_id = participant.get('guarantee_id')
    if not guarantee_id:
        raise HTTPException(status_code=400, detail="Aucune garantie trouvée pour ce participant")

    guarantee = db.payment_guarantees.find_one({"guarantee_id": guarantee_id}, {"_id": 0})
    if not guarantee or not guarantee.get('requires_revalidation'):
        raise HTTPException(status_code=400, detail="Cette garantie ne nécessite pas de reconfirmation")

    appointment = db.appointments.find_one(
        {"appointment_id": participant['appointment_id']},
        {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    from services.stripe_guarantee_service import StripeGuaranteeService

    frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')
    if not frontend_url:
        frontend_url = str(request.base_url).rstrip('/')

    participant_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()
    if not participant_name:
        participant_name = participant.get('email', '').split('@')[0]

    result = StripeGuaranteeService.create_guarantee_session(
        participant_id=participant['participant_id'],
        appointment_id=appointment['appointment_id'],
        participant_email=participant.get('email', ''),
        participant_name=participant_name,
        appointment_title=appointment.get('title', 'Rendez-vous'),
        penalty_amount=float(appointment.get('penalty_amount', 0)),
        penalty_currency=appointment.get('penalty_currency', 'eur'),
        frontend_url=frontend_url,
        invitation_token=token
    )

    if not result.get('success'):
        raise HTTPException(status_code=500, detail=f"Erreur Stripe: {result.get('error')}")

    # Clear old revalidation flag and link to new guarantee
    now = now_utc_iso()
    old_guarantee_id = guarantee_id
    new_guarantee_id = result['guarantee_id']

    # Mark old guarantee as superseded
    db.payment_guarantees.update_one(
        {"guarantee_id": old_guarantee_id},
        {"$set": {
            "status": "superseded",
            "superseded_by": new_guarantee_id,
            "superseded_at": now,
            "requires_revalidation": False
        }}
    )

    # Link new guarantee to participant
    db.participants.update_one(
        {"invitation_token": token},
        {"$set": {
            "guarantee_id": new_guarantee_id,
            "stripe_session_id": result['session_id'],
            "status": "accepted_pending_guarantee",
            "updated_at": now
        }}
    )

    return {
        "success": True,
        "checkout_url": result['checkout_url'],
        "session_id": result['session_id'],
        "new_guarantee_id": new_guarantee_id
    }


@router.post("/{token}/cancel")
@limiter.limit("5/minute")
async def cancel_participation(request: Request, token: str):
    """
    Public endpoint to cancel participation after acceptance.
    Only allowed if cancellation deadline has not passed.
    No authentication required - uses token for security.
    """
    # Find participant by token
    participant = db.participants.find_one(
        {"invitation_token": token},
        {"_id": 0}
    )
    
    if not participant:
        raise HTTPException(status_code=404, detail="Invitation non trouvée ou expirée")
    
    # Check if participant has accepted (with or without guarantee)
    current_status = participant.get('status', 'invited')
    if current_status not in ('accepted', 'accepted_guaranteed'):
        raise HTTPException(
            status_code=400, 
            detail="Seule une invitation acceptée peut être annulée"
        )
    
    # Get appointment to check cancellation deadline
    appointment = db.appointments.find_one(
        {"appointment_id": participant['appointment_id']},
        {"_id": 0}
    )
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous associé introuvable")
    
    # Check if appointment is still active
    if appointment.get('status') in ['cancelled', 'completed']:
        raise HTTPException(status_code=400, detail="Ce rendez-vous n'est plus actif")
    
    # Calculate and check cancellation deadline
    start_dt = parse_iso_datetime(appointment.get('start_datetime', ''))
    if not start_dt:
        raise HTTPException(status_code=400, detail="Date du rendez-vous invalide")
    
    cancellation_deadline_hours = appointment.get('cancellation_deadline_hours', 24)
    cancellation_deadline_dt = start_dt - timedelta(hours=cancellation_deadline_hours)
    
    now = datetime.now(timezone.utc)
    
    if now >= cancellation_deadline_dt:
        raise HTTPException(
            status_code=400, 
            detail="Le délai d'annulation est dépassé. Vous ne pouvez plus annuler en ligne."
        )
    
    # Check if appointment hasn't started yet
    if now >= start_dt:
        raise HTTPException(status_code=400, detail="Ce rendez-vous a déjà commencé")
    
    now_str = now_utc_iso()
    
    update_data = {
        "status": "cancelled_by_participant",
        "cancelled_at": now_str,
        "updated_at": now_str
    }
    
    # Update participant status
    db.participants.update_one(
        {"invitation_token": token},
        {"$set": update_data}
    )
    
    # Release guarantee if participant had one
    if current_status == 'accepted_guaranteed' and participant.get('guarantee_id'):
        try:
            from services.stripe_guarantee_service import StripeGuaranteeService
            StripeGuaranteeService.release_guarantee(
                participant['guarantee_id'],
                "cancelled_by_participant"
            )
        except Exception as e:
            print(f"[CANCEL] Failed to release guarantee: {e}")
    
    # Get updated participant
    updated_participant = db.participants.find_one(
        {"invitation_token": token},
        {"_id": 0}
    )
    
    # Send notification email to organizer
    try:
        from services.email_service import EmailService
        
        # Get organizer details
        organizer = db.users.find_one(
            {"user_id": appointment['organizer_id']},
            {"_id": 0, "email": 1, "first_name": 1, "last_name": 1}
        )
        
        if organizer:
            organizer_name = f"{organizer.get('first_name', '')} {organizer.get('last_name', '')}".strip() or "Organisateur"
            participant_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip() or participant.get('email', 'Participant')
            
            # Build appointment link
            frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')
            appointment_link = f"{frontend_url}/dashboard" if frontend_url else None
            
            await EmailService.send_participant_cancellation_notification(
                organizer_email=organizer['email'],
                organizer_name=organizer_name,
                participant_name=participant_name,
                participant_email=participant.get('email', ''),
                appointment_title=appointment.get('title', 'Rendez-vous'),
                appointment_datetime=appointment.get('start_datetime', ''),
                location=appointment.get('location') or appointment.get('meeting_provider'),
                appointment_link=appointment_link,
                appointment_timezone=appointment.get('appointment_timezone', 'Europe/Paris')
            )
    except Exception as e:
        import logging
        logging.error(f"Failed to send cancellation notification: {e}")
    
    return {
        "success": True,
        "message": "Votre participation a bien été annulée.",
        "status": "cancelled_by_participant",
        "participant": {
            "participant_id": updated_participant['participant_id'],
            "first_name": updated_participant.get('first_name', ''),
            "last_name": updated_participant.get('last_name', ''),
            "status": updated_participant['status'],
            "accepted_at": updated_participant.get('accepted_at'),
            "cancelled_at": updated_participant.get('cancelled_at')
        }
    }


@router.post("/{token}/resend")
async def resend_invitation(token: str, request: Request):
    """
    Resend invitation email (requires organizer auth).
    """
    from middleware.auth_middleware import get_current_user
    from services.email_service import EmailService
    
    user = await get_current_user(request)
    
    # Find participant
    participant = db.participants.find_one(
        {"invitation_token": token},
        {"_id": 0}
    )
    
    if not participant:
        raise HTTPException(status_code=404, detail="Participant introuvable")
    
    # Get appointment and verify organizer
    appointment = db.appointments.find_one(
        {"appointment_id": participant['appointment_id']},
        {"_id": 0}
    )
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    
    if appointment['organizer_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="Seul l'organisateur peut renvoyer une invitation")
    
    # Build invitation link
    frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')
    invitation_link = f"{frontend_url}/invitation/{token}"
    
    # Get organizer name
    organizer_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    
    # Build participant name
    participant_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()
    if not participant_name:
        participant_name = participant.get('email', '').split('@')[0]
    
    # Send email
    has_account = db.users.count_documents({"email": participant['email'], "is_verified": True}) > 0
    result = await EmailService.send_invitation_email(
        to_email=participant['email'],
        to_name=participant_name,
        organizer_name=organizer_name,
        appointment_title=appointment['title'],
        appointment_datetime=appointment.get('start_datetime', ''),
        invitation_link=invitation_link,
        appointment_timezone=appointment.get('appointment_timezone', 'Europe/Paris'),
        has_existing_account=has_account,
    )

    if result.get('success'):
        # Update last sent timestamp
        db.participants.update_one(
            {"invitation_token": token},
            {"$set": {"last_invitation_sent_at": now_utc().isoformat()}}
        )
        return {"success": True, "message": "Invitation renvoyée avec succès"}
    else:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'envoi: {result.get('error')}")
