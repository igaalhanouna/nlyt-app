from fastapi import APIRouter, HTTPException, Request
import os
import sys
import json
import logging
import stripe
sys.path.append('/app/backend')
from services.stripe_guarantee_service import StripeGuaranteeService
from services.connect_service import handle_account_updated, handle_account_deauthorized
from services.payout_service import handle_transfer_paid, handle_transfer_failed
from datetime import datetime, timezone

from database import db

logger = logging.getLogger("webhooks")

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
                logger.info(f"DUPLICATE event_id={event_id} type={event_type} — skipping")
                return {"status": "duplicate", "event_id": event_id}
        
        logger.info(f"RECEIVED event_id={event_id} type={event_type}")
        
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
            logger.info(f"CHECKOUT event_id={event_id} mode={session_mode} meta_type={metadata.get('type', 'N/A')} appointment_id={metadata.get('appointment_id', 'N/A')} guarantee_id={metadata.get('guarantee_id', 'N/A')}")
            
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
                        g_id = metadata.get("guarantee_id")
                        logger.warning(f"SKIP_GUARANTEE event_id={event_id} appointment_id={apt_id} status={apt['status']} guarantee_id={g_id} — appointment inactive, releasing guarantee")
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
                                    logger.info(f"ACTIVATION event_id={event_id} appointment_id={appointment['appointment_id']} organizer_id={appointment['organizer_id']} success={activation.get('success')}")
                                except Exception as act_err:
                                    logger.error(f"ACTIVATION_ERROR event_id={event_id} appointment_id={appointment['appointment_id']} error={act_err}")
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
            logger.info(f"PAYMENT_INTENT event_id={event_id} guarantee_id={guarantee_id or 'N/A'} amount={payment_intent.get('amount', '?')}")
            
            if guarantee_id:
                db.payment_guarantees.update_one(
                    {"guarantee_id": guarantee_id},
                    {"$set": {
                        "capture_confirmed_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                logger.info(f"CAPTURE_CONFIRMED event_id={event_id} guarantee_id={guarantee_id}")
        
        # Handle Stripe Connect account updates
        elif event_type == "account.updated":
            account_id = event_data.get("id", "unknown")
            logger.info(f"CONNECT_UPDATE event_id={event_id} account_id={account_id}")
            result = handle_account_updated(event_data)
            logger.info(f"CONNECT_UPDATE_RESULT event_id={event_id} account_id={account_id} result={result}")
            return {"status": "success", "event_type": event_type, "result": result}
        
        # Handle Stripe Connect deauthorization
        elif event_type == "account.application.deauthorized":
            account_id = event_data.get("id") or event_data.get("account")
            logger.warning(f"CONNECT_DEAUTH event_id={event_id} account_id={account_id}")
            if account_id:
                result = handle_account_deauthorized(account_id)
                logger.info(f"CONNECT_DEAUTH_RESULT event_id={event_id} account_id={account_id} result={result}")
                return {"status": "success", "event_type": event_type, "result": result}
        
        # Handle Stripe Transfer paid (payout completed)
        elif event_type == "transfer.paid":
            transfer_id = event_data.get("id", "unknown")
            payout_meta = event_data.get("metadata", {})
            logger.info(f"TRANSFER_PAID event_id={event_id} transfer_id={transfer_id} payout_id={payout_meta.get('payout_id', 'N/A')} user_id={payout_meta.get('user_id', 'N/A')} amount={event_data.get('amount', '?')}")
            result = handle_transfer_paid(event_data)
            logger.info(f"TRANSFER_PAID_RESULT event_id={event_id} transfer_id={transfer_id} result={result}")
            return {"status": "success", "event_type": event_type, "result": result}
        
        # Handle Stripe Transfer failed/reversed (payout failed)
        elif event_type in ("transfer.failed", "transfer.reversed"):
            transfer_id = event_data.get("id", "unknown")
            payout_meta = event_data.get("metadata", {})
            logger.warning(f"TRANSFER_FAIL event_id={event_id} type={event_type} transfer_id={transfer_id} payout_id={payout_meta.get('payout_id', 'N/A')} user_id={payout_meta.get('user_id', 'N/A')} failure={event_data.get('failure_message', 'N/A')}")
            result = handle_transfer_failed(event_data)
            logger.info(f"TRANSFER_FAIL_RESULT event_id={event_id} transfer_id={transfer_id} result={result}")
            return {"status": "success", "event_type": event_type, "result": result}
        
        logger.info(f"UNHANDLED event_id={event_id} type={event_type} — no specific handler")
        return {"status": "success", "event_type": event_type}
    
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"SIGNATURE_INVALID error={e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        _eid = locals().get('event_id', 'N/A')
        logger.error(f"WEBHOOK_ERROR event_id={_eid} error={e}")
        raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)}")