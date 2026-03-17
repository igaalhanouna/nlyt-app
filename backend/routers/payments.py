from fastapi import APIRouter, HTTPException, Request
from pymongo import MongoClient
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
import os
import sys
sys.path.append('/app/backend')
from middleware.auth_middleware import get_optional_user
from services.payment_service import PaymentService
from utils.date_utils import now_utc

router = APIRouter()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

@router.post("/guarantee/create")
async def create_payment_guarantee(participant_id: str, appointment_id: str, request: Request):
    participant = db.participants.find_one({"participant_id": participant_id}, {"_id": 0})
    appointment = db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    
    if not participant or not appointment:
        raise HTTPException(status_code=404, detail="Données introuvables")
    
    guarantee_mode = PaymentService.determine_guarantee_mode(appointment['start_datetime'])
    
    guarantee = PaymentService.create_payment_guarantee(
        participant_id=participant_id,
        appointment_id=appointment_id,
        guarantee_mode=guarantee_mode,
        amount=appointment['penalty_amount'],
        currency=appointment['penalty_currency']
    )
    
    return guarantee

@router.post("/guarantee/{guarantee_id}/setup")
async def setup_payment_method(guarantee_id: str, request: Request):
    guarantee = PaymentService.get_guarantee_by_id(guarantee_id)
    
    if not guarantee:
        raise HTTPException(status_code=404, detail="Garantie introuvable")
    
    appointment = db.appointments.find_one({"appointment_id": guarantee['appointment_id']}, {"_id": 0})
    participant = db.participants.find_one({"participant_id": guarantee['participant_id']}, {"_id": 0})
    
    host_url = str(request.base_url).rstrip('/')
    success_url = f"{host_url}/payment-success?session_id={{CHECKOUT_SESSION_ID}}&guarantee_id={guarantee_id}"
    cancel_url = f"{host_url}/payment-cancel?guarantee_id={guarantee_id}"
    
    stripe_checkout = StripeCheckout(
        api_key=STRIPE_API_KEY,
        webhook_url=f"{host_url}/api/webhooks/stripe"
    )
    
    checkout_request = CheckoutSessionRequest(
        amount=float(guarantee['amount']),
        currency=guarantee['currency'],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "guarantee_id": guarantee_id,
            "appointment_id": guarantee['appointment_id'],
            "participant_id": guarantee['participant_id'],
            "type": "payment_guarantee"
        }
    )
    
    session = await stripe_checkout.create_checkout_session(checkout_request)
    
    PaymentService.update_guarantee_status(
        guarantee_id,
        "awaiting_payment_method",
        {"stripe_session_id": session.session_id}
    )
    
    transaction_id = str(__import__('uuid').uuid4())
    db.payment_transactions.insert_one({
        "transaction_id": transaction_id,
        "guarantee_id": guarantee_id,
        "session_id": session.session_id,
        "amount": guarantee['amount'],
        "currency": guarantee['currency'],
        "status": "pending",
        "created_at": now_utc().isoformat()
    })
    
    return {"checkout_url": session.url, "session_id": session.session_id}

@router.get("/guarantee/{guarantee_id}")
async def get_guarantee(guarantee_id: str):
    guarantee = PaymentService.get_guarantee_by_id(guarantee_id)
    
    if not guarantee:
        raise HTTPException(status_code=404, detail="Garantie introuvable")
    
    return guarantee

@router.post("/guarantee/{guarantee_id}/release")
async def release_guarantee(guarantee_id: str, reason: str, request: Request):
    user = await get_optional_user(request)
    
    result = PaymentService.release_guarantee(guarantee_id, reason)
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return result

@router.get("/transactions")
async def list_transactions(appointment_id: str = None):
    query = {}
    if appointment_id:
        guarantees = list(db.payment_guarantees.find({"appointment_id": appointment_id}, {"_id": 0}))
        guarantee_ids = [g['guarantee_id'] for g in guarantees]
        query["guarantee_id"] = {"$in": guarantee_ids}
    
    transactions = list(db.payment_transactions.find(query, {"_id": 0}).sort("created_at", -1))
    return {"transactions": transactions}