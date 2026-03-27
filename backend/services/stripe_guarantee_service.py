"""
Stripe Guarantee Service for NLYT
Uses Stripe Checkout Session in "setup" mode to collect payment methods
without charging immediately. The payment method can be used later
to capture funds if needed (no-show, late cancellation).
"""
import os
import stripe
import uuid
from dotenv import load_dotenv
from datetime import datetime, timezone
from database import db

load_dotenv()

STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')

# Initialize Stripe
stripe.api_key = STRIPE_API_KEY



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
    def create_guarantee_with_saved_card(
        participant_id: str,
        appointment_id: str,
        invitation_token: str,
        penalty_amount: float,
        penalty_currency: str,
        user_id: str,
        stripe_customer_id: str,
        payment_method_id: str,
    ) -> dict:
        """
        Create a guarantee using a saved payment method.
        Verifies the card is still valid via a Stripe SetupIntent (off-session).
        No Checkout redirect — but real Stripe verification.
        """
        guarantee_id = str(uuid.uuid4())

        # ── STRIPE VERIFICATION: confirm the card is still valid ──
        setup_intent_id = None
        if STRIPE_API_KEY and STRIPE_API_KEY != 'sk_test_emergent' and not payment_method_id.startswith("pm_dev_"):
            try:
                si = stripe.SetupIntent.create(
                    customer=stripe_customer_id,
                    payment_method=payment_method_id,
                    confirm=True,
                    usage="off_session",
                    metadata={
                        "guarantee_id": guarantee_id,
                        "participant_id": participant_id,
                        "type": "reuse_verification",
                    },
                )
                setup_intent_id = si.id

                if si.status == "requires_action":
                    # SCA required — cannot silently reuse, fall back to Checkout
                    print(f"[GUARANTEE] SCA required for {payment_method_id[:15]}... — falling back to Checkout")
                    # Cancel the SetupIntent
                    stripe.SetupIntent.cancel(si.id)
                    return {"success": False, "reason": "sca_required"}

                if si.status != "succeeded":
                    print(f"[GUARANTEE] SetupIntent status={si.status} for {payment_method_id[:15]}... — falling back")
                    return {"success": False, "reason": f"setup_failed_{si.status}"}

                print(f"[GUARANTEE] Card verified via SetupIntent {si.id} for {payment_method_id[:15]}...")

            except stripe.error.CardError as e:
                print(f"[GUARANTEE] Card error during verification: {e.user_message}")
                return {"success": False, "reason": "card_error", "message": e.user_message}
            except Exception as e:
                print(f"[GUARANTEE] Verification error: {e}")
                return {"success": False, "reason": "verification_error"}
        else:
            # Dev mode — skip Stripe verification
            print(f"[GUARANTEE_DEV] Skipping Stripe verification for {payment_method_id}")

        # ── Card verified (or dev mode) — create guarantee record ──
        guarantee_record = {
            "guarantee_id": guarantee_id,
            "participant_id": participant_id,
            "appointment_id": appointment_id,
            "invitation_token": invitation_token,
            "stripe_customer_id": stripe_customer_id,
            "stripe_session_id": f"reuse_{guarantee_id[:8]}",
            "stripe_setup_intent_id": setup_intent_id,
            "stripe_payment_method_id": payment_method_id,
            "penalty_amount": penalty_amount,
            "penalty_currency": penalty_currency,
            "status": "completed",
            "dev_mode": not STRIPE_API_KEY or STRIPE_API_KEY == 'sk_test_emergent',
            "reused_card": True,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        db.payment_guarantees.insert_one(guarantee_record)
        guarantee_record.pop("_id", None)

        # Update participant
        db.participants.update_one(
            {"participant_id": participant_id},
            {"$set": {
                "status": "accepted_guaranteed",
                "guarantee_id": guarantee_id,
                "stripe_customer_id": stripe_customer_id,
                "stripe_payment_method_id": payment_method_id,
                "guaranteed_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )

        print(f"[GUARANTEE] Reused saved card {payment_method_id[:15]}... for participant {participant_id}")
        return {
            "success": True,
            "guarantee_id": guarantee_id,
            "reused_card": True,
            "setup_intent_id": setup_intent_id,
        }

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
            
            # ── AUTO-SAVE card as default payment method on user profile ──
            try:
                participant = db.participants.find_one(
                    {"participant_id": participant_id},
                    {"_id": 0, "user_id": 1, "email": 1}
                )
                user_id = participant.get("user_id") if participant else None
                p_email = participant.get("email") if participant else None

                # If participant has no user_id, look up by email
                if not user_id and p_email:
                    user_doc = db.users.find_one({"email": p_email}, {"_id": 0, "user_id": 1})
                    if user_doc:
                        user_id = user_doc["user_id"]
                        # Also link participant to user
                        db.participants.update_one(
                            {"participant_id": participant_id},
                            {"$set": {"user_id": user_id}}
                        )

                if user_id and payment_method_id:
                    already_has_pm = db.users.find_one(
                        {"user_id": user_id, "default_payment_method_id": {"$exists": True, "$ne": None}},
                        {"_id": 0, "user_id": 1}
                    )
                    if not already_has_pm:
                        try:
                            pm = stripe.PaymentMethod.retrieve(payment_method_id)
                            card = pm.get("card", {})
                        except Exception:
                            card = {"last4": "****", "brand": "unknown", "exp_month": "??", "exp_year": "????"}
                        db.users.update_one(
                            {"user_id": user_id},
                            {"$set": {
                                "stripe_customer_id": customer_id,
                                "default_payment_method_id": payment_method_id,
                                "default_payment_method_last4": card.get("last4", "****"),
                                "default_payment_method_brand": card.get("brand", "unknown"),
                                "default_payment_method_exp": f"{card.get('exp_month', '??')}/{card.get('exp_year', '????')}",
                                "payment_method_consent": True,
                                "payment_method_setup_at": datetime.now(timezone.utc).isoformat(),
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                            }}
                        )
                        print(f"[GUARANTEE] Auto-saved payment method {payment_method_id[:15]}... for user {user_id}")
            except Exception as pm_err:
                print(f"[GUARANTEE] Auto-save payment method error (non-blocking): {pm_err}")
            
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

            # NOTE: Confirmation email (with ICS + proof link) is sent by the
            # webhook router (webhooks.py) which is async and can await
            # EmailService directly. No email logic here.
            
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
            pm_id = f"pm_dev_{guarantee['guarantee_id'][:8]}"
            # Auto-confirm in dev mode
            db.payment_guarantees.update_one(
                {"stripe_session_id": session_id},
                {"$set": {
                    "status": "completed",
                    "stripe_payment_method_id": pm_id,
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
                    "stripe_payment_method_id": pm_id,
                    "guaranteed_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            # Auto-save as default payment method on user profile (dev mode)
            participant = db.participants.find_one(
                {"participant_id": guarantee['participant_id']},
                {"_id": 0, "user_id": 1}
            )
            if participant and participant.get("user_id"):
                uid = participant["user_id"]
                existing_pm = db.users.find_one(
                    {"user_id": uid, "default_payment_method_id": {"$exists": True, "$ne": None}},
                    {"_id": 0, "user_id": 1}
                )
                if not existing_pm:
                    db.users.update_one(
                        {"user_id": participant["user_id"]},
                        {"$set": {
                            "stripe_customer_id": guarantee.get("stripe_customer_id"),
                            "default_payment_method_id": pm_id,
                            "default_payment_method_last4": "4242",
                            "default_payment_method_brand": "visa",
                            "default_payment_method_exp": "12/2030",
                            "payment_method_consent": True,
                            "payment_method_setup_at": datetime.now(timezone.utc).isoformat(),
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }}
                    )
                    print(f"[GUARANTEE_DEV] Auto-saved dev payment method for user {participant['user_id']}")
            
            return {
                "success": True,
                "guarantee_id": guarantee.get("guarantee_id"),
                "status": "completed",
                "participant_id": guarantee.get("participant_id"),
                "dev_mode": True
            }
        
        # Real mode: if still pending, check Stripe directly (fallback if webhook delayed)
        if guarantee.get("status") == "pending" and guarantee.get("stripe_session_id"):
            try:
                session = stripe.checkout.Session.retrieve(guarantee["stripe_session_id"])
                if session.status == "complete" and session.setup_intent:
                    result = StripeGuaranteeService.handle_checkout_completed({
                        "id": session.id,
                        "setup_intent": session.setup_intent,
                        "customer": session.customer,
                        "metadata": dict(session.metadata) if session.metadata else {}
                    })
                    if result.get("success"):
                        guarantee = db.payment_guarantees.find_one(
                            {"stripe_session_id": session_id}, {"_id": 0}
                        )
            except Exception as e:
                print(f"[GUARANTEE_STATUS] Stripe direct check failed: {e}")
        
        return {
            "success": True,
            "guarantee_id": guarantee.get("guarantee_id"),
            "status": guarantee.get("status"),
            "participant_id": guarantee.get("participant_id")
        }
    
    # ────────────────────────────────────────────────────────
    #  Default Payment Method (Settings)
    # ────────────────────────────────────────────────────────

    @staticmethod
    def setup_default_payment_method_session(
        user_id: str,
        user_email: str,
        user_name: str,
        frontend_url: str
    ) -> dict:
        """
        Create a Stripe Checkout Session (setup mode) to save a default
        payment method in Settings.  The captured PaymentMethod can then be
        reused for future organizer guarantees without redirect.
        """
        try:
            if not STRIPE_API_KEY or STRIPE_API_KEY == 'sk_test_emergent':
                # Dev mode — auto-save simulated card
                dev_session_id = f"cs_dev_pm_{user_id[:8]}"
                dev_pm_id = f"pm_dev_{user_id[:8]}"

                db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {
                        "stripe_customer_id": f"cus_dev_{user_id[:8]}",
                        "default_payment_method_id": dev_pm_id,
                        "default_payment_method_last4": "4242",
                        "default_payment_method_brand": "visa",
                        "default_payment_method_exp": "12/2028",
                        "payment_method_consent": True,
                        "payment_method_setup_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }}
                )

                success_url = (
                    f"{frontend_url}/settings/payment"
                    f"?setup_status=success&session_id={dev_session_id}&dev_mode=true"
                )
                return {
                    "success": True,
                    "checkout_url": success_url,
                    "session_id": dev_session_id,
                    "dev_mode": True
                }

            # Production — real Stripe
            customer = StripeGuaranteeService._get_or_create_customer(user_email, user_name)

            success_url = (
                f"{frontend_url}/settings/payment"
                "?setup_status=success&session_id={CHECKOUT_SESSION_ID}"
            )
            cancel_url = f"{frontend_url}/settings/payment?setup_status=cancelled"

            session = stripe.checkout.Session.create(
                mode="setup",
                customer=customer.id,
                payment_method_types=["card"],
                success_url=success_url,
                cancel_url=cancel_url,
                locale="fr",
                metadata={
                    "type": "nlyt_default_payment_method",
                    "user_id": user_id
                },
                custom_text={
                    "submit": {
                        "message": (
                            "En enregistrant cette carte, vous autorisez NLYT "
                            "à l'utiliser automatiquement pour vos garanties "
                            "organisateur futures."
                        )
                    }
                }
            )

            # Persist customer_id on user doc
            db.users.update_one(
                {"user_id": user_id},
                {"$set": {"stripe_customer_id": customer.id}}
            )

            return {
                "success": True,
                "checkout_url": session.url,
                "session_id": session.id
            }

        except stripe.error.StripeError as e:
            print(f"[DEFAULT_PM_SETUP] Stripe error: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            print(f"[DEFAULT_PM_SETUP] Error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def handle_default_payment_setup_completed(session: dict) -> dict:
        """
        Process checkout.session.completed for a default-payment-method setup.
        Retrieves the PaymentMethod from the SetupIntent and persists card
        details + consent flag on the user document.
        """
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        setup_intent_id = session.get("setup_intent")
        customer_id = session.get("customer")

        if not user_id:
            return {"success": False, "error": "No user_id in metadata"}

        try:
            setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
            payment_method_id = setup_intent.payment_method
            payment_method = stripe.PaymentMethod.retrieve(payment_method_id)

            card = payment_method.get("card", {})

            db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "stripe_customer_id": customer_id,
                    "default_payment_method_id": payment_method_id,
                    "default_payment_method_last4": card.get("last4", "****"),
                    "default_payment_method_brand": card.get("brand", "unknown"),
                    "default_payment_method_exp": (
                        f"{card.get('exp_month', '??')}/{card.get('exp_year', '????')}"
                    ),
                    "payment_method_consent": True,
                    "payment_method_setup_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )

            return {"success": True, "user_id": user_id, "payment_method_id": payment_method_id}
        except Exception as e:
            print(f"[DEFAULT_PM_SETUP] Error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def check_default_payment_setup(session_id: str, user_id: str) -> dict:
        """
        Polling endpoint helper — checks whether the default payment method
        has been saved.  If the webhook hasn't arrived yet, proactively
        retrieves the session from Stripe and processes it.
        """
        user = db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            return {"success": False, "error": "User not found"}

        if user.get("default_payment_method_id"):
            return {
                "success": True,
                "status": "completed",
                "payment_method": {
                    "last4": user.get("default_payment_method_last4"),
                    "brand": user.get("default_payment_method_brand"),
                    "exp": user.get("default_payment_method_exp")
                }
            }

        # Fallback: query Stripe directly if webhook delayed
        if (STRIPE_API_KEY and STRIPE_API_KEY != 'sk_test_emergent'
                and session_id and not session_id.startswith('cs_dev_')):
            try:
                s = stripe.checkout.Session.retrieve(session_id)
                if s.status == "complete" and s.setup_intent:
                    return StripeGuaranteeService.handle_default_payment_setup_completed({
                        "id": s.id,
                        "setup_intent": s.setup_intent,
                        "customer": s.customer,
                        "metadata": dict(s.metadata) if s.metadata else {}
                    })
            except Exception as e:
                print(f"[DEFAULT_PM_CHECK] Stripe check failed: {e}")

        return {"success": True, "status": "pending"}

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
        
        if guarantee.get("status") in ("released", "captured"):
            return {"success": False, "error": f"Guarantee already {guarantee['status']}"}
        
        db.payment_guarantees.update_one(
            {"guarantee_id": guarantee_id},
            {"$set": {
                "status": "released",
                "release_reason": reason,
                "released_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Update participant status
        db.participants.update_one(
            {"guarantee_id": guarantee_id},
            {"$set": {"status": "guarantee_released"}}
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
        
        # Dev mode: simulate capture
        if not STRIPE_API_KEY or STRIPE_API_KEY == 'sk_test_emergent':
            db.payment_guarantees.update_one(
                {"guarantee_id": guarantee_id},
                {"$set": {
                    "status": "captured",
                    "capture_reason": reason,
                    "stripe_payment_intent_id": f"pi_dev_{guarantee_id[:8]}",
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            return {"success": True, "message": "Guarantee captured (dev mode)", "dev_mode": True}
        
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
