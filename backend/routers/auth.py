from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
import sys
import os
sys.path.append('/app/backend')
from models.schemas import UserCreate, UserLogin, PasswordResetRequest, PasswordReset, TokenResponse
from services.auth_service import AuthService

router = APIRouter()

def get_frontend_url(request: Request) -> str:
    """Get FRONTEND_URL from env, fallback to request.base_url"""
    frontend_url = os.environ.get('FRONTEND_URL', '')
    if frontend_url:
        return frontend_url.rstrip('/')
    return str(request.base_url).rstrip('/')

@router.post("/register")
async def register(user: UserCreate, request: Request):
    base_url = get_frontend_url(request)
    result = await AuthService.register_user(
        email=user.email,
        password=user.password,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        base_url=base_url
    )
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return result

@router.post("/login")
async def login(credentials: UserLogin):
    result = await AuthService.login_user(credentials.email, credentials.password)
    
    if not result['success']:
        # Check if it's a "not_verified" error
        if result.get('error') == 'not_verified':
            raise HTTPException(
                status_code=401, 
                detail={'error': 'not_verified', 'message': result.get('message', 'Email non vérifié')}
            )
        raise HTTPException(status_code=401, detail=result['error'])
    
    return {
        "access_token": result['access_token'],
        "token_type": "bearer",
        "user": result['user']
    }

@router.get("/verify-email")
async def verify_email(token: str):
    result = await AuthService.verify_email(token)
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return result

@router.post("/forgot-password")
async def forgot_password(request_data: PasswordResetRequest, request: Request):
    base_url = get_frontend_url(request)
    result = await AuthService.request_password_reset(request_data.email, base_url)
    return result

@router.post("/reset-password")
async def reset_password(reset_data: PasswordReset):
    result = await AuthService.reset_password(reset_data.token, reset_data.new_password)
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return result

@router.post("/resend-verification")
async def resend_verification_email(request_data: PasswordResetRequest, request: Request):
    base_url = get_frontend_url(request)
    result = await AuthService.resend_verification_email(request_data.email, base_url)
    
    if not result.get('success', False):
        raise HTTPException(status_code=400, detail=result.get('error', 'Erreur lors du renvoi'))
    
    return result

@router.get("/me")
async def get_current_user_info(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    return user