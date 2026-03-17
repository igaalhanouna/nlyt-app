from fastapi import Request, HTTPException, status
from typing import Optional
import sys
sys.path.append('/app/backend')
from utils.jwt_utils import verify_token

async def get_current_user(request: Request) -> Optional[dict]:
    import logging
    logger = logging.getLogger(__name__)
    
    # Debug log all headers
    logger.info(f"[AUTH_DEBUG] All headers: {dict(request.headers)}")
    
    auth_header = request.headers.get('Authorization') or request.headers.get('authorization')
    logger.info(f"[AUTH_DEBUG] Auth header: {auth_header}")
    
    if not auth_header or not auth_header.startswith('Bearer '):
        logger.error(f"[AUTH_DEBUG] Missing or invalid auth header: {auth_header}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification manquant"
        )
    
    token = auth_header.split(' ')[1]
    logger.info(f"[AUTH_DEBUG] Extracted token: {token[:30]}...")
    payload = verify_token(token)
    
    if not payload:
        logger.error(f"[AUTH_DEBUG] Token verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré"
        )
    
    logger.info(f"[AUTH_DEBUG] Auth successful for user: {payload.get('email')}")
    return payload

async def get_optional_user(request: Request) -> Optional[dict]:
    auth_header = request.headers.get('Authorization') or request.headers.get('authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    return verify_token(token)