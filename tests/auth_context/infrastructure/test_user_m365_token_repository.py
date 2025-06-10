# tests/auth_context/infrastructure/test_user_m365_token_repository.py
import unittest
from unittest.mock import patch, MagicMock
import os
import importlib
from datetime import datetime, timezone, timedelta
import pymongo # For IndexModel and error types

# Import the class to be tested
from src.auth_context.infrastructure import user_m365_token_repository # Import module
from src.auth_context.domain.user_m365_token import UserM365Token

class TestMongoUserM365TokenRepository(unittest.TestCase):

    MOCK_ENV_VARS = {
        "MONGO_URI": "mongodb://fakelocal:1234/testdb", # Ensure URI includes a DB for parsing if AUTH_MONGO_DB_NAME is not set
        "AUTH_MONGO_DB_NAME": "test_auth_db_for_tokens"
    }

    @patch.dict(os.environ, MOCK_ENV_VARS, clear=True)
    @patch('pymongo.MongoClient') # Patch MongoClient at the top level where it's imported
    def setUp(self, MockMongoClient):
        # Reload the repository module to ensure it picks up the mocked os.environ for its defaults
        importlib.reload(user_m365_token_repository)

        self.mock_mongo_client_instance = MockMongoClient.return_value
        # Ensure the __getitem__ on the client (for db selection) and on db (for collection selection) are MagicMock
        self.mock_db_instance = MagicMock()
        self.mock_mongo_client_instance.__getitem__.return_value = self.mock_db_instance

        self.mock_collection_instance = MagicMock()
        self.mock_db_instance.__getitem__.return_value = self.mock_collection_instance

        # Mock the admin command used for pinging to simulate successful connection
        self.mock_mongo_client_instance.admin.command.return_value = {'ok': 1}

        # Instantiate the repository. It will use the mocked MongoClient.
        self.repository = user_m365_token_repository.MongoUserM365TokenRepository()

        # Assertions for __init__ behavior
        MockMongoClient.assert_called_with(self.MOCK_ENV_VARS["MONGO_URI"], serverSelectionTimeoutMS=5000)
        self.mock_mongo_client_instance.__getitem__.assert_called_with(self.MOCK_ENV_VARS["AUTH_MONGO_DB_NAME"])
        self.mock_db_instance.__getitem__.assert_called_with(user_m365_token_repository.DEFAULT_M365_TOKEN_COLLECTION_NAME)
        self.mock_collection_instance.create_index.assert_called_once_with("user_id", unique=True)

        # Reset mocks for collection methods that will be called by each test
        self.mock_collection_instance.update_one.reset_mock()
        self.mock_collection_instance.find_one.reset_mock()
        self.mock_collection_instance.delete_one.reset_mock()


    @patch.dict(os.environ, {"AUTH_MONGO_DB_NAME": "test"}, clear=True) # MONGO_URI is missing
    def test_init_missing_mongo_uri_logs_error_and_sets_collection_to_none(self):
        # This test assumes DEFAULT_MONGO_URI in the module might not be set or is also problematic
        # The constructor tries to connect, fails, logs, and sets self.collection to None
        with patch.object(user_m365_token_repository.pymongo, 'MongoClient', side_effect=pymongo.errors.ConnectionFailure("Test connection failure")):
            with patch.object(user_m365_token_repository.print) as mock_print: # Patch print for error log check
                importlib.reload(user_m365_token_repository) # Reload to apply new env
                repo = user_m365_token_repository.MongoUserM365TokenRepository() # MONGO_URI will default to localhost which fails due to mock
                self.assertIsNone(repo.collection)
                # Check that an error message was printed (logged)
                self.assertTrue(any("Could not connect to MongoDB" in call_args[0][0] for call_args in mock_print.call_args_list))


    def test_save_new_token(self):
        now = datetime.now(timezone.utc)
        # Note: created_at and updated_at have default factories.
        # The save method explicitly sets updated_at.
        token_data = UserM365Token(
            user_id="user123_new",
            encrypted_refresh_token="new_encrypted_token_val",
            access_token_expires_at=now + timedelta(hours=1),
            scopes=["Scope1", "Scope2"]
        )
        # The actual 'updated_at' will be set inside the save method right before DB call.

        mock_result = MagicMock(spec=pymongo.results.UpdateResult)
        mock_result.upserted_id = "mongo_upsert_id_1"
        mock_result.modified_count = 0
        mock_result.matched_count = 0 # If new, matched is 0, upserted_id is set
        self.mock_collection_instance.update_one.return_value = mock_result

        success = self.repository.save(token_data)
        self.assertTrue(success)

        self.mock_collection_instance.update_one.assert_called_once()
        call_args = self.mock_collection_instance.update_one.call_args
        query_filter, update_doc, kwargs = call_args[0][0], call_args[0][1], call_args[1]

        self.assertEqual(query_filter, {"user_id": "user123_new"})
        self.assertTrue(kwargs.get("upsert"))

        # Check $set fields
        set_doc = update_doc.get("$set", {})
        self.assertEqual(set_doc.get("user_id"), "user123_new")
        self.assertEqual(set_doc.get("encrypted_refresh_token"), "new_encrypted_token_val")
        self.assertEqual(set_doc.get("access_token_expires_at"), now + timedelta(hours=1))
        self.assertEqual(set_doc.get("scopes"), ["Scope1", "Scope2"])
        self.assertIn("created_at", set_doc) # Should be part of the initial asdict
        self.assertIn("updated_at", set_doc) # Should be updated by save()
        self.assertLessEqual(now, set_doc["updated_at"]) # updated_at >= now


    def test_save_update_existing_token(self):
        initial_creation_time = datetime.now(timezone.utc) - timedelta(days=1)
        initial_update_time = datetime.now(timezone.utc) - timedelta(hours=1)

        token_data_to_update = UserM365Token(
            user_id="user_existing_1",
            encrypted_refresh_token="updated_encrypted_token",
            access_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
            scopes=["ScopeNew"],
            created_at=initial_creation_time, # Preserve original created_at
            updated_at=initial_update_time # This will be overwritten by save()
        )

        mock_result = MagicMock(spec=pymongo.results.UpdateResult)
        mock_result.upserted_id = None
        mock_result.modified_count = 1
        mock_result.matched_count = 1
        self.mock_collection_instance.update_one.return_value = mock_result

        success = self.repository.save(token_data_to_update)
        self.assertTrue(success)

        self.mock_collection_instance.update_one.assert_called_once()
        call_args = self.mock_collection_instance.update_one.call_args
        query_filter, update_doc, kwargs = call_args[0][0], call_args[0][1], call_args[1]

        self.assertEqual(query_filter, {"user_id": "user_existing_1"})
        self.assertTrue(kwargs.get("upsert"))
        set_doc = update_doc.get("$set", {})
        self.assertEqual(set_doc.get("encrypted_refresh_token"), "updated_encrypted_token")
        self.assertEqual(set_doc.get("created_at"), initial_creation_time) # Created_at should persist
        self.assertGreater(set_doc.get("updated_at"), initial_update_time) # Updated_at should be newer

    def test_get_by_user_id_found(self):
        user_id = "user_get_found"
        db_document = {
            "_id": "some_mongo_object_id",
            "user_id": user_id,
            "encrypted_refresh_token": "retrieved_encrypted_token",
            "access_token_expires_at": datetime.now(timezone.utc),
            "scopes": ["Mail.Read", "offline_access"],
            "id_token_claims": {"sub": "m365_user_sub"},
            "created_at": datetime.now(timezone.utc) - timedelta(days=2),
            "updated_at": datetime.now(timezone.utc) - timedelta(hours=1)
        }
        self.mock_collection_instance.find_one.return_value = db_document

        result = self.repository.get_by_user_id(user_id)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, UserM365Token)
        self.assertEqual(result.user_id, user_id)
        self.assertEqual(result.encrypted_refresh_token, "retrieved_encrypted_token")
        self.assertEqual(result.id_token_claims, {"sub": "m365_user_sub"})
        self.mock_collection_instance.find_one.assert_called_once_with({"user_id": user_id})

    def test_get_by_user_id_not_found(self):
        user_id = "user_get_not_found"
        self.mock_collection_instance.find_one.return_value = None
        result = self.repository.get_by_user_id(user_id)
        self.assertIsNone(result)

    def test_delete_by_user_id_success(self):
        user_id = "user_delete_success"
        mock_result = MagicMock(spec=pymongo.results.DeleteResult)
        mock_result.deleted_count = 1
        self.mock_collection_instance.delete_one.return_value = mock_result

        success = self.repository.delete_by_user_id(user_id)
        self.assertTrue(success)
        self.mock_collection_instance.delete_one.assert_called_once_with({"user_id": user_id})

    def test_delete_by_user_id_not_found(self):
        user_id = "user_delete_not_found"
        mock_result = MagicMock(spec=pymongo.results.DeleteResult)
        mock_result.deleted_count = 0
        self.mock_collection_instance.delete_one.return_value = mock_result

        success = self.repository.delete_by_user_id(user_id)
        self.assertFalse(success) # Based on current repo logic: return bool(result.deleted_count > 0)

if __name__ == '__main__':
    unittest.main()

```
