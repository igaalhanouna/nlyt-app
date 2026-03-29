"""
Migration: Insert static VALIDATED_ASSOCIATIONS into MongoDB charity_associations collection.
Idempotent: uses upsert on association_id. Never deletes existing documents.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from database import db

STATIC_ASSOCIATIONS = [
    {
        "association_id": "assoc_croix_rouge",
        "name": "Croix-Rouge française",
        "description": "Association humanitaire française",
        "website": "https://www.croix-rouge.fr",
        "logo_url": None,
        "is_active": True,
    },
    {
        "association_id": "assoc_restos_coeur",
        "name": "Les Restos du Cœur",
        "description": "Aide alimentaire et insertion",
        "website": "https://www.restosducoeur.org",
        "logo_url": None,
        "is_active": True,
    },
    {
        "association_id": "assoc_secours_populaire",
        "name": "Secours populaire français",
        "description": "Association de solidarité",
        "website": "https://www.secourspopulaire.fr",
        "logo_url": None,
        "is_active": True,
    },
    {
        "association_id": "assoc_medecins_sans_frontieres",
        "name": "Médecins Sans Frontières",
        "description": "Association médicale humanitaire",
        "website": "https://www.msf.fr",
        "logo_url": None,
        "is_active": True,
    },
    {
        "association_id": "assoc_unicef",
        "name": "UNICEF France",
        "description": "Fonds des Nations Unies pour l'enfance",
        "website": "https://www.unicef.fr",
        "logo_url": None,
        "is_active": True,
    },
    {
        "association_id": "assoc_emmaus",
        "name": "Emmaüs France",
        "description": "Lutte contre l'exclusion",
        "website": "https://emmaus-france.org",
        "logo_url": None,
        "is_active": True,
    },
    {
        "association_id": "assoc_fondation_abbe_pierre",
        "name": "Fondation Abbé Pierre",
        "description": "Lutte contre le mal-logement",
        "website": "https://www.fondation-abbe-pierre.fr",
        "logo_url": None,
        "is_active": True,
    },
    {
        "association_id": "assoc_action_contre_faim",
        "name": "Action contre la Faim",
        "description": "Lutte contre la faim dans le monde",
        "website": "https://www.actioncontrelafaim.org",
        "logo_url": None,
        "is_active": True,
    },
]


def run_migration():
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    updated = 0
    skipped = 0

    # Ensure unique index
    db.charity_associations.create_index("association_id", unique=True)

    for assoc in STATIC_ASSOCIATIONS:
        existing = db.charity_associations.find_one(
            {"association_id": assoc["association_id"]}, {"_id": 0}
        )
        doc = {**assoc, "updated_at": now}
        if not existing:
            doc["created_at"] = now
            doc["contact_email"] = None
            db.charity_associations.insert_one(doc)
            inserted += 1
            print(f"  [INSERT] {assoc['association_id']} — {assoc['name']}")
        else:
            # Only update fields that don't exist yet (non-destructive)
            set_fields = {}
            for key in ["name", "description", "website", "is_active"]:
                if key not in existing or existing[key] is None:
                    set_fields[key] = assoc[key]
            if "contact_email" not in existing:
                set_fields["contact_email"] = None
            if "created_at" not in existing:
                set_fields["created_at"] = now
            set_fields["updated_at"] = now
            if set_fields:
                db.charity_associations.update_one(
                    {"association_id": assoc["association_id"]},
                    {"$set": set_fields},
                )
                updated += 1
                print(f"  [UPDATE] {assoc['association_id']} — enriched {list(set_fields.keys())}")
            else:
                skipped += 1
                print(f"  [SKIP]   {assoc['association_id']} — already complete")

    # Log existing documents NOT in the static list (like charity-001)
    all_ids = [a["association_id"] for a in STATIC_ASSOCIATIONS]
    orphans = list(db.charity_associations.find(
        {"association_id": {"$nin": all_ids}}, {"_id": 0, "association_id": 1, "name": 1}
    ))
    if orphans:
        print(f"\n  [INFO] {len(orphans)} document(s) existant(s) hors liste statique (conserves):")
        for o in orphans:
            print(f"    - {o['association_id']}: {o.get('name', '?')}")

    total = db.charity_associations.count_documents({})
    print(f"\nMigration terminee: {inserted} inseres, {updated} enrichis, {skipped} ignores")
    print(f"Total en base: {total} associations")
    return {"inserted": inserted, "updated": updated, "skipped": skipped, "total": total}


if __name__ == "__main__":
    print("=== Migration associations statiques -> MongoDB ===\n")
    result = run_migration()
    print(f"\nResultat: {result}")
