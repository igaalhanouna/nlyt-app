import os
import uuid
import logging
from pymongo import MongoClient
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend directory
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

from utils.date_utils import now_utc

logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

class WorkspaceService:
    @staticmethod
    def create_default_workspace(user_id: str, first_name: str, last_name: str) -> dict:
        """
        Create a default workspace for a new user.
        This is called automatically during signup.
        """
        workspace_id = str(uuid.uuid4())
        workspace_name = f"Espace de {first_name} {last_name}"
        
        workspace_doc = {
            "workspace_id": workspace_id,
            "name": workspace_name,
            "description": "Espace de travail personnel",
            "owner_id": user_id,
            "is_default": True,
            "created_at": now_utc().isoformat(),
            "updated_at": now_utc().isoformat()
        }
        
        try:
            db.workspaces.insert_one(workspace_doc)
            logger.info(f"[WORKSPACE] ✅ Default workspace created for user {user_id}: {workspace_id}")
        except Exception as e:
            logger.error(f"[WORKSPACE] ❌ Failed to create default workspace: {str(e)}")
            return None
        
        # Create membership
        membership = {
            "membership_id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "user_id": user_id,
            "role": "admin",
            "joined_at": now_utc().isoformat()
        }
        
        try:
            db.workspace_memberships.insert_one(membership)
            logger.info(f"[WORKSPACE] ✅ Membership created for user {user_id} in workspace {workspace_id}")
        except Exception as e:
            logger.error(f"[WORKSPACE] ❌ Failed to create membership: {str(e)}")
        
        return {
            "workspace_id": workspace_id,
            "name": workspace_name,
            "description": "Espace de travail personnel",
            "owner_id": user_id,
            "is_default": True
        }
    
    @staticmethod
    def ensure_user_has_workspace(user_id: str, first_name: str, last_name: str) -> dict:
        """
        Ensure a user has at least one workspace.
        If not, create a default one.
        Used for existing users who don't have a workspace.
        """
        # Check if user has any workspace membership
        membership = db.workspace_memberships.find_one({"user_id": user_id}, {"_id": 0})
        
        if membership:
            # User already has a workspace
            workspace = db.workspaces.find_one(
                {"workspace_id": membership['workspace_id']}, 
                {"_id": 0}
            )
            if workspace:
                return workspace
        
        # No workspace found, create default one
        logger.info(f"[WORKSPACE] User {user_id} has no workspace, creating default...")
        return WorkspaceService.create_default_workspace(user_id, first_name, last_name)
    
    @staticmethod
    def get_user_default_workspace(user_id: str) -> dict:
        """
        Get the user's default workspace, or first available workspace.
        """
        # First try to find a default workspace
        membership = db.workspace_memberships.find_one({"user_id": user_id}, {"_id": 0})
        
        if not membership:
            return None
        
        workspace = db.workspaces.find_one(
            {"workspace_id": membership['workspace_id']}, 
            {"_id": 0}
        )
        
        return workspace
