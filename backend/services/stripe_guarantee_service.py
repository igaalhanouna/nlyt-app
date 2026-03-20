"""
Stripe Guarantee Service for NLYT
Uses Stripe Checkout Session in "setup" mode to collect payment methods
without charging immediately. The payment method can be used later
to capture funds if needed (no-show, late cancellation).
"""
import os
import stripe
import uuid
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')

# Initialize Stripe
stripe.api_key = STRIPE_API_KEY

client = MongoClient(MONGO_URL)
db = client[DB_NAME]


class StripeGuaranteeService:
    """
    Service for handling Stripe payment guarantees using SetupIntent via Checkout Session.
    
    Flow:
    1. Participant accepts invitation
    2. Create Stripe Checkout Session in "setup" mode
    3. Participant completes Stripe form (provides payment method)
    4. Webhook confirms completion
    5. Participant status becomes "accepted_guaranteed"
    6. Payment method stored for future use (no-show capture)
    """
    
    @staticmethod
    def create_guarantee_session(
        participant_id: str,
        appointment_id: str,
        participant_email: str,
        participant_name: str,
        appointment_title: str,
        penalty_amount: float,
        penalty_currency: str,
        frontend_url: str,
        invitation_token: str
    ) -> dict:
        """
        Create a Stripe Checkout Session in "setup" mode to collect payment method.
        No charge is made at this point.
        
        Returns:
            dict with checkout_url and session_id
        """
        # Generate guarantee record ID
        guarantee_id = str(uuid.uuid4())
        
        try:
            # Check if Stripe is properly configured
            if not STRIPE_API_KEY or STRIPE_API_KEY == 'sk_test_emergent':
                # Development mode - simulate success flow
                print("[STRIPE_GUARANTEE] Running in development mode - simulating Stripe")
                
                # Store guarantee record with simulated data
                guarantee_record = {
                    "guarantee_id": guarantee_id,
                    "participant_id": participant_id,
                    "appointment_id": appointment_id,
                    "invitation_token": invitation_token,
                    "stripe_customer_id": f"cus_dev_{participant_id[:8]}",
                    "stripe_session_id": f"cs_dev_{guarantee_id[:8]}",
                    "stripe_setup_intent_id": None,
                    "stripe_payment_method_id": None,
                    "penalty_amount": penalty_amount,
                    "penalty_currency": penalty_currency,
                    "status": "dev_pending",  # Special status for dev mode
                    "dev_mode": True,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
                db.payment_guarantees.insert_one(guarantee_record)
                
                # In dev mode, return a URL that will auto-confirm
                dev_success_url = f"{frontend_url}/invitation/{invitation_token}?guarantee_status=success&session_id=cs_dev_{guarantee_id[:8]}&dev_mode=true"
                
                return {
                    "success": True,
                    "checkout_url": dev_success_url,
                    "session_id": f"cs_dev_{guarantee_id[:8]}",
                    "guarantee_id": guarantee_id,
                    "dev_mode": True
                }
            
            # Production mode - use real Stripe
            # Create or retrieve Stripe customer
            customer = StripeGuaranteeService._get_or_create_customer(
                participant_email, participant_name
            )
            
            # Build success/cancel URLs
            success_url = f"{frontend_url}/invitation/{invitation_token}?guarantee_status=success&session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{frontend_url}/invitation/{invitation_token}?guarantee_status=cancelled"
            
            # Create Checkout Session in setup mode
            # This collects payment method without charging
            session = stripe.checkout.Session.create(
                mode="setup",  # KEY: setup mode = no charge
                customer=customer.id,
                payment_method_types=["card"],
                success_url=success_url,
                cancel_url=cancel_url,
                locale="fr",  # French language
                metadata={
                    "guarantee_id": guarantee_id,
                    "participant_id": participant_id,
                    "appointment_id": appointment_id,
                    "invitation_token": invitation_token,
                    "type": "nlyt_guarantee"
                },
                # Custom text for setup mode
                custom_text={
                    "submit": {
                        "message": f"En confirmant, vous autorisez NLYT à prélever {penalty_amount:.2f} {penalty_currency.upper()} en cas d'absence ou de retard excessif au rendez-vous \"{appointment_title}\"."
                    }
                }
            )
            
            # Store guarantee record in database
            guarantee_record = {
                "guarantee_id": guarantee_id,
                "participant_id": participant_id,
                "appointment_id": appointment_id,
                "invitation_token": invitation_token,
                "stripe_customer_id": customer.id,
                "stripe_session_id": session.id,
                "stripe_setup_intent_id": None,  # Will be set by webhook
                "stripe_payment_method_id": None,  # Will be set by webhook
                "penalty_amount": penalty_amount,
                "penalty_currency": penalty_currency,
                "status": "pending",  # pending -> completed -> captured/released
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            db.payment_guarantees.insert_one(guarantee_record)
            
            return {
                "success": True,
                "checkout_url": session.url,
                "session_id": session.id,
                "guarantee_id": guarantee_id
            }
            
        except stripe.error.StripeError as e:
            print(f"[STRIPE_ERROR] {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "stripe_error"
            }
        except Exception as e:
            print(f"[GUARANTEE_ERROR] {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "internal_error"
            }
    
    @staticmethod
    def _get_or_create_customer(email: str, name: str) -> stripe.Customer:
        """Get existing Stripe customer or create new one"""
        # Check if customer exists in our DB
        existing = db.stripe_customers.find_one({"email": email}, {"_id": 0})
        
        if existing and existing.get("stripe_customer_id"):
            try:
                # Verify customer still exists in Stripe
                customer = stripe.Customer.retrieve(existing["stripe_customer_id"])
                if not customer.get("deleted"):
                    return customer
            except stripe.error.InvalidRequestError:
                pass  # Customer doesn't exist, create new one
        
        # Create new customer
        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata={"source": "nlyt"}
        )
        
        # Store in our DB
        db.stripe_customers.update_one(
            {"email": email},
            {"$set": {
                "email": email,
                "name": name,
                "stripe_customer_id": customer.id,
                "created_at": datetime.now(timezone.utc).isoformat()
            }},
            upsert=True
        )
        
        return customer
    
    @staticmethod
    def handle_checkout_completed(session: dict) -> dict:
        """
        Handle checkout.session.completed webhook event.
        Updates guarantee status and participant status.
        """
        session_id = session.get("id")
        setup_intent_id = session.get("setup_intent")
        customer_id = session.get("customer")
        metadata = session.get("metadata", {})
        
        guarantee_id = metadata.get("guarantee_id")
        participant_id = metadata.get("participant_id")
        invitation_token = metadata.get("invitation_token")
        
        if not guarantee_id:
            return {"success": False, "error": "No guarantee_id in metadata"}
        
        try:
            # Get the SetupIntent to retrieve the payment method
            setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
            payment_method_id = setup_intent.payment_method
            
            # Update guarantee record
            db.payment_guarantees.update_one(
                {"guarantee_id": guarantee_id},
                {"$set": {
                    "status": "completed",
                    "stripe_setup_intent_id": setup_intent_id,
                    "stripe_payment_method_id": payment_method_id,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            # Update participant status to accepted_guaranteed
            db.participants.update_one(
                {"participant_id": participant_id},
                {"$set": {
                    "status": "accepted_guaranteed",
                    "guarantee_id": guarantee_id,
                    "stripe_customer_id": customer_id,
                    "stripe_payment_method_id": payment_method_id,
                    "guaranteed_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            # Log the event
            db.stripe_events.insert_one({
                "event_id": str(uuid.uuid4()),
                "event_type": "checkout.session.completed",
                "session_id": session_id,
                "guarantee_id": guarantee_id,
                "participant_id": participant_id,
                "payment_method_id": payment_method_id,
                "processed_at": datetime.now(timezone.utc).isoformat()
            })
            
            return {
                "success": True,
                "guarantee_id": guarantee_id,
                "participant_id": participant_id,
                "status": "accepted_guaranteed"
            }
            
        except Exception as e:
            print(f"[WEBHOOK_ERROR] {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def get_guarantee_status(session_id: str) -> dict:
        """Check the status of a guarantee by session_id"""
        guarantee = db.payment_guarantees.find_one(
            {"stripe_session_id": session_id},
            {"_id": 0}
        )
        
        if not guarantee:
            return {"success": False, "error": "Guarantee not found"}
        
        # Handle dev mode auto-confirmation
        if guarantee.get("dev_mode") and guarantee.get("status") == "dev_pending":
            # Auto-confirm in dev mode
            db.payment_guarantees.update_one(
                {"stripe_session_id": session_id},
                {"$set": {
                    "status": "completed",
                    "stripe_payment_method_id": f"pm_dev_{guarantee['guarantee_id'][:8]}",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            # Update participant status
            db.participants.update_one(
                {"participant_id": guarantee['participant_id']},
                {"$set": {
                    "status": "accepted_guaranteed",
                    "guarantee_id": guarantee['guarantee_id'],
                    "guaranteed_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            return {
                "success": True,
                "guarantee_id": guarantee.get("guarantee_id"),
                "status": "completed",
                "participant_id": guarantee.get("participant_id"),
                "dev_mode": True
            }
        
        return {
            "success": True,
            "guarantee_id": guarantee.get("guarantee_id"),
            "status": guarantee.get("status"),
            "participant_id": guarantee.get("participant_id")
        }
    
    @staticmethod
    def release_guarantee(guarantee_id: str, reason: str) -> dict:
        """
        Release a guarantee (e.g., when organizer cancels).
        No charge is made.
        """
        guarantee = db.payment_guarantees.find_one(
            {"guarantee_id": guarantee_id},
            {"_id": 0}
        )
        
        if not guarantee:
            return {"success": False, "error": "Guarantee not found"}
        
        db.payment_guarantees.update_one(
            {"guarantee_id": guarantee_id},
            {"$set": {
                "status": "released",
                "release_reason": reason,
                "released_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        return {"success": True, "message": "Guarantee released"}
    
    @staticmethod
    def capture_guarantee(guarantee_id: str, reason: str) -> dict:
        """
        Capture a guarantee (charge the participant).
        Used for no-show or late cancellation.
        """
        guarantee = db.payment_guarantees.find_one(
            {"guarantee_id": guarantee_id},
            {"_id": 0}
        )
        
        if not guarantee:
            return {"success": False, "error": "Guarantee not found"}
        
        if guarantee.get("status") != "completed":
            return {"success": False, "error": "Guarantee not in completed state"}
        
        try:
            # Create PaymentIntent using the stored payment method
            payment_intent = stripe.PaymentIntent.create(
                amount=int(guarantee["penalty_amount"] * 100),  # Convert to cents
                currency=guarantee["penalty_currency"],
                customer=guarantee["stripe_customer_id"],
                payment_method=guarantee["stripe_payment_method_id"],
                off_session=True,
                confirm=True,
                metadata={
                    "guarantee_id": guarantee_id,
                    "capture_reason": reason
                }
            )
            
            # Update guarantee status
            db.payment_guarantees.update_one(
                {"guarantee_id": guarantee_id},
                {"$set": {
                    "status": "captured",
                    "capture_reason": reason,
                    "stripe_payment_intent_id": payment_intent.id,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            return {
                "success": True,
                "message": "Guarantee captured",
                "payment_intent_id": payment_intent.id
            }
            
        except stripe.error.CardError as e:
            return {"success": False, "error": f"Card error: {e.user_message}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
