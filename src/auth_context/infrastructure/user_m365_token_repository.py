# src/auth_context/infrastructure/user_m365_token_repository.py
import pymongo
from pymongo.errors import ConnectionFailure, OperationFailure, DuplicateKeyError
from pymongo.results import UpdateResult, DeleteResult
import dataclasses
from typing import Optional
import os
from datetime import datetime, timezone # For handling datetime fields

from ..domain.user_m365_token import UserM365Token

# Use the same MongoDB URI as UserRepository or define a specific one if needed
# For this example, assuming they might share the same DB instance but different collections/DBs.
# Using AUTH_MONGO_DB_NAME for the database, and a new collection name.
DEFAULT_M365_TOKEN_MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DEFAULT_M365_TOKEN_DB_NAME = os.environ.get("AUTH_MONGO_DB_NAME", "auth_db_default") # Same DB as users
DEFAULT_M365_TOKEN_COLLECTION_NAME = "user_m365_tokens"

class MongoUserM365TokenRepository:
    """
    MongoDB repository for storing and retrieving UserM365Token domain objects.
    Assumes user_id is the primary key for these records (one M365 token set per user).
    """

    def __init__(self,
                 mongo_uri: str = DEFAULT_M365_TOKEN_MONGO_URI,
                 db_name: str = DEFAULT_M365_TOKEN_DB_NAME,
                 collection_name: str = DEFAULT_M365_TOKEN_COLLECTION_NAME):
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.collection_name = collection_name

        try:
            self.client = pymongo.MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            # Create a unique index on 'user_id' as we assume one token record per user.
            # This also makes lookups by user_id faster.
            self.collection.create_index("user_id", unique=True)
            print(f"Successfully connected to MongoDB for UserM365TokenRepository at {self.mongo_uri}, "
                  f"db '{self.db_name}', collection '{self.collection_name}'.")
        except ConnectionFailure as e:
            print(f"UserM365TokenRepository Error: Could not connect to MongoDB. Details: {e}")
            self.client = None; self.db = None; self.collection = None
        except OperationFailure as e:
            print(f"UserM365TokenRepository Error: MongoDB operation failed during init (e.g. index creation): {e}")
            if self.client and not hasattr(self, 'collection'):
                 self.db = self.client[self.db_name]
                 self.collection = self.db[self.collection_name]
                 print("Warning: UserM365Token collection might not have user_id index due to error.")
            else:
                 self.client = None; self.db = None; self.collection = None
        except Exception as e:
            print(f"UserM365TokenRepository: Unexpected error during MongoDB init: {e}")
            self.client = None; self.db = None; self.collection = None

    def _ensure_connected(self) -> bool:
        if self.collection is None:
            print("UserM365TokenRepository Error: MongoDB collection is not available.")
            return False
        return True

    def _to_domain_object(self, document: dict) -> Optional[UserM365Token]:
        """Converts a MongoDB document (dict) to a UserM365Token domain object."""
        if document is None: return None
        document.pop('_id', None)

        # Convert ISO string dates from DB back to datetime objects if necessary
        # Pymongo typically handles datetime objects correctly, but if they were stored as strings:
        # for field_name in ['access_token_expires_at', 'created_at', 'updated_at']:
        #     if field_name in document and isinstance(document[field_name], str):
        #         try:
        #             document[field_name] = datetime.fromisoformat(document[field_name].replace('Z', '+00:00'))
        #         except ValueError: # Handle cases where it might not be a valid ISO string or already datetime
        #             pass

        valid_fields = {f.name for f in dataclasses.fields(UserM365Token)}
        filtered_doc = {k: v for k, v in document.items() if k in valid_fields}
        try:
            return UserM365Token(**filtered_doc)
        except TypeError as te:
            print(f"UserM365TokenRepository Warning: Error converting document to domain object: {te}. Doc: {document}")
            return None

    def save(self, token_data: UserM365Token) -> bool:
        """Inserts or updates token data for a user_id (upsert)."""
        if not self._ensure_connected(): return False

        # Ensure `updated_at` is current
        token_data.updated_at = datetime.now(timezone.utc)
        token_dict = dataclasses.asdict(token_data)

        # Datetime objects are stored as BSON Date type in MongoDB by default, which is good.

        try:
            result: UpdateResult = self.collection.update_one(
                {"user_id": token_data.user_id},
                {"$set": token_dict},
                upsert=True
            )
            if result.upserted_id or result.modified_count > 0 or result.matched_count > 0:
                print(f"UserM365Token for user_id '{token_data.user_id}' saved/updated successfully.")
                return True
            # matched_count > 0 but modified_count == 0 means data was the same, still success.
            print(f"UserM365Token for user_id '{token_data.user_id}' - no changes made or not found for update (and upsert didn't happen). Matched: {result.matched_count}")
            return False # Or True if matched_count > 0 is considered success
        except OperationFailure as e:
            print(f"UserM365TokenRepository Error: MongoDB operation failed during save: {e}"); return False
        except Exception as e:
            print(f"UserM365TokenRepository: Unexpected error during save: {e}"); return False

    def get_by_user_id(self, user_id: str) -> Optional[UserM365Token]:
        """Retrieves token data for a user."""
        if not self._ensure_connected(): return None
        try:
            document = self.collection.find_one({"user_id": user_id})
            return self._to_domain_object(document)
        except OperationFailure as e:
            print(f"UserM365TokenRepository Error: MongoDB operation failed during get_by_user_id: {e}"); return None
        except Exception as e:
            print(f"UserM365TokenRepository: Unexpected error during get_by_user_id: {e}"); return None

    def delete_by_user_id(self, user_id: str) -> bool:
        """Deletes token data for a user."""
        if not self._ensure_connected(): return False
        try:
            result: DeleteResult = self.collection.delete_one({"user_id": user_id})
            if result.deleted_count > 0:
                print(f"UserM365Token for user_id '{user_id}' deleted successfully.")
                return True
            print(f"UserM365Token for user_id '{user_id}' not found for deletion.")
            return False
        except OperationFailure as e:
            print(f"UserM365TokenRepository Error: MongoDB operation failed during delete: {e}"); return False
        except Exception as e:
            print(f"UserM365TokenRepository: Unexpected error during delete: {e}"); return False

# Example Usage
if __name__ == '__main__':
    print("\n--- MongoUserM365TokenRepository Demonstration ---")
    # Requires MongoDB to be running and accessible.
    token_repo = MongoUserM365TokenRepository()

    if token_repo.collection is not None:
        test_user_id = "demo_user_for_m365token"

        # Clean up before test
        token_repo.delete_by_user_id(test_user_id)
        print(f"Attempted pre-test cleanup for user_id: {test_user_id}")

        print("\n1. Saving new token data:")
        token_obj1 = UserM365Token(
            user_id=test_user_id,
            encrypted_refresh_token="encrypted_example_refresh_token_v1",
            access_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes=["Mail.Read", "User.Read", "offline_access"]
        )
        save_success1 = token_repo.save(token_obj1)
        print(f"Save new token successful: {save_success1}")
        assert save_success1

        print("\n2. Getting token data by user_id:")
        retrieved_token1 = token_repo.get_by_user_id(test_user_id)
        if retrieved_token1:
            print(f"Retrieved token for user '{retrieved_token1.user_id}', expires at: {retrieved_token1.access_token_expires_at}")
            assert retrieved_token1.encrypted_refresh_token == "encrypted_example_refresh_token_v1"
        else:
            print(f"Token data for user '{test_user_id}' not found after save.")

        print("\n3. Updating token data (upsert should modify):")
        # Simulate token refresh - new encrypted refresh token and new expiry
        token_obj2 = UserM365Token(
            user_id=test_user_id,
            encrypted_refresh_token="encrypted_example_refresh_token_v2_updated",
            access_token_expires_at=datetime.now(timezone.utc) + timedelta(minutes=30), # Shorter expiry for test
            scopes=["Mail.Read", "User.Read", "offline_access", "Calendars.Read"], # Added a scope
            id_token_claims={"oid": "m365_user_guid"} # Added some claims
        )
        save_success2 = token_repo.save(token_obj2) # This will use the same user_id, so it's an update
        print(f"Update token successful: {save_success2}")
        assert save_success2

        retrieved_token2 = token_repo.get_by_user_id(test_user_id)
        if retrieved_token2:
            print(f"Retrieved updated token for user '{retrieved_token2.user_id}', expires at: {retrieved_token2.access_token_expires_at}")
            assert retrieved_token2.encrypted_refresh_token == "encrypted_example_refresh_token_v2_updated"
            assert "Calendars.Read" in retrieved_token2.scopes
            assert retrieved_token2.id_token_claims.get("oid") == "m365_user_guid"
        else:
            print(f"Token data for user '{test_user_id}' not found after update.")

        print("\n4. Deleting token data:")
        delete_success = token_repo.delete_by_user_id(test_user_id)
        print(f"Delete token successful: {delete_success}")
        assert delete_success

        retrieved_after_delete = token_repo.get_by_user_id(test_user_id)
        print(f"Token data found after delete: {retrieved_after_delete is not None} (expected False)")
        assert retrieved_after_delete is None
    else:
        print("\nSkipping UserM365TokenRepository operations as MongoDB connection failed.")

    print("\n--- End of MongoUserM365TokenRepository Demonstration ---")
