"""
Charity Associations — Source unique MongoDB avec fallback statique (Phase 1).

Phase 1 : MongoDB est la source principale. Le fallback statique est conservé
           en lecture seule pour sécurité. Il sera supprimé en Phase 2.
Phase 2 : Suppression de VALIDATED_ASSOCIATIONS après validation en production.
"""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional
from database import db
from middleware.auth_middleware import get_current_user
from rate_limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)


# ─── Fallback statique (Phase 1 — lecture seule, sera supprimé en Phase 2) ────

VALIDATED_ASSOCIATIONS = [
    {"association_id": "assoc_croix_rouge", "name": "Croix-Rouge française", "description": "Association humanitaire française", "website": "https://www.croix-rouge.fr", "logo_url": None, "is_active": True},
    {"association_id": "assoc_restos_coeur", "name": "Les Restos du Cœur", "description": "Aide alimentaire et insertion", "website": "https://www.restosducoeur.org", "logo_url": None, "is_active": True},
    {"association_id": "assoc_secours_populaire", "name": "Secours populaire français", "description": "Association de solidarité", "website": "https://www.secourspopulaire.fr", "logo_url": None, "is_active": True},
    {"association_id": "assoc_medecins_sans_frontieres", "name": "Médecins Sans Frontières", "description": "Association médicale humanitaire", "website": "https://www.msf.fr", "logo_url": None, "is_active": True},
    {"association_id": "assoc_unicef", "name": "UNICEF France", "description": "Fonds des Nations Unies pour l'enfance", "website": "https://www.unicef.fr", "logo_url": None, "is_active": True},
    {"association_id": "assoc_emmaus", "name": "Emmaüs France", "description": "Lutte contre l'exclusion", "website": "https://emmaus-france.org", "logo_url": None, "is_active": True},
    {"association_id": "assoc_fondation_abbe_pierre", "name": "Fondation Abbé Pierre", "description": "Lutte contre le mal-logement", "website": "https://www.fondation-abbe-pierre.fr", "logo_url": None, "is_active": True},
    {"association_id": "assoc_action_contre_faim", "name": "Action contre la Faim", "description": "Lutte contre la faim dans le monde", "website": "https://www.actioncontrelafaim.org", "logo_url": None, "is_active": True},
]

_STATIC_BY_ID = {a["association_id"]: a for a in VALIDATED_ASSOCIATIONS}


# ─── Helper functions (used by other modules) ────────────────────

def is_valid_association(association_id: str) -> bool:
    """Check if an association ID is valid and active."""
    if not association_id:
        return True
    doc = db.charity_associations.find_one(
        {"association_id": association_id, "is_active": True}, {"_id": 0, "association_id": 1}
    )
    if doc:
        return True
    # Phase 1 fallback
    return association_id in _STATIC_BY_ID and _STATIC_BY_ID[association_id].get("is_active", True)


def get_association_name(association_id: str) -> str:
    """Get association name by ID."""
    if not association_id:
        return None
    doc = db.charity_associations.find_one(
        {"association_id": association_id}, {"_id": 0, "name": 1}
    )
    if doc:
        return doc.get("name")
    # Phase 1 fallback
    static = _STATIC_BY_ID.get(association_id)
    return static["name"] if static else None


# ─── Public API (same contract as before) ────────────────────────

@router.get("/")
async def list_charity_associations():
    """Get list of active charity associations. Same response format."""
    associations = list(db.charity_associations.find(
        {"is_active": True},
        {"_id": 0, "association_id": 1, "name": 1, "description": 1, "website": 1, "logo_url": 1, "is_active": 1}
    ))
    if not associations:
        # Phase 1 fallback: if MongoDB is empty, serve static list
        logger.warning("[ASSOCIATIONS] MongoDB empty, falling back to static list")
        associations = [a for a in VALIDATED_ASSOCIATIONS if a.get("is_active", True)]
    return {"associations": associations, "count": len(associations)}


@router.get("/{association_id}")
async def get_charity_association(association_id: str):
    """Get a specific charity association by ID."""
    doc = db.charity_associations.find_one(
        {"association_id": association_id, "is_active": True},
        {"_id": 0, "association_id": 1, "name": 1, "description": 1, "website": 1, "logo_url": 1, "is_active": 1}
    )
    if doc:
        return doc
    # Phase 1 fallback
    static = _STATIC_BY_ID.get(association_id)
    if static and static.get("is_active", True):
        return static
    raise HTTPException(status_code=404, detail="Association non trouvée")


# ─── Admin CRUD ──────────────────────────────────────────────────

class AssociationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: str = Field(default="", max_length=500)
    website: Optional[str] = None
    contact_email: Optional[str] = None
    contact_first_name: Optional[str] = None
    contact_last_name: Optional[str] = None
    contact_phone: Optional[str] = None


class AssociationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, max_length=500)
    website: Optional[str] = None
    contact_email: Optional[str] = None
    contact_first_name: Optional[str] = None
    contact_last_name: Optional[str] = None
    contact_phone: Optional[str] = None


@router.get("/admin/list")
@limiter.limit("30/minute")
async def admin_list_associations(request: Request):
    """Admin: list ALL associations (including inactive)."""
    await get_current_user(request)
    associations = list(db.charity_associations.find(
        {},
        {"_id": 0}
    ).sort("name", 1))
    return {"associations": associations, "count": len(associations)}


@router.post("/admin/create")
@limiter.limit("10/minute")
async def admin_create_association(request: Request, body: AssociationCreate):
    """Admin: create a new association."""
    user = await get_current_user(request)
    now = datetime.now(timezone.utc).isoformat()

    # Generate a slug-based ID
    slug = body.name.lower().strip()
    slug = slug.replace(" ", "_").replace("'", "").replace("'", "")
    for ch in "àâä":
        slug = slug.replace(ch, "a")
    for ch in "éèêë":
        slug = slug.replace(ch, "e")
    for ch in "îï":
        slug = slug.replace(ch, "i")
    for ch in "ôö":
        slug = slug.replace(ch, "o")
    for ch in "ùûü":
        slug = slug.replace(ch, "u")
    for ch in "ç":
        slug = slug.replace(ch, "c")
    slug = "".join(c for c in slug if c.isalnum() or c == "_")
    association_id = f"assoc_{slug}"

    # Check uniqueness
    if db.charity_associations.find_one({"association_id": association_id}):
        raise HTTPException(status_code=409, detail=f"Une association avec cet ID existe déjà: {association_id}")

    doc = {
        "association_id": association_id,
        "name": body.name.strip(),
        "description": body.description.strip() if body.description else "",
        "website": body.website.strip() if body.website else None,
        "logo_url": None,
        "contact_email": body.contact_email.strip() if body.contact_email else None,
        "contact_first_name": body.contact_first_name.strip() if body.contact_first_name else None,
        "contact_last_name": body.contact_last_name.strip() if body.contact_last_name else None,
        "contact_phone": body.contact_phone.strip() if body.contact_phone else None,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    db.charity_associations.insert_one(doc)
    doc.pop("_id", None)

    logger.info(f"[ADMIN] Association created: {association_id} by {user.get('email')}")
    return doc


@router.put("/admin/{association_id}")
@limiter.limit("10/minute")
async def admin_update_association(request: Request, association_id: str, body: AssociationUpdate):
    """Admin: update an association."""
    user = await get_current_user(request)

    existing = db.charity_associations.find_one({"association_id": association_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Association non trouvée")

    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if body.name is not None:
        update_fields["name"] = body.name.strip()
    if body.description is not None:
        update_fields["description"] = body.description.strip()
    if body.website is not None:
        update_fields["website"] = body.website.strip() if body.website else None
    if body.contact_email is not None:
        update_fields["contact_email"] = body.contact_email.strip() if body.contact_email else None
    if body.contact_first_name is not None:
        update_fields["contact_first_name"] = body.contact_first_name.strip() if body.contact_first_name else None
    if body.contact_last_name is not None:
        update_fields["contact_last_name"] = body.contact_last_name.strip() if body.contact_last_name else None
    if body.contact_phone is not None:
        update_fields["contact_phone"] = body.contact_phone.strip() if body.contact_phone else None

    db.charity_associations.update_one(
        {"association_id": association_id},
        {"$set": update_fields}
    )

    updated = db.charity_associations.find_one({"association_id": association_id}, {"_id": 0})
    logger.info(f"[ADMIN] Association updated: {association_id} by {user.get('email')}")
    return updated


@router.patch("/admin/{association_id}/toggle")
@limiter.limit("10/minute")
async def admin_toggle_association(request: Request, association_id: str):
    """Admin: activate/deactivate an association."""
    user = await get_current_user(request)

    existing = db.charity_associations.find_one({"association_id": association_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Association non trouvée")

    new_status = not existing.get("is_active", True)
    db.charity_associations.update_one(
        {"association_id": association_id},
        {"$set": {"is_active": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    action = "activée" if new_status else "désactivée"
    logger.info(f"[ADMIN] Association {association_id} {action} by {user.get('email')}")
    return {"association_id": association_id, "is_active": new_status, "message": f"Association {action}"}
