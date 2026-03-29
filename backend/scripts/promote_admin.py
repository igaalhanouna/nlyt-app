"""Promote a user to admin role."""
import sys
sys.path.insert(0, '/app/backend')

import os
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

from database import db

ADMIN_EMAIL = "testuser_audit@nlyt.app"

result = db.users.update_one(
    {"email": ADMIN_EMAIL},
    {"$set": {"role": "admin"}}
)

if result.modified_count:
    print(f"User {ADMIN_EMAIL} promoted to admin.")
else:
    user = db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0, "role": 1})
    if user and user.get("role") == "admin":
        print(f"User {ADMIN_EMAIL} is already admin.")
    else:
        print(f"User {ADMIN_EMAIL} not found!")
