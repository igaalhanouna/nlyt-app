import os
from pymongo import MongoClient
from dotenv import load_dotenv
import uuid
import sys
sys.path.append('/app/backend')
from utils.date_utils import now_utc
from datetime import datetime, timedelta, timezone

load_dotenv()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

class PaymentService:
    @staticmethod
    def create_payment_guarantee(participant_id: str, appointment_id: str, 
                                guarantee_mode: str, amount: float, currency: str = "eur") -> dict:
        guarantee_id = str(uuid.uuid4())
        
        guarantee = {
            "guarantee_id": guarantee_id,
            "participant_id": participant_id,
            "appointment_id": appointment_id,
            "guarantee_mode": guarantee_mode,
            "amount": amount,
            "currency": currency,
            "status": "not_started",
            "stripe_setup_intent_id": None,
            "stripe_payment_intent_id": None,
            "stripe_payment_method_id": None,
            "capture_before": None,
            "created_at": now_utc().isoformat(),
            "updated_at": now_utc().isoformat()
        }
        
        db.payment_guarantees.insert_one(guarantee)
        return guarantee
    
    @staticmethod
    def update_guarantee_status(guarantee_id: str, status: str, update_data: dict = None) -> bool:
        update_fields = {"status": status, "updated_at": now_utc().isoformat()}
        if update_data:
            update_fields.update(update_data)
        
        result = db.payment_guarantees.update_one(
            {"guarantee_id": guarantee_id},
            {"$set": update_fields}
        )
        return result.modified_count > 0
    
    @staticmethod
    def determine_guarantee_mode(appointment_start_datetime: str) -> str:
        start_dt = datetime.fromisoformat(appointment_start_datetime.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        days_until = (start_dt - now).days
        
        if days_until <= 7:
            return "auth_now"
        else:
            return "auth_later"
    
    @staticmethod
    def log_stripe_event(event_id: str, event_type: str, event_data: dict) -> None:
        log_entry = {
            "log_id": str(uuid.uuid4()),
            "event_id": event_id,
            "event_type": event_type,
            "event_data": event_data,
            "received_at": now_utc().isoformat()
        }
        db.stripe_events.insert_one(log_entry)
    
    @staticmethod
    def get_guarantee_by_id(guarantee_id: str) -> dict:
        return db.payment_guarantees.find_one({"guarantee_id": guarantee_id}, {"_id": 0})
    
    @staticmethod
    def release_guarantee(guarantee_id: str, reason: str) -> dict:
        guarantee = PaymentService.get_guarantee_by_id(guarantee_id)
        if not guarantee:
            return {"success": False, "error": "Guarantee not found"}
        
        if guarantee['status'] == "authorization_active":
            update_data = {"release_reason": reason}
            PaymentService.update_guarantee_status(guarantee_id, "released", update_data)
            return {"success": True, "message": "Guarantee released"}
        
        return {"success": False, "error": "Cannot release guarantee in current state"}