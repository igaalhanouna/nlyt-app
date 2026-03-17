from fastapi import APIRouter, HTTPException, Request, Depends
from pymongo import MongoClient
import os
import sys
sys.path.append('/app/backend')
from middleware.auth_middleware import get_current_user
from services.auth_service import AuthService

router = APIRouter()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

@router.get("/email-attempts")
async def get_email_attempts(limit: int = 50, request: Request = None):
    """Get all email send attempts for debugging"""
    user = await get_current_user(request)
    
    attempts = list(db.email_attempts.find(
        {},
        {"_id": 0}
    ).sort("attempted_at", -1).limit(limit))
    
    return {"attempts": attempts, "count": len(attempts)}

@router.get("/users-debug")
async def get_users_debug(request: Request):
    """Get all users with verification status for debugging"""
    user = await get_current_user(request)
    
    users = list(db.users.find(
        {},
        {
            "_id": 0,
            "password_hash": 0
        }
    ).sort("created_at", -1))
    
    return {"users": users, "count": len(users)}

@router.post("/mark-verified/{email}")
async def mark_user_verified(email: str, request: Request):
    """Mark a user as verified (debug only)"""
    user = await get_current_user(request)
    
    result = db.users.update_one(
        {"email": email},
        {"$set": {"is_verified": True}}
    )
    
    if result.modified_count > 0:
        return {"success": True, "message": f"User {email} marked as verified"}
    return {"success": False, "message": "User not found"}

@router.delete("/delete-unverified/{email}")
async def delete_unverified_user(email: str, request: Request):
    """Delete an unverified user (debug only)"""
    user = await get_current_user(request)
    
    # Only delete if not verified
    result = db.users.delete_one({"email": email, "is_verified": False})
    
    if result.deleted_count > 0:
        return {"success": True, "message": f"Unverified user {email} deleted"}
    return {"success": False, "message": "User not found or already verified"}

@router.post("/force-resend/{email}")
async def force_resend_verification(email: str, request: Request):
    """Force resend verification email bypassing rate limit"""
    user = await get_current_user(request)
    
    # Reset rate limit timestamp
    db.users.update_one(
        {"email": email},
        {"$set": {"last_verification_email_sent": "2020-01-01T00:00:00+00:00"}}
    )
    
    # Call resend
    base_url = str(request.base_url).rstrip('/')
    result = await AuthService.resend_verification_email(email, base_url)
    
    return result

@router.post("/cleanup-test-user/{email}")
async def cleanup_test_user(email: str, secret: str):
    """Delete a test user and related data (public endpoint with secret)"""
    # Simple secret check to prevent abuse
    if secret != "nlyt_cleanup_2026":
        return {"success": False, "error": "Invalid secret"}
    
    # Only allow specific test emails
    allowed_emails = ["igaal@hotmail.com", "igaal+test@hotmail.com"]
    if email not in allowed_emails:
        return {"success": False, "error": "Email not in allowed cleanup list"}
    
    # Delete user
    user_result = db.users.delete_many({"email": email})
    
    # Delete email attempts
    email_result = db.email_attempts.delete_many({"email": email})
    
    return {
        "success": True,
        "users_deleted": user_result.deleted_count,
        "email_attempts_deleted": email_result.deleted_count,
        "message": f"Cleaned up {email}"
    }


@router.post("/trigger-reminders")
async def trigger_reminders(request: Request):
    """Manually trigger the reminder job for testing"""
    user = await get_current_user(request)
    
    try:
        from services.reminder_service import run_reminder_job
        count = await run_reminder_job()
        return {"success": True, "reminders_processed": count}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/headers")  
async def debug_headers(request: Request):
    """Debug endpoint to check headers (no auth required)"""
    headers = dict(request.headers)
    return {
        "headers": headers,
        "auth_header": headers.get('authorization'),
        "has_bearer": headers.get('authorization', '').startswith('Bearer ') if headers.get('authorization') else False
    }
