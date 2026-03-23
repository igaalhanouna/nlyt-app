from fastapi import APIRouter, HTTPException, Request, Depends
import os
import uuid
import sys
sys.path.append('/app/backend')
from models.schemas import WorkspaceCreate, WorkspaceResponse, WorkspaceUpdate
from middleware.auth_middleware import get_current_user
from utils.date_utils import now_utc

from database import db
router = APIRouter()


@router.post("/", response_model=WorkspaceResponse)
async def create_workspace(workspace: WorkspaceCreate, request: Request):
    user = await get_current_user(request)
    
    workspace_id = str(uuid.uuid4())
    workspace_doc = {
        "workspace_id": workspace_id,
        "name": workspace.name,
        "description": workspace.description,
        "owner_id": user['user_id'],
        "created_at": now_utc().isoformat(),
        "updated_at": now_utc().isoformat()
    }
    
    db.workspaces.insert_one(workspace_doc)
    
    membership = {
        "membership_id": str(uuid.uuid4()),
        "workspace_id": workspace_id,
        "user_id": user['user_id'],
        "role": "admin",
        "joined_at": now_utc().isoformat()
    }
    db.workspace_memberships.insert_one(membership)
    
    return WorkspaceResponse(
        workspace_id=workspace_id,
        name=workspace.name,
        description=workspace.description,
        owner_id=user['user_id'],
        created_at=workspace_doc['created_at']
    )

@router.get("/")
async def list_workspaces(request: Request):
    user = await get_current_user(request)
    
    memberships = list(db.workspace_memberships.find({"user_id": user['user_id']}, {"_id": 0}))
    workspace_ids = [m['workspace_id'] for m in memberships]
    
    workspaces = list(db.workspaces.find({"workspace_id": {"$in": workspace_ids}}, {"_id": 0}))
    
    return {"workspaces": workspaces}

@router.get("/{workspace_id}")
async def get_workspace(workspace_id: str, request: Request):
    user = await get_current_user(request)
    
    membership = db.workspace_memberships.find_one({
        "workspace_id": workspace_id,
        "user_id": user['user_id']
    }, {"_id": 0})
    
    if not membership:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    workspace = db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace introuvable")
    
    return workspace


@router.put("/{workspace_id}")
async def update_workspace(workspace_id: str, data: WorkspaceUpdate, request: Request):
    user = await get_current_user(request)

    membership = db.workspace_memberships.find_one(
        {"workspace_id": workspace_id, "user_id": user["user_id"]},
        {"_id": 0},
    )
    if not membership or membership.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Seul l'admin peut modifier le workspace")

    updates = {"updated_at": now_utc().isoformat()}
    if data.name is not None:
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Le nom ne peut pas être vide")
        updates["name"] = name
    if data.description is not None:
        updates["description"] = data.description.strip()

    db.workspaces.update_one({"workspace_id": workspace_id}, {"$set": updates})

    workspace = db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
    return workspace
