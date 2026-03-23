"""
Charity Associations - Liste des associations validées pour les dons caritatifs
"""
from fastapi import APIRouter, HTTPException
import os
import uuid
from datetime import datetime, timezone

from database import db
router = APIRouter()


# Liste statique des associations validées pour le MVP
# En production, cela pourrait être géré via une collection MongoDB avec admin panel
VALIDATED_ASSOCIATIONS = [
    {
        "association_id": "assoc_croix_rouge",
        "name": "Croix-Rouge française",
        "description": "Association humanitaire française",
        "website": "https://www.croix-rouge.fr",
        "logo_url": None,
        "is_active": True
    },
    {
        "association_id": "assoc_restos_coeur",
        "name": "Les Restos du Cœur",
        "description": "Aide alimentaire et insertion",
        "website": "https://www.restosducoeur.org",
        "logo_url": None,
        "is_active": True
    },
    {
        "association_id": "assoc_secours_populaire",
        "name": "Secours populaire français",
        "description": "Association de solidarité",
        "website": "https://www.secourspopulaire.fr",
        "logo_url": None,
        "is_active": True
    },
    {
        "association_id": "assoc_medecins_sans_frontieres",
        "name": "Médecins Sans Frontières",
        "description": "Association médicale humanitaire",
        "website": "https://www.msf.fr",
        "logo_url": None,
        "is_active": True
    },
    {
        "association_id": "assoc_unicef",
        "name": "UNICEF France",
        "description": "Fonds des Nations Unies pour l'enfance",
        "website": "https://www.unicef.fr",
        "logo_url": None,
        "is_active": True
    },
    {
        "association_id": "assoc_emmaus",
        "name": "Emmaüs France",
        "description": "Lutte contre l'exclusion",
        "website": "https://emmaus-france.org",
        "logo_url": None,
        "is_active": True
    },
    {
        "association_id": "assoc_fondation_abbe_pierre",
        "name": "Fondation Abbé Pierre",
        "description": "Lutte contre le mal-logement",
        "website": "https://www.fondation-abbe-pierre.fr",
        "logo_url": None,
        "is_active": True
    },
    {
        "association_id": "assoc_action_contre_faim",
        "name": "Action contre la Faim",
        "description": "Lutte contre la faim dans le monde",
        "website": "https://www.actioncontrelafaim.org",
        "logo_url": None,
        "is_active": True
    }
]


@router.get("/")
async def list_charity_associations():
    """
    Get list of validated charity associations.
    Only active associations are returned.
    """
    active_associations = [a for a in VALIDATED_ASSOCIATIONS if a.get("is_active", True)]
    return {
        "associations": active_associations,
        "count": len(active_associations)
    }


@router.get("/{association_id}")
async def get_charity_association(association_id: str):
    """
    Get a specific charity association by ID.
    """
    for assoc in VALIDATED_ASSOCIATIONS:
        if assoc["association_id"] == association_id and assoc.get("is_active", True):
            return assoc
    
    raise HTTPException(status_code=404, detail="Association non trouvée")


def is_valid_association(association_id: str) -> bool:
    """
    Check if an association ID is valid and active.
    Used for validation when saving user preferences.
    """
    if not association_id:
        return True  # No association is valid (optional field)
    
    for assoc in VALIDATED_ASSOCIATIONS:
        if assoc["association_id"] == association_id and assoc.get("is_active", True):
            return True
    return False


def get_association_name(association_id: str) -> str:
    """
    Get association name by ID.
    """
    for assoc in VALIDATED_ASSOCIATIONS:
        if assoc["association_id"] == association_id:
            return assoc["name"]
    return None
