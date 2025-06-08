# src/auth_context/infrastructure/user_repository.py
import pymongo
from pymongo.errors import ConnectionFailure, OperationFailure
import dataclasses
from typing import List, Optional
import os

from ..domain.user import User # Import the User domain model

# Default MongoDB connection parameters for user repository
# These could be different from the activity log's if needed, or shared via a common config
DEFAULT_AUTH_MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/") # Reuse general MONGO_URI
DEFAULT_AUTH_DB_NAME = os.environ.get("AUTH_MONGO_DB_NAME", "auth_db_default") # Specific DB for auth
DEFAULT_AUTH_COLLECTION_NAME = "users"

class MongoUserRepository:
    """
    A MongoDB repository for storing and retrieving User domain objects.
    """

    def __init__(self,
                 mongo_uri: str = DEFAULT_AUTH_MONGO_URI,
                 db_name: str = DEFAULT_AUTH_DB_NAME,
                 collection_name: str = DEFAULT_AUTH_COLLECTION_NAME):
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.collection_name = collection_name

        try:
            self.client = pymongo.MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            # Create a unique index on 'username' for faster lookups and to prevent duplicates
            self.collection.create_index("username", unique=True)
            print(f"Successfully connected to MongoDB for UserRepository at {self.mongo_uri}, db '{self.db_name}', collection '{self.collection_name}'.")
        except ConnectionFailure as e:
            print(f"UserRepository Error: Could not connect to MongoDB at {self.mongo_uri}. Details: {e}")
            self.client = None; self.db = None; self.collection = None
        except OperationFailure as e: # Handle errors like index creation if DB is read-only, etc.
            print(f"UserRepository Error: MongoDB operation failed during init (e.g. index creation): {e}")
            # Depending on severity, might still allow client/db/collection to be set if connection itself is ok
            if self.client and not hasattr(self, 'collection'): # if client is ok, but collection/index failed
                 self.db = self.client[self.db_name]
                 self.collection = self.db[self.collection_name] # Allow use, but warn about index
                 print("Warning: User collection might not have username index due to previous error.")
            else:
                 self.client = None; self.db = None; self.collection = None
        except Exception as e:
            print(f"UserRepository: An unexpected error occurred during MongoDB init: {e}")
            self.client = None; self.db = None; self.collection = None

    def _ensure_connected(self) -> bool:
        if self.collection is None:
            print("UserRepository Error: MongoDB collection is not available.")
            return False
        return True

    def _to_user_domain_object(self, document: dict) -> Optional[User]:
        """Converts a MongoDB document (dict) to a User domain object."""
        if document is None:
            return None
        document.pop('_id', None) # Remove MongoDB's internal _id
        # Filter to only include fields defined in User dataclass
        valid_fields = {f.name for f in dataclasses.fields(User)}
        filtered_doc = {k: v for k, v in document.items() if k in valid_fields}
        try:
            return User(**filtered_doc)
        except TypeError as te:
            print(f"UserRepository Warning: Skipping document due to TypeError (missing fields or type mismatch): {te}. Doc: {document}")
            return None

    def add(self, user: User) -> bool:
        """Adds a new User to the MongoDB collection."""
        if not self._ensure_connected(): return False
        try:
            user_dict = dataclasses.asdict(user)
            # To use user.id as MongoDB's _id, uncomment next line. Otherwise, MongoDB generates its own.
            # user_dict['_id'] = user.id
            self.collection.insert_one(user_dict)
            print(f"User '{user.username}' (ID: {user.id}) added to repository.")
            return True
        except pymongo.errors.DuplicateKeyError: # Catch if username is not unique (if index is set)
            print(f"UserRepository Error: User with username '{user.username}' already exists.")
            return False
        except OperationFailure as e:
            print(f"UserRepository Error: MongoDB operation failed during add: {e}"); return False
        except Exception as e:
            print(f"UserRepository: Unexpected error during add: {e}"); return False

    def get_by_username(self, username: str) -> Optional[User]:
        """Retrieves a User by their username."""
        if not self._ensure_connected(): return None
        try:
            document = self.collection.find_one({"username": username})
            return self._to_user_domain_object(document)
        except OperationFailure as e:
            print(f"UserRepository Error: MongoDB operation failed during get_by_username: {e}"); return None
        except Exception as e:
            print(f"UserRepository: Unexpected error during get_by_username: {e}"); return None

    def get_by_id(self, user_id: str) -> Optional[User]:
        """Retrieves a User by their ID."""
        if not self._ensure_connected(): return None
        try:
            # If user.id is stored as MongoDB's _id, query would be:
            # document = self.collection.find_one({"_id": user_id})
            # Assuming 'id' is a separate field in the document:
            document = self.collection.find_one({"id": user_id})
            return self._to_user_domain_object(document)
        except OperationFailure as e:
            print(f"UserRepository Error: MongoDB operation failed during get_by_id: {e}"); return None
        except Exception as e:
            print(f"UserRepository: Unexpected error during get_by_id: {e}"); return None

# Example usage
if __name__ == '__main__':
    print("\n--- MongoUserRepository Demonstration ---")
    # This demo assumes MongoDB is running.
    user_repo = MongoUserRepository()

    if user_repo.collection is not None:
        # Clean up potential old test users first for idempotency
        user_repo.collection.delete_many({"username": {"$in": ["testuser@example.com", "getme@example.com"]}})
        print("Cleaned up old test users if any existed.")

        print("\n1. Adding a new user:")
        new_user = User(username="testuser@example.com", hashed_password="hashed_password_123")
        add_success = user_repo.add(new_user)
        print(f"Add user 'testuser@example.com' successful: {add_success}")

        # Try adding duplicate username
        print("\nTrying to add duplicate username:")
        add_duplicate_success = user_repo.add(User(username="testuser@example.com", hashed_password="another_hash"))
        print(f"Add duplicate user 'testuser@example.com' successful: {add_duplicate_success} (expected False if unique index works)")


        print("\n2. Getting user by username:")
        retrieved_user = user_repo.get_by_username("testuser@example.com")
        if retrieved_user:
            print(f"Found user: {retrieved_user.username}, ID: {retrieved_user.id}, Active: {retrieved_user.is_active}")
            assert retrieved_user.username == "testuser@example.com"
        else:
            print("User 'testuser@example.com' not found after add.")

        print("\n3. Getting user by ID:")
        if retrieved_user: # Use ID from the user we just retrieved
            user_by_id = user_repo.get_by_id(retrieved_user.id)
            if user_by_id:
                print(f"Found user by ID '{retrieved_user.id}': {user_by_id.username}")
                assert user_by_id.id == retrieved_user.id
            else:
                print(f"User with ID '{retrieved_user.id}' not found.")

        print("\n4. Getting non-existent user:")
        non_existent_user = user_repo.get_by_username("nosuchuser@example.com")
        print(f"Found non-existent user 'nosuchuser@example.com': {non_existent_user is not None} (expected False)")

        # Clean up test user
        if retrieved_user:
            user_repo.collection.delete_one({"id": retrieved_user.id})
            print(f"Cleaned up user: {retrieved_user.username}")
    else:
        print("\nSkipping UserRepository operations as MongoDB connection failed.")

    print("\n--- End of MongoUserRepository Demonstration ---")
