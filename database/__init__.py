"""
Database module for Co Penny.
MIGRATION: MongoDB → Firebase Firestore

All code that imports `get_mongodb_service` continues to work unchanged.
FirestoreService is exported as both its own name and as MongoDBService (legacy alias)
so that any `from database.mongodb_service import MongoDBService` imports also resolve.
"""
# Primary service is now Firestore
from .firestore_service import FirestoreService, get_firestore_service

# Legacy aliases for backward compatibility
MongoDBService = FirestoreService
def get_mongodb_service():
    return get_firestore_service()

__all__ = ["FirestoreService", "get_firestore_service", "MongoDBService", "get_mongodb_service"]
