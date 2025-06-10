# src/auth_context/infrastructure/user_google_token_repository.py
import pymongo
from pymongo.errors import ConnectionFailure, OperationFailure, DuplicateKeyError
from pymongo.results import UpdateResult, DeleteResult
import dataclasses
from typing import Optional
import os
from datetime import datetime, timezone # For handling datetime fields

from ..domain.user_google_token import UserGoogleToken # Import the domain model

# Configuration for MongoDB connection
# Reusing AUTH_MONGO_DB_NAME for the database, but a new collection name.
DEFAULT_GOOGLE_TOKEN_MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DEFAULT_GOOGLE_TOKEN_DB_NAME = os.environ.get("AUTH_MONGO_DB_NAME", "auth_db_default")
DEFAULT_GOOGLE_TOKEN_COLLECTION_NAME = "user_google_tokens"

class MongoUserGoogleTokenRepository:
    """
    MongoDB repository for storing and retrieving UserGoogleToken domain objects.
    Assumes user_id is the primary key for these records (one Google token set per user).
    """

    def __init__(self,
                 mongo_uri: str = DEFAULT_GOOGLE_TOKEN_MONGO_URI,
                 db_name: str = DEFAULT_GOOGLE_TOKEN_DB_NAME,
                 collection_name: str = DEFAULT_GOOGLE_TOKEN_COLLECTION_NAME):
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.collection_name = collection_name
        self.client: Optional[pymongo.MongoClient] = None
        self.db: Optional[pymongo.database.Database] = None
        self.collection: Optional[pymongo.collection.Collection] = None

        try:
            self.client = pymongo.MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            # Create a unique index on 'user_id'
            self.collection.create_index("user_id", unique=True)
            print(f"Successfully connected to MongoDB for UserGoogleTokenRepository at {self.mongo_uri}, "
                  f"db '{self.db_name}', collection '{self.collection_name}'.")
        except ConnectionFailure as e:
            print(f"UserGoogleTokenRepository Error: Could not connect to MongoDB. Details: {e}")
        except OperationFailure as e: # Handles errors like index creation if DB is read-only, etc.
            print(f"UserGoogleTokenRepository Error: MongoDB operation failed during init (e.g. index creation): {e}")
            if self.client and self.db and not hasattr(self, 'collection'): # if client/db ok, but collection/index failed
                 self.collection = self.db[self.collection_name] # Allow use, but warn
                 print("Warning: UserGoogleToken collection might not have user_id index due to error.")
        except Exception as e: # Catch-all for other unexpected errors during init
            print(f"UserGoogleTokenRepository: Unexpected error during MongoDB init: {e}")

    def _ensure_connected(self) -> bool:
        if self.collection is None:
            print("UserGoogleTokenRepository Error: MongoDB collection is not available (initialization may have failed).")
            return False
        return True

    def _to_domain_object(self, document: dict) -> Optional[UserGoogleToken]:
        """Converts a MongoDB document (dict) to a UserGoogleToken domain object."""
        if document is None: return None
        document.pop('_id', None)

        # Ensure datetime fields are actual datetime objects (Pymongo usually handles this well)
        # This is more for robustness if data was somehow inserted as strings.
        for field_name in ['access_token_expires_at', 'created_at', 'updated_at']:
            if field_name in document and isinstance(document[field_name], str):
                try:
                    # Attempt to parse ISO format string back to datetime
                    dt_val = datetime.fromisoformat(document[field_name].replace('Z', '+00:00'))
                    document[field_name] = dt_val.astimezone(timezone.utc) if dt_val.tzinfo is None else dt_val
                except ValueError:
                    print(f"UserGoogleTokenRepository Warning: Could not parse date string '{document[field_name]}' for field '{field_name}'.")
                    # Decide handling: set to None, raise error, or leave as string (might fail dataclass init)
                    document[field_name] = None

        valid_fields = {f.name for f in dataclasses.fields(UserGoogleToken)}
        filtered_doc = {k: v for k, v in document.items() if k in valid_fields}
        try:
            return UserGoogleToken(**filtered_doc)
        except TypeError as te:
            print(f"UserGoogleTokenRepository Warning: Error converting document to UserGoogleToken: {te}. Doc: {document}")
            return None

    def save(self, token_data: UserGoogleToken) -> bool:
        """Inserts or updates token data for a user_id (upsert)."""
        if not self._ensure_connected(): return False

        token_data.updated_at = datetime.now(timezone.utc) # Ensure updated_at is current
        # Convert dataclass to dict. Datetime objects are stored as BSON Date by default.
        token_dict = dataclasses.asdict(token_data)

        try:
            result: UpdateResult = self.collection.update_one(
                {"user_id": token_data.user_id},
                {"$set": token_dict},
                upsert=True
            )
            # Check if operation was successful (document inserted, updated, or matched existing identical)
            if result.upserted_id or result.modified_count > 0 or result.matched_count > 0:
                print(f"UserGoogleToken for user_id '{token_data.user_id}' saved/updated successfully.")
                return True
            # This case (matched_count > 0 but modified_count == 0 and no upserted_id) means the
            # exact same document was already there. Considered a success for 'save'.
            print(f"UserGoogleToken for user_id '{token_data.user_id}' - data was identical, no changes made by DB.")
            return True
        except DuplicateKeyError: # Should not happen with upsert logic based on user_id if index is correct
             print(f"UserGoogleTokenRepository Error: Duplicate key error for user_id '{token_data.user_id}' during save (should be handled by upsert).")
             return False
        except OperationFailure as e:
            print(f"UserGoogleTokenRepository Error: MongoDB operation failed during save: {e}"); return False
        except Exception as e:
            print(f"UserGoogleTokenRepository: Unexpected error during save: {e}"); return False

    def get_by_user_id(self, user_id: str) -> Optional[UserGoogleToken]:
        """Retrieves token data for a user."""
        if not self._ensure_connected(): return None
        try:
            document = self.collection.find_one({"user_id": user_id})
            return self._to_domain_object(document)
        except OperationFailure as e:
            print(f"UserGoogleTokenRepository Error: MongoDB operation failed during get_by_user_id: {e}"); return None
        except Exception as e:
            print(f"UserGoogleTokenRepository: Unexpected error during get_by_user_id: {e}"); return None

    def delete_by_user_id(self, user_id: str) -> bool:
        """Deletes token data for a user."""
        if not self._ensure_connected(): return False
        try:
            result: DeleteResult = self.collection.delete_one({"user_id": user_id})
            if result.deleted_count > 0:
                print(f"UserGoogleToken for user_id '{user_id}' deleted successfully.")
                return True
            print(f"UserGoogleToken for user_id '{user_id}' not found for deletion.")
            return False # No document was deleted, but operation itself didn't fail
        except OperationFailure as e:
            print(f"UserGoogleTokenRepository Error: MongoDB operation failed during delete: {e}"); return False
        except Exception as e:
            print(f"UserGoogleTokenRepository: Unexpected error during delete: {e}"); return False

# Example Usage
if __name__ == '__main__':
    print("\n--- MongoUserGoogleTokenRepository Demonstration ---")
    # This demo requires MongoDB to be running and accessible.
    # Ensure GOOGLE_TOKEN_MONGO_URI and GOOGLE_TOKEN_DB_NAME env vars are set if defaults are not used.
    token_repo = MongoUserGoogleTokenRepository()

    if token_repo.collection is not None:
        test_user_id_google = "demo_user_for_googletk"

        token_repo.delete_by_user_id(test_user_id_google) # Pre-cleanup
        print(f"Attempted pre-test cleanup for user_id: {test_user_id_google}")

        print("\n1. Saving new Google token data:")
        token1 = UserGoogleToken(
            user_id=test_user_id_google,
            encrypted_refresh_token="encrypted_google_rt_v1",
            access_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes=["email", "profile"]
        )
        save1_ok = token_repo.save(token1)
        print(f"Save new token success: {save1_ok}")
        assert save1_ok

        print("\n2. Getting token data:")
        retrieved1 = token_repo.get_by_user_id(test_user_id_google)
        if retrieved1:
            print(f"Retrieved: User {retrieved1.user_id}, Scopes: {retrieved1.scopes}, Expires: {retrieved1.access_token_expires_at}")
            assert retrieved1.encrypted_refresh_token == "encrypted_google_rt_v1"
        else:
            print(f"Token for user {test_user_id_google} not found after save.")

        print("\n3. Updating token data (save with same user_id):")
        token2 = UserGoogleToken(
            user_id=test_user_id_google,
            encrypted_refresh_token="encrypted_google_rt_v2_updated",
            access_token_expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            scopes=["email", "profile", "https://www.googleapis.com/auth/gmail.readonly"],
            id_token_claims={"sub": "google_user_123", "email_verified": True}
        )
        # For update, created_at from original document should ideally be preserved if not re-read first.
        # The current save method will overwrite created_at if token2 is a new instance.
        # A true update might fetch, modify, then save. Here, save is an upsert.
        if retrieved1: # Simulate preserving created_at for an update
            token2.created_at = retrieved1.created_at

        save2_ok = token_repo.save(token2)
        print(f"Update token success: {save2_ok}")
        assert save2_ok

        retrieved2 = token_repo.get_by_user_id(test_user_id_google)
        if retrieved2:
            print(f"Retrieved updated: User {retrieved2.user_id}, Scopes: {retrieved2.scopes}, RT: {retrieved2.encrypted_refresh_token}")
            assert retrieved2.encrypted_refresh_token == "encrypted_google_rt_v2_updated"
            assert "https://www.googleapis.com/auth/gmail.readonly" in retrieved2.scopes
            if retrieved1: assert retrieved2.created_at == retrieved1.created_at # Check created_at preserved if handled
        else:
            print(f"Token for user {test_user_id_google} not found after update.")

        print("\n4. Deleting token data:")
        delete_ok = token_repo.delete_by_user_id(test_user_id_google)
        print(f"Delete token success: {delete_ok}")
        assert delete_ok

        retrieved_after_delete = token_repo.get_by_user_id(test_user_id_google)
        print(f"Token found after delete: {retrieved_after_delete is not None} (expected False)")
        assert retrieved_after_delete is None
    else:
        print("\nSkipping MongoUserGoogleTokenRepository demo: MongoDB collection not available.")

    print("\n--- End of MongoUserGoogleTokenRepository Demonstration ---")

```
