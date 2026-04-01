import os
from dotenv import load_dotenv
import sys
import logging
from datetime import datetime, timedelta, timezone
sys.path.append('/app/backend')
from utils.password_utils import hash_password, verify_password
from utils.jwt_utils import create_access_token, create_reset_token, create_verification_token, verify_token
from utils.date_utils import now_utc
from services.email_service import EmailService
from services.workspace_service import WorkspaceService
import uuid

load_dotenv()

from database import db
logger = logging.getLogger(__name__)



RESEND_RATE_LIMIT_MINUTES = 2  # Minimum time between resend requests

class AuthService:
    @staticmethod
    async def register_user(email: str, password: str, first_name: str, last_name: str, phone: str = None, base_url: str = ""):
        existing_user = db.users.find_one({"email": email}, {"_id": 0})
        
        # If user exists and is not verified, allow resend instead of error
        if existing_user:
            if not existing_user.get('is_verified', False):
                logger.info(f"Registration attempted for existing unverified account: {email}")
                return {
                    "success": False, 
                    "error": "not_verified",
                    "message": "Un compte existe avec cet email mais n'est pas vérifié. Vérifiez vos emails ou demandez un nouvel email de vérification."
                }
            else:
                logger.warning(f"Registration failed: Email {email} already exists and is verified")
                return {"success": False, "error": "Un compte existe déjà avec cet email"}
        
        user_id = str(uuid.uuid4())
        hashed_password = hash_password(password)
        
        DEFAULT_MESSAGE = (
            "J'utilise NLYT pour perdre le moins de temps possible et m'organiser efficacement.\n\n"
            "En vous demandant une garantie, je veux vous faire comprendre qu'un rendez-vous non honoré "
            "représente une perte de temps et d'argent pour moi.\n\n"
            "De façon symétrique, en cas d'absence ou de retard de ma part, je m'impose à moi-même "
            "les mêmes règles de pénalités que je vous soumets.\n\n"
            "Comme vous pourrez le constater, en cas d'absence ou de retard, une partie de ces sommes "
            "ira sous forme de don à l'association ci-dessous.\n\n"
            "Merci de votre compréhension."
        )

        user = {
            "user_id": user_id,
            "email": email,
            "password_hash": hashed_password,
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "is_verified": False,
            "last_verification_email_sent": now_utc().isoformat(),
            "verification_email_sent_count": 1,
            "created_at": now_utc().isoformat(),
            "updated_at": now_utc().isoformat(),
            "appointment_defaults": {
                "default_message": DEFAULT_MESSAGE
            }
        }
        
        try:
            db.users.insert_one(user)
            logger.info(f"[REGISTER] ✅ User {email} created successfully (ID: {user_id})")
        except Exception as e:
            logger.error(f"[REGISTER] ❌ Failed to create user {email}: {str(e)}")
            return {"success": False, "error": "Erreur lors de la création du compte"}
        
        # Auto-create default workspace for the user
        logger.info(f"[REGISTER] Creating default workspace for user {user_id}")
        workspace = WorkspaceService.create_default_workspace(user_id, first_name, last_name)
        if workspace:
            logger.info(f"[REGISTER] ✅ Default workspace created: {workspace['workspace_id']}")
        else:
            logger.warning(f"[REGISTER] ⚠️ Failed to create default workspace for user {user_id}")

        # Auto-create wallet for the user
        from services.wallet_service import create_wallet
        wallet = create_wallet(user_id)
        logger.info(f"[REGISTER] ✅ Wallet created: {wallet['wallet_id']}")
        
        # Generate token
        logger.info(f"[REGISTER] Generating verification token for {email}")
        verification_token = create_verification_token(email)
        logger.info(f"[REGISTER] Token generated: {verification_token[:30]}...")
        
        # Send verification email
        logger.info(f"[REGISTER] 📧 Calling send_verification_email for {email}")
        email_result = await EmailService.send_verification_email(email, verification_token, base_url)
        logger.info(f"[REGISTER] Email send result: {email_result}")
        
        if not email_result.get('success'):
            logger.error(f"[REGISTER] ❌ Email send FAILED for {email}: {email_result.get('error')}")
            return {
                "success": False,
                "error": "email_send_failed",
                "message": "Compte créé mais l'email de vérification n'a pas pu être envoyé. Utilisez 'Renvoyer l'email' pour réessayer."
            }
        
        logger.info(f"[REGISTER] ✅ Registration complete for {email}")
        return {"success": True, "user_id": user_id, "message": "Compte créé. Vérifiez votre email."}
    
    @staticmethod
    async def resend_verification_email(email: str, base_url: str = ""):
        logger.info(f"[RESEND] ▶️ Starting resend for {email}")
        
        user = db.users.find_one({"email": email}, {"_id": 0})
        
        # Security: Don't leak account existence
        if not user:
            logger.info(f"[RESEND] User {email} does not exist (not leaking)")
            return {
                "success": True, 
                "message": "Si ce compte existe et n'est pas vérifié, un nouvel email de vérification a été envoyé."
            }
        
        # If already verified
        if user.get('is_verified', False):
            logger.info(f"[RESEND] User {email} is already verified")
            return {
                "success": True,
                "already_verified": True,
                "message": "Ce compte est déjà vérifié. Vous pouvez vous connecter."
            }
        
        # Rate limiting
        last_sent = user.get('last_verification_email_sent')
        if last_sent:
            try:
                last_sent_dt = datetime.fromisoformat(last_sent)
                now = now_utc()
                seconds_since = (now - last_sent_dt).total_seconds()
                logger.info(f"[RESEND] Last email sent {seconds_since:.0f} seconds ago")
                
                if seconds_since < RESEND_RATE_LIMIT_MINUTES * 60:
                    logger.warning(f"[RESEND] Rate limit exceeded for {email}")
                    return {
                        "success": False,
                        "error": "Veuillez attendre quelques minutes avant de demander un nouvel email."
                    }
            except Exception as e:
                logger.error(f"[RESEND] Error checking rate limit: {str(e)}")
        
        # Update timestamp and counter
        current_count = user.get('verification_email_sent_count', 1)
        db.users.update_one(
            {"email": email},
            {"$set": {
                "last_verification_email_sent": now_utc().isoformat(),
                "verification_email_sent_count": current_count + 1
            }}
        )
        logger.info(f"[RESEND] Updated timestamp and counter (attempt #{current_count + 1}) for {email}")
        
        # Generate new token
        verification_token = create_verification_token(email)
        logger.info(f"[RESEND] New token generated: {verification_token[:30]}...")
        
        # Send email
        logger.info(f"[RESEND] 📧 Calling send_verification_email for {email}")
        email_result = await EmailService.send_verification_email(email, verification_token, base_url)
        logger.info(f"[RESEND] Email send result: {email_result}")
        
        if not email_result.get('success'):
            logger.error(f"[RESEND] ❌ Email send FAILED for {email}: {email_result.get('error')}")
            return {
                "success": False,
                "error": "Erreur lors de l'envoi de l'email. Veuillez réessayer."
            }
        
        logger.info(f"[RESEND] ✅ Resend complete for {email}")
        return {
            "success": True,
            "message": "Un nouvel email de vérification a été envoyé. Vérifiez votre boîte de réception."
        }
    
    @staticmethod
    async def login_user(email: str, password: str):
        user = db.users.find_one({"email": email}, {"_id": 0})
        if not user:
            logger.warning(f"Login failed: User {email} not found")
            return {"success": False, "error": "Email ou mot de passe incorrect"}
        
        # Handle OAuth-only accounts (no password set)
        if not user.get('password_hash'):
            provider = user.get('auth_provider', '')
            if user.get('google_id'):
                provider = 'Google'
            elif user.get('microsoft_id'):
                provider = 'Microsoft'
            if provider:
                logger.warning(f"Login failed: {email} is an OAuth-only account ({provider})")
                return {"success": False, "error": f"Ce compte utilise {provider} pour se connecter. Utilisez le bouton « Continuer avec {provider} »."}
            return {"success": False, "error": "Email ou mot de passe incorrect"}
        
        if not verify_password(password, user['password_hash']):
            logger.warning(f"Login failed: Invalid password for {email}")
            return {"success": False, "error": "Email ou mot de passe incorrect"}
        
        if not user.get('is_verified', False):
            logger.warning(f"Login failed: Email {email} not verified")
            return {
                "success": False, 
                "error": "not_verified",
                "message": "Veuillez vérifier votre email avant de vous connecter"
            }
        
        # Ensure user has a workspace (migration for existing users)
        WorkspaceService.ensure_user_has_workspace(
            user['user_id'], 
            user['first_name'], 
            user['last_name']
        )
        
        user_role = user.get('role', 'user')
        token_data = {
            "user_id": user['user_id'],
            "email": user['email'],
            "first_name": user['first_name'],
            "last_name": user['last_name'],
            "role": user_role,
        }
        access_token = create_access_token(token_data)
        logger.info(f"User logged in: {email} (role={user_role})")
        
        user_response = {
            "user_id": user['user_id'],
            "email": user['email'],
            "first_name": user['first_name'],
            "last_name": user['last_name'],
            "phone": user.get('phone'),
            "is_verified": user['is_verified'],
            "created_at": user['created_at'],
            "role": user_role,
        }
        
        return {"success": True, "access_token": access_token, "user": user_response}
    
    @staticmethod
    async def verify_email(token: str):
        logger.info(f"Email verification attempt with token: {token[:20]}...")
        
        payload = verify_token(token)
        
        if not payload:
            logger.error(f"Email verification failed: Invalid or expired token")
            return {"success": False, "error": "Token invalide ou expiré"}
        
        if payload.get('type') != 'verification':
            logger.error(f"Email verification failed: Wrong token type {payload.get('type')}")
            return {"success": False, "error": "Type de token invalide"}
        
        email = payload.get('email')
        if not email:
            logger.error(f"Email verification failed: No email in token")
            return {"success": False, "error": "Token invalide"}
        
        logger.info(f"Verifying email for: {email}")
        
        user = db.users.find_one({"email": email}, {"_id": 0})
        if not user:
            logger.error(f"Email verification failed: User {email} not found")
            return {"success": False, "error": "Utilisateur introuvable"}
        
        if user.get('is_verified', False):
            logger.info(f"Email already verified for: {email}")
            return {"success": True, "message": "Email déjà vérifié"}
        
        result = db.users.update_one(
            {"email": email},
            {"$set": {"is_verified": True, "updated_at": now_utc().isoformat()}}
        )
        
        if result.modified_count > 0:
            logger.info(f"Email verified successfully for: {email}")
            return {"success": True, "message": "Email vérifié avec succès"}
        
        logger.error(f"Email verification failed: Database update failed for {email}")
        return {"success": False, "error": "Erreur lors de la vérification"}
    
    @staticmethod
    async def request_password_reset(email: str, base_url: str):
        user = db.users.find_one({"email": email}, {"_id": 0})
        if not user:
            logger.info(f"Password reset requested for non-existent email: {email}")
            return {"success": True, "message": "Si cet email existe, un lien de réinitialisation a été envoyé"}
        
        reset_token = create_reset_token(email)
        logger.info(f"Password reset token created for: {email}")
        
        await EmailService.send_password_reset_email(email, reset_token, base_url)
        
        return {"success": True, "message": "Si cet email existe, un lien de réinitialisation a été envoyé"}
    
    @staticmethod
    async def reset_password(token: str, new_password: str):
        logger.info(f"Password reset attempt with token: {token[:20]}...")
        
        payload = verify_token(token)
        if not payload or payload.get('type') != 'reset':
            logger.error("Password reset failed: Invalid or expired token")
            return {"success": False, "error": "Token invalide ou expiré"}
        
        email = payload.get('email')
        hashed_password = hash_password(new_password)
        
        result = db.users.update_one(
            {"email": email},
            {"$set": {"password_hash": hashed_password, "updated_at": now_utc().isoformat()}}
        )
        
        if result.modified_count > 0:
            logger.info(f"Password reset successfully for: {email}")
            return {"success": True, "message": "Mot de passe réinitialisé avec succès"}
        
        logger.error(f"Password reset failed: User {email} not found")
        return {"success": False, "error": "Utilisateur introuvable"}