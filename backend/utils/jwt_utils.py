from datetime import datetime, timedelta, timezone
import jwt
import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
import logging

# Load .env from backend directory
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get('JWT_SECRET', 'nlyt_secure_jwt_secret_key_2026')
JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS', 720))

logger.info(f"[JWT_UTILS] Loaded JWT_SECRET (first 10 chars): {JWT_SECRET[:10]}...")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    try:
        logger.info(f"[JWT_VERIFY] Attempting to verify token (first 30 chars): {token[:30]}...")
        logger.info(f"[JWT_VERIFY] Using secret (first 10 chars): {JWT_SECRET[:10]}...")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        logger.info(f"[JWT_VERIFY] ✅ Token valid. Payload: email={payload.get('email')}, type={payload.get('type')}")
        return payload
    except jwt.ExpiredSignatureError:
        logger.error(f"[JWT_VERIFY] ❌ Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.error(f"[JWT_VERIFY] ❌ Invalid token: {str(e)}")
        return None

def create_reset_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    to_encode = {"email": email, "exp": expire, "type": "reset"}
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_verification_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    to_encode = {"email": email, "exp": expire, "type": "verification"}
    token = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    logger.info(f"[JWT_CREATE] Created verification token for {email}")
    logger.info(f"[JWT_CREATE] Using secret (first 10 chars): {JWT_SECRET[:10]}...")
    logger.info(f"[JWT_CREATE] Token (first 30 chars): {token[:30]}...")
    return token