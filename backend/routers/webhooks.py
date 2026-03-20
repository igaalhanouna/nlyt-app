from fastapi import APIRouter, HTTPException, Request
from pymongo import MongoClient
import os
import sys
import json
import stripe
sys.path.append('/app/backend')
from services.payment_service import PaymentService
from services.stripe_guarantee_service import StripeGuaranteeService
from datetime import datetime, timezone

router = APIRouter()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

stripe.api_key = STRIPE_API_KEY

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

@router.post("/stripe")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.
    
    Key events:
    - checkout.session.completed (mode=setup): Payment method collected for guarantee
    - payment_intent.succeeded: Penalty captured (no-show)
    """
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")
    
    try:
        # Verify webhook signature if secret is configured
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(
                body, signature, STRIPE_WEBHOOK_SECRET
            )
        else:
            # Parse event without verification (dev mode)
            event = json.loads(body)
        
        event_type = event.get("type", event.get("event_type", "unknown"))
        event_id = event.get("id", "unknown")
        event_data = event.get("data", {}).get("object", event.get("data", {}))
        
        print(f"[WEBHOOK] Received event: {event_type}")
        
        # Log all events
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
            
            # Check if this is a guarantee setup session
            if session_mode == "setup" and metadata.get("type") == "nlyt_guarantee":
                result = StripeGuaranteeService.handle_checkout_completed(session)
                
                if result.get("success"):
                    # Send confirmation email with calendar link
                    try:
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
                                from services.email_service import EmailService
                                
                                organizer = db.users.find_one(
                                    {"user_id": appointment.get('organizer_id')},
                                    {"_id": 0}
                                )
                                organizer_name = f"{organizer.get('first_name', '')} {organizer.get('last_name', '')}".strip() if organizer else "L'organisateur"
                                
                                participant_name = f"{participant.get('first_name', '')} {participant.get('last_name', '')}".strip()
                                if not participant_name:
                                    participant_name = participant.get('email', '').split('@')[0]
                                
                                frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')
                                ics_link = f"{frontend_url}/api/calendar/export/ics/{appointment['appointment_id']}"
                                invitation_link = f"{frontend_url}/invitation/{participant.get('invitation_token')}"
                                
                                await EmailService.send_acceptance_confirmation_email(
                                    to_email=participant.get('email', ''),
                                    to_name=participant_name,
                                    organizer_name=organizer_name,
                                    appointment_title=appointment.get('title', ''),
                                    appointment_datetime=appointment.get('start_datetime', ''),
                                    location=appointment.get('location') or appointment.get('meeting_provider'),
                                    penalty_amount=appointment.get('penalty_amount'),
                                    penalty_currency=appointment.get('penalty_currency', 'EUR'),
                                    cancellation_deadline_hours=appointment.get('cancellation_deadline_hours'),
                                    ics_link=ics_link,
                                    invitation_link=invitation_link
                                )
                    except Exception as email_error:
                        print(f"[WEBHOOK] Email error: {email_error}")
                
                return {"status": "success", "event_type": event_type, "result": result}
            
            # Handle regular payment checkout (legacy)
            elif session.get("payment_status") == "paid":
                guarantee_id = metadata.get('guarantee_id')
                
                if guarantee_id:
                    PaymentService.update_guarantee_status(
                        guarantee_id,
                        "setup_complete",
                        {"stripe_session_id": session.get("id")}
                    )
        
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
        
        return {"status": "success", "event_type": event_type}
    
    except stripe.error.SignatureVerificationError as e:
        print(f"[WEBHOOK] Signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        print(f"[WEBHOOK] Error: {e}")
        raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)}")