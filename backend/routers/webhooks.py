from fastapi import APIRouter, HTTPException, Request
import os
import sys
import json
import stripe
sys.path.append('/app/backend')
from services.stripe_guarantee_service import StripeGuaranteeService
from services.connect_service import handle_account_updated, handle_account_deauthorized
from datetime import datetime, timezone

from database import db
router = APIRouter()

STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

stripe.api_key = STRIPE_API_KEY


@router.post("/stripe")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.
    """
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")
    
    try:
        # CRITICAL: Always verify webhook signature in production
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(
                body, signature, STRIPE_WEBHOOK_SECRET
            )
        elif STRIPE_API_KEY and STRIPE_API_KEY != 'sk_test_emergent':
            # Real Stripe key but no webhook secret = misconfiguration
            raise HTTPException(status_code=500, detail="STRIPE_WEBHOOK_SECRET is required in production")
        else:
            # Dev mode only
            event = json.loads(body)
        
        event_type = event.get("type", event.get("event_type", "unknown"))
        event_id = event.get("id", "unknown")
        event_data = event.get("data", {}).get("object", event.get("data", {}))
        
        # Idempotence guard: reject duplicate events
        if event_id != "unknown":
            existing = db.stripe_events.find_one({"event_id": event_id})
            if existing:
                print(f"[WEBHOOK] Duplicate event {event_id} — skipping")
                return {"status": "duplicate", "event_id": event_id}
        
        print(f"[WEBHOOK] Received event: {event_type}")
        
        # Log event (with unique event_id as guard)
        db.stripe_events.insert_one({
            "event_id": event_id,
            "event_type": event_type,
            "data": event_data,
            "received_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Handle checkout.session.completed
        if event_type == "checkout.session.completed":
            session = event_data
            session_mode = session.get("mode")
            metadata = session.get("metadata", {})
            
            # ── Default payment method setup (Settings page) ──
            if session_mode == "setup" and metadata.get("type") == "nlyt_default_payment_method":
                result = StripeGuaranteeService.handle_default_payment_setup_completed(session)
                return {"status": "success", "event_type": event_type, "result": result}
            
            # ── Guarantee setup session (participant or organizer) ──
            if session_mode == "setup" and metadata.get("type") == "nlyt_guarantee":
                # Verify appointment is still active before confirming guarantee
                apt_id = metadata.get("appointment_id")
                if apt_id:
                    apt = db.appointments.find_one({"appointment_id": apt_id}, {"_id": 0, "status": 1})
                    if apt and apt.get("status") in ("cancelled", "deleted"):
                        print(f"[WEBHOOK] Appointment {apt_id} is {apt['status']} — releasing guarantee")
                        g_id = metadata.get("guarantee_id")
                        if g_id:
                            StripeGuaranteeService.release_guarantee(g_id, f"appointment_{apt['status']}")
                        return {"status": "skipped", "reason": f"appointment_{apt['status']}"}
                
                result = StripeGuaranteeService.handle_checkout_completed(session)
                
                if result.get("success"):
                    participant_id = result.get("participant_id")
                    participant = db.participants.find_one(
                        {"participant_id": participant_id},
                        {"_id": 0}
                    )
                    
                    if participant:
                        appointment = db.appointments.find_one(
                            {"appointment_id": participant.get("appointment_id")},
                            {"_id": 0}
                        )
                        
                        if appointment:
                            # ── ORGANIZER ACTIVATION ──
                            # If this is the organizer's guarantee and the RDV is still pending,
                            # activate it: send invitations, sync calendar, create meeting.
                            if (participant.get("is_organizer")
                                    and appointment.get("status") == "pending_organizer_guarantee"):
                                try:
                                    from services.appointment_lifecycle import activate_appointment
                                    activation = await activate_appointment(
                                        appointment["appointment_id"],
                                        appointment["organizer_id"]
                                    )
                                    print(f"[WEBHOOK] Appointment {appointment['appointment_id']} activated: {activation.get('success')}")
                                except Exception as act_err:
                                    print(f"[WEBHOOK] Activation error: {act_err}")
                            else:
                                # Regular participant — send confirmation email (idempotent)
                                from routers.invitations import send_confirmation_email_once
                                await send_confirmation_email_once(participant, appointment)
                
                return {"status": "success", "event_type": event_type, "result": result}
        
        # Handle payment_intent.succeeded (penalty capture)
        elif event_type == "payment_intent.succeeded":
            payment_intent = event_data
            metadata = payment_intent.get("metadata", {})
            guarantee_id = metadata.get("guarantee_id")
            
            if guarantee_id:
                db.payment_guarantees.update_one(
                    {"guarantee_id": guarantee_id},
                    {"$set": {
                        "capture_confirmed_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
        
        # Handle Stripe Connect account updates
        elif event_type == "account.updated":
            result = handle_account_updated(event_data)
            return {"status": "success", "event_type": event_type, "result": result}
        
        # Handle Stripe Connect deauthorization
        elif event_type == "account.application.deauthorized":
            account_id = event_data.get("id") or event_data.get("account")
            if account_id:
                result = handle_account_deauthorized(account_id)
                return {"status": "success", "event_type": event_type, "result": result}
        
        return {"status": "success", "event_type": event_type}
    
    except stripe.error.SignatureVerificationError as e:
        print(f"[WEBHOOK] Signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        print(f"[WEBHOOK] Error: {e}")
        raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)}")