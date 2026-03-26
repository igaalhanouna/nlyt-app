"""
Stripe Connect Express — Onboarding Service

Manages the lifecycle of Stripe Express accounts for NLYT users.
All Connect data is stored in the existing `wallets` collection.

Statuses: not_started → onboarding → active | restricted | disabled
Business types: individual (particulier/indépendant) | company (société/organisation)
"""
import os
import stripe
import logging
from datetime import datetime, timezone
from database import db

logger = logging.getLogger(__name__)

STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')
FRONTEND_URL = os.environ.get('FRONTEND_URL', '').rstrip('/')
DEFAULT_CONNECT_COUNTRY = "FR"

stripe.api_key = STRIPE_API_KEY

SUPPORTED_COUNTRIES = {
    "FR", "DE", "ES", "IT", "NL", "BE", "AT", "PT", "IE", "FI",
    "LU", "GR", "EE", "LV", "LT", "SK", "SI", "MT", "CY",
    "GB", "US", "CA", "AU", "NZ", "JP", "SG", "HK",
    "CH", "NO", "SE", "DK", "PL", "CZ", "HU", "RO", "BG", "HR",
}

VALID_BUSINESS_TYPES = {"individual", "company"}


def get_connect_country(user: dict) -> str:
    country = (user.get("country") or "").upper().strip()
    if country and country in SUPPORTED_COUNTRIES:
        return country
    return DEFAULT_CONNECT_COUNTRY


def start_onboarding(user_id: str, business_type: str = "individual") -> dict:
    """
    Create or resume Stripe Connect Express onboarding.
    business_type: 'individual' (particulier/indépendant) or 'company' (société/organisation)
    """
    if business_type not in VALID_BUSINESS_TYPES:
        return {"success": False, "error": f"Type de profil invalide: {business_type}"}

    if not STRIPE_API_KEY or STRIPE_API_KEY == 'sk_test_emergent':
        return _dev_mode_onboarding(user_id, business_type)

    wallet = db.wallets.find_one({"user_id": user_id, "wallet_type": "user"}, {"_id": 0})
    if not wallet:
        return {"success": False, "error": "Wallet introuvable"}

    user = db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return {"success": False, "error": "Utilisateur introuvable"}

    account_id = wallet.get("stripe_connect_account_id")
    current_status = wallet.get("stripe_connect_status", "not_started")

    # If already active, no link needed
    if current_status == "active" and account_id:
        return {
            "success": True,
            "connect_status": "active",
            "onboarding_url": None,
            "message": "Compte déjà vérifié et actif",
        }

    try:
        # Create Express account if none exists
        if not account_id:
            country = get_connect_country(user)
            create_params = {
                "type": "express",
                "country": country,
                "email": user.get("email"),
                "business_type": business_type,
                "metadata": {"nlyt_user_id": user_id, "nlyt_wallet_id": wallet["wallet_id"]},
                "capabilities": {"transfers": {"requested": True}},
            }

            if business_type == "individual":
                create_params["individual"] = {
                    "first_name": user.get("first_name", ""),
                    "last_name": user.get("last_name", ""),
                    "email": user.get("email"),
                }
            elif business_type == "company":
                company_name = user.get("company_name") or user.get("organization_name") or ""
                if company_name:
                    create_params["company"] = {"name": company_name}

            account = stripe.Account.create(**create_params)
            account_id = account.id

            now = datetime.now(timezone.utc).isoformat()
            db.wallets.update_one(
                {"wallet_id": wallet["wallet_id"]},
                {"$set": {
                    "stripe_connect_account_id": account_id,
                    "stripe_connect_status": "onboarding",
                    "stripe_connect_business_type": business_type,
                    "stripe_connect_country": country,
                    "stripe_connect_created_at": now,
                    "updated_at": now,
                }}
            )
            logger.info(f"[CONNECT] Created Express account {account_id} for user {user_id} (country={country}, business_type={business_type})")

        # Generate onboarding link
        account_link = stripe.AccountLink.create(
            account=account_id,
            type="account_onboarding",
            return_url=f"{FRONTEND_URL}/settings/wallet?connect=complete",
            refresh_url=f"{FRONTEND_URL}/settings/wallet?connect=refresh",
        )

        return {
            "success": True,
            "connect_status": wallet.get("stripe_connect_status", "onboarding"),
            "onboarding_url": account_link.url,
        }

    except stripe.error.StripeError as e:
        error_msg = str(e)
        if "signed up for Connect" in error_msg:
            logger.warning(f"[CONNECT] Stripe Connect not enabled — falling back to dev mode for user {user_id}")
            return _dev_mode_onboarding(user_id, business_type)
        logger.error(f"[CONNECT] Stripe error for user {user_id}: {e}")
        return {"success": False, "error": error_msg}


def reset_connect_account(user_id: str, new_business_type: str) -> dict:
    """
    Reset a user's Connect account to allow changing business_type.
    Deletes the Stripe account and resets wallet Connect fields.
    Blocks if pending payouts exist.
    """
    if new_business_type not in VALID_BUSINESS_TYPES:
        return {"success": False, "error": f"Type de profil invalide: {new_business_type}"}

    wallet = db.wallets.find_one({"user_id": user_id, "wallet_type": "user"}, {"_id": 0})
    if not wallet:
        return {"success": False, "error": "Wallet introuvable"}

    account_id = wallet.get("stripe_connect_account_id")
    current_type = wallet.get("stripe_connect_business_type")

    if current_type == new_business_type:
        return {"success": False, "error": "Le type de profil est déjà celui demandé"}

    # Block if pending payouts
    if wallet.get("pending_balance", 0) > 0:
        return {
            "success": False,
            "error": "Impossible de modifier le profil : des fonds sont en attente de vérification. Réessayez une fois la période de vérification terminée.",
        }

    # Delete existing Stripe account if real
    if account_id and not account_id.startswith("acct_dev_") and not account_id.startswith("acct_demo_"):
        if STRIPE_API_KEY and STRIPE_API_KEY != 'sk_test_emergent':
            try:
                stripe.Account.delete(account_id)
                logger.info(f"[CONNECT] Deleted Stripe account {account_id} for user {user_id} (type change: {current_type} → {new_business_type})")
            except stripe.error.StripeError as e:
                logger.error(f"[CONNECT] Failed to delete account {account_id}: {e}")
                return {"success": False, "error": f"Erreur Stripe lors de la suppression: {str(e)}"}

    # Reset wallet Connect fields
    now = datetime.now(timezone.utc).isoformat()
    db.wallets.update_one(
        {"wallet_id": wallet["wallet_id"]},
        {"$set": {
            "stripe_connect_account_id": None,
            "stripe_connect_status": "not_started",
            "stripe_connect_business_type": new_business_type,
            "stripe_connect_details_submitted": False,
            "stripe_connect_charges_enabled": False,
            "stripe_connect_payouts_enabled": False,
            "stripe_connect_requirements": {},
            "stripe_connect_country": None,
            "stripe_connect_created_at": None,
            "stripe_connect_onboarded_at": None,
            "updated_at": now,
        }}
    )

    logger.info(f"[CONNECT] Reset Connect for user {user_id}: {current_type} → {new_business_type}")
    return {
        "success": True,
        "message": f"Profil modifié en '{new_business_type}'. Vous pouvez maintenant relancer l'onboarding.",
        "new_business_type": new_business_type,
    }


def get_connect_status(user_id: str) -> dict:
    """Get current Connect status from wallet."""
    wallet = db.wallets.find_one({"user_id": user_id, "wallet_type": "user"}, {"_id": 0})
    if not wallet:
        return {"connect_status": "not_started"}

    return {
        "connect_status": wallet.get("stripe_connect_status", "not_started"),
        "business_type": wallet.get("stripe_connect_business_type"),
        "details_submitted": wallet.get("stripe_connect_details_submitted", False),
        "charges_enabled": wallet.get("stripe_connect_charges_enabled", False),
        "payouts_enabled": wallet.get("stripe_connect_payouts_enabled", False),
        "requirements": wallet.get("stripe_connect_requirements", {}),
        "country": wallet.get("stripe_connect_country"),
        "onboarded_at": wallet.get("stripe_connect_onboarded_at"),
    }


def create_dashboard_link(user_id: str) -> dict:
    """Generate a Stripe Express Dashboard link for an active account."""
    wallet = db.wallets.find_one({"user_id": user_id, "wallet_type": "user"}, {"_id": 0})
    if not wallet:
        return {"success": False, "error": "Wallet introuvable"}

    account_id = wallet.get("stripe_connect_account_id")
    if not account_id:
        return {"success": False, "error": "Aucun compte Stripe connecté"}

    if wallet.get("stripe_connect_status") != "active":
        return {"success": False, "error": "Le compte doit être actif pour accéder au dashboard"}

    # Dev mode accounts can't use real Stripe dashboard
    is_dev_account = account_id.startswith("acct_dev_") or account_id.startswith("acct_demo_")
    if not STRIPE_API_KEY or STRIPE_API_KEY == 'sk_test_emergent' or is_dev_account:
        return {"success": True, "dashboard_url": f"{FRONTEND_URL}/settings/wallet?dev_dashboard=true"}

    try:
        login_link = stripe.Account.create_login_link(account_id)
        return {"success": True, "dashboard_url": login_link.url}
    except stripe.error.StripeError as e:
        logger.error(f"[CONNECT] Dashboard link error for user {user_id}: {e}")
        return {"success": False, "error": str(e)}


def handle_account_updated(account_data: dict) -> dict:
    """Process account.updated webhook event."""
    account_id = account_data.get("id")
    if not account_id:
        return {"success": False, "error": "No account ID"}

    wallet = db.wallets.find_one({"stripe_connect_account_id": account_id}, {"_id": 0})
    if not wallet:
        logger.warning(f"[CONNECT] Webhook for unknown account {account_id}")
        return {"success": False, "error": "Unknown account"}

    now = datetime.now(timezone.utc).isoformat()
    details_submitted = account_data.get("details_submitted", False)
    charges_enabled = account_data.get("charges_enabled", False)
    payouts_enabled = account_data.get("payouts_enabled", False)
    requirements = account_data.get("requirements", {})

    updates = {
        "stripe_connect_details_submitted": details_submitted,
        "stripe_connect_charges_enabled": charges_enabled,
        "stripe_connect_payouts_enabled": payouts_enabled,
        "stripe_connect_requirements": {
            "currently_due": requirements.get("currently_due", []),
            "eventually_due": requirements.get("eventually_due", []),
            "past_due": requirements.get("past_due", []),
            "disabled_reason": requirements.get("disabled_reason"),
        },
        "updated_at": now,
    }

    # Sync business_type from Stripe if present
    btype = account_data.get("business_type")
    if btype:
        updates["stripe_connect_business_type"] = btype

    old_status = wallet.get("stripe_connect_status", "not_started")

    if charges_enabled and payouts_enabled and details_submitted:
        new_status = "active"
        if not wallet.get("stripe_connect_onboarded_at"):
            updates["stripe_connect_onboarded_at"] = now
    elif details_submitted:
        new_status = "restricted"
    elif old_status == "active" and not charges_enabled:
        new_status = "disabled"
    else:
        new_status = "onboarding"

    updates["stripe_connect_status"] = new_status

    db.wallets.update_one({"wallet_id": wallet["wallet_id"]}, {"$set": updates})
    logger.info(f"[CONNECT] account.updated {account_id}: {old_status} → {new_status}")

    return {"success": True, "old_status": old_status, "new_status": new_status}


def handle_account_deauthorized(account_id: str) -> dict:
    """Process account.application.deauthorized — user disconnected NLYT."""
    wallet = db.wallets.find_one({"stripe_connect_account_id": account_id}, {"_id": 0})
    if not wallet:
        return {"success": False, "error": "Unknown account"}

    now = datetime.now(timezone.utc).isoformat()
    db.wallets.update_one(
        {"wallet_id": wallet["wallet_id"]},
        {"$set": {
            "stripe_connect_status": "disabled",
            "stripe_connect_charges_enabled": False,
            "stripe_connect_payouts_enabled": False,
            "updated_at": now,
        }}
    )
    logger.info(f"[CONNECT] Account {account_id} deauthorized")
    return {"success": True, "new_status": "disabled"}


# ─── Dev Mode ────────────────────────────────────────────

def _dev_mode_onboarding(user_id: str, business_type: str = "individual") -> dict:
    """Simulate onboarding in dev mode (no real Stripe key)."""
    wallet = db.wallets.find_one({"user_id": user_id, "wallet_type": "user"}, {"_id": 0})
    if not wallet:
        return {"success": False, "error": "Wallet introuvable"}

    now = datetime.now(timezone.utc).isoformat()
    if not wallet.get("stripe_connect_account_id"):
        db.wallets.update_one(
            {"wallet_id": wallet["wallet_id"]},
            {"$set": {
                "stripe_connect_account_id": f"acct_dev_{user_id[:8]}",
                "stripe_connect_status": "active",
                "stripe_connect_business_type": business_type,
                "stripe_connect_details_submitted": True,
                "stripe_connect_charges_enabled": True,
                "stripe_connect_payouts_enabled": True,
                "stripe_connect_country": DEFAULT_CONNECT_COUNTRY,
                "stripe_connect_created_at": now,
                "stripe_connect_onboarded_at": now,
                "updated_at": now,
            }}
        )
        logger.info(f"[CONNECT:DEV] Simulated active Connect for user {user_id}")

    return {
        "success": True,
        "connect_status": "active",
        "onboarding_url": None,
        "message": "[DEV MODE] Compte simulé comme actif",
    }
