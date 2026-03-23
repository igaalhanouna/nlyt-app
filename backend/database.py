"""
Centralized MongoDB connection — single MongoClient for the entire application.

Usage in any router or service:
    from database import db
"""
import os
from pymongo import MongoClient

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]
