from fastapi import APIRouter, HTTPException, Request
from pymongo import MongoClient
import os
import sys
import json
sys.path.append('/app/backend')
from services.payment_service import PaymentService
from emergentintegrations.payments.stripe.checkout import StripeCheckout

router = APIRouter()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

@router.post("/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")
    
    try:
        host_url = str(request.base_url).rstrip('/')
        stripe_checkout = StripeCheckout(
            api_key=STRIPE_API_KEY,
            webhook_url=f"{host_url}/api/webhooks/stripe"
        )
        
        webhook_response = await stripe_checkout.handle_webhook(body, signature)
        
        event_type = webhook_response.event_type
        event_id = webhook_response.event_id
        session_id = webhook_response.session_id
        payment_status = webhook_response.payment_status
        metadata = webhook_response.metadata
        
        PaymentService.log_stripe_event(event_id, event_type, {
            "session_id": session_id,
            "payment_status": payment_status,
            "metadata": metadata
        })
        
        if event_type == "checkout.session.completed" and payment_status == "paid":
            guarantee_id = metadata.get('guarantee_id')
            
            if guarantee_id:
                transaction = db.payment_transactions.find_one(
                    {"session_id": session_id, "guarantee_id": guarantee_id},
                    {"_id": 0}
                )
                
                if transaction and transaction['status'] != 'completed':
                    db.payment_transactions.update_one(
                        {"session_id": session_id},
                        {"$set": {"status": "completed", "payment_status": payment_status}}
                    )
                    
                    PaymentService.update_guarantee_status(
                        guarantee_id,
                        "setup_complete",
                        {"stripe_session_id": session_id}
                    )
        
        return {"status": "success", "event_type": event_type}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)}")