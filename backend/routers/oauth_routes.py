"""
OAuth routes for Google (Emergent Auth) and Microsoft login/signup.
Account linking: same email = same account, no duplicates.
"""
import os
import uuid
import secrets
import urllib.parse
import logging
import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from database import db
from utils.jwt_utils import create_access_token
from utils.date_utils import now_utc_iso
from services.workspace_service import WorkspaceService
from services.wallet_service import create_wallet
from rate_limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)

FRONTEND_URL = os.environ.get('FRONTEND_URL', '').rstrip('/')
MICROSOFT_CLIENT_ID = os.environ.get('MICROSOFT_CLIENT_ID', '')
MICROSOFT_CLIENT_SECRET = os.environ.get('MICROSOFT_CLIENT_SECRET', '')
MICROSOFT_TENANT_ID = os.environ.get('MICROSOFT_TENANT_ID', 'common')


# ─── Shared helpers ──────────────────────────────────────

def _find_or_create_oauth_user(email: str, first_name: str, last_name: str, provider: str, provider_id: str):
    """
    Account linking logic:
    - If email exists → link provider, return existing user
    - If new email → create user + workspace + wallet
    """
    now = now_utc_iso()
    email_lower = email.lower().strip()
    existing = db.users.find_one({"email": email_lower}, {"_id": 0})

    if existing:
        update_fields = {f"{provider}_id": provider_id, "updated_at": now}
        if not existing.get("is_verified"):
            update_fields["is_verified"] = True
        db.users.update_one({"email": email_lower}, {"$set": update_fields})
        user = db.users.find_one({"email": email_lower}, {"_id": 0})
        logger.info(f"[OAUTH] Linked {provider} to existing user {email_lower}")
        return user, False

    user_id = str(uuid.uuid4())
    user_doc = {
        "user_id": user_id,
        "email": email_lower,
        "first_name": first_name or "",
        "last_name": last_name or "",
        "password_hash": None,
        "auth_provider": provider,
        f"{provider}_id": provider_id,
        "is_verified": True,
        "phone": None,
        "created_at": now,
        "updated_at": now,
    }
    db.users.insert_one(user_doc)
    logger.info(f"[OAUTH] Created new user via {provider}: {email_lower} (ID: {user_id})")

    WorkspaceService.create_default_workspace(user_id, first_name or "", last_name or "")
    create_wallet(user_id)

    user = db.users.find_one({"email": email_lower}, {"_id": 0})
    return user, True


def _build_jwt_response(user: dict, is_new: bool):
    """Generate JWT and standard response for OAuth login."""
    # Auto-link orphan participants on every OAuth login
    from services.auth_service import _auto_link_user_to_participants
    _auto_link_user_to_participants(user["user_id"], user["email"])

    token_data = {
        "user_id": user["user_id"],
        "email": user["email"],
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", ""),
        "role": user.get("role", "user"),
    }
    access_token = create_access_token(token_data)

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "user_id": user["user_id"],
            "email": user["email"],
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
            "role": user.get("role", "user"),
        },
        "is_new_account": is_new,
    }


# ─── Google OAuth (via Emergent Auth) ────────────────────

class GoogleCallbackRequest(BaseModel):
    session_id: str


@router.post("/google/callback")
@limiter.limit("10/minute")
async def google_callback(request: Request, body: GoogleCallbackRequest):
    """Exchange Emergent Auth session_id for user data, create/link account, return JWT."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": body.session_id},
            )

        if resp.status_code != 200:
            logger.error(f"[OAUTH] Emergent Auth session exchange failed: {resp.status_code} {resp.text}")
            raise HTTPException(status_code=401, detail="Session Google invalide ou expirée")

        data = resp.json()
        email = data.get("email")
        name = data.get("name", "")
        google_id = data.get("id", "")

        if not email:
            raise HTTPException(status_code=400, detail="Email non disponible depuis Google")

        parts = name.split(" ", 1) if name else ["", ""]
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

        user, is_new = _find_or_create_oauth_user(email, first_name, last_name, "google", google_id)
        return _build_jwt_response(user, is_new)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[OAUTH] Google callback error: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'authentification Google")


# ─── Microsoft OAuth ─────────────────────────────────────

@router.get("/microsoft/login")
@limiter.limit("10/minute")
async def microsoft_login(request: Request):
    """Generate Microsoft OAuth authorization URL."""
    if not MICROSOFT_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Microsoft OAuth non configuré")

    redirect_uri = f"{FRONTEND_URL}/auth/callback"
    state = secrets.token_urlsafe(32)
    scopes = "openid email profile User.Read"

    params = urllib.parse.urlencode({
        "client_id": MICROSOFT_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scopes,
        "response_mode": "query",
        "state": state,
    })

    authorization_url = f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/oauth2/v2.0/authorize?{params}"

    return {"authorization_url": authorization_url, "state": state}


class MicrosoftCallbackRequest(BaseModel):
    code: str


@router.post("/microsoft/callback")
@limiter.limit("10/minute")
async def microsoft_callback(request: Request, body: MicrosoftCallbackRequest):
    """Exchange Microsoft authorization code for user data, create/link account, return JWT."""
    if not MICROSOFT_CLIENT_ID or not MICROSOFT_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Microsoft OAuth non configuré")

    redirect_uri = f"{FRONTEND_URL}/auth/callback"
    token_url = f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/oauth2/v2.0/token"

    try:
        # 1. Exchange code for access token
        async with httpx.AsyncClient(timeout=15) as client:
            token_resp = await client.post(
                token_url,
                data={
                    "client_id": MICROSOFT_CLIENT_ID,
                    "client_secret": MICROSOFT_CLIENT_SECRET,
                    "code": body.code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                    "scope": "openid email profile User.Read",
                },
            )

        if token_resp.status_code != 200:
            logger.error(f"[OAUTH] Microsoft token exchange failed: {token_resp.text}")
            raise HTTPException(status_code=401, detail="Code d'autorisation Microsoft invalide ou expiré")

        ms_access_token = token_resp.json().get("access_token")
        if not ms_access_token:
            raise HTTPException(status_code=401, detail="Token Microsoft non reçu")

        # 2. Get user profile from Microsoft Graph
        async with httpx.AsyncClient(timeout=10) as client:
            graph_resp = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {ms_access_token}"},
            )

        if graph_resp.status_code != 200:
            logger.error(f"[OAUTH] Microsoft Graph failed: {graph_resp.text}")
            raise HTTPException(status_code=401, detail="Impossible de récupérer le profil Microsoft")

        profile = graph_resp.json()
        email = profile.get("mail") or profile.get("userPrincipalName")
        microsoft_id = profile.get("id", "")
        first_name = profile.get("givenName", "")
        last_name = profile.get("surname", "")

        if not email:
            raise HTTPException(status_code=400, detail="Email non disponible depuis Microsoft")

        user, is_new = _find_or_create_oauth_user(email, first_name, last_name, "microsoft", microsoft_id)
        return _build_jwt_response(user, is_new)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[OAUTH] Microsoft callback error: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'authentification Microsoft")
