# tests/auth_context/infrastructure/test_user_m365_token_repository.py
import unittest
from unittest.mock import patch, MagicMock
import dataclasses
from datetime import datetime, timezone, timedelta

from src.auth_context.domain.user_m365_token import UserM365Token
from src.auth_context.infrastructure.user_m365_token_repository import MongoUserM365TokenRepository
import pymongo # For pymongo.errors and constants

class TestMongoUserM365TokenRepository(unittest.TestCase):

    @patch('src.auth_context.infrastructure.user_m365_token_repository.pymongo.MongoClient')
    def setUp(self, MockMongoClient):
        self.mock_client_instance = MockMongoClient.return_value
        self.mock_db_instance = self.mock_client_instance.__getitem__.return_value
        self.mock_collection_instance = self.mock_db_instance.__getitem__.return_value
        self.mock_client_instance.admin.command.return_value = {'ok': 1} # Simulate successful ping

        self.token_repo = MongoUserM365TokenRepository(
            mongo_uri="mongodb://fakehost:1234/",
            db_name="fake_auth_db"
        )
        # Ensure collection.create_index was called if not already mocked for specific tests
        self.mock_collection_instance.create_index.assert_called_once_with("user_id", unique=True)


    def test_save_new_token(self):
        """Test saving a new UserM365Token (upsert=True results in insert)."""
        new_token_data = UserM365Token(
            user_id="user123",
            encrypted_refresh_token="enc_refresh_token_new",
            access_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes=["Mail.Read"]
        )
        token_dict = dataclasses.asdict(new_token_data)
        # The repo's save method updates 'updated_at', so we capture it for assertion
        # For a new insert, the dict passed to update_one will have the default created_at/updated_at
        # We need to ensure the mock considers the updated_at that save() sets *before* asdict()

        mock_update_result = MagicMock(spec=pymongo.results.UpdateResult)
        mock_update_result.upserted_id = "some_upserted_id"
        mock_update_result.modified_count = 0
        mock_update_result.matched_count = 0 # For a new insert via upsert
        self.mock_collection_instance.update_one.return_value = mock_update_result

        success = self.token_repo.save(new_token_data)

        self.assertTrue(success)
        # update_one is called with {'user_id': ...}, {'$set': ...}, upsert=True
        args, kwargs = self.mock_collection_instance.update_one.call_args
        self.assertEqual(args[0], {"user_id": "user123"})
        # The '$set' dict should contain all fields of UserM365Token, including updated 'updated_at'
        self.assertIn("encrypted_refresh_token", args[1]["$set"])
        self.assertIn("updated_at", args[1]["$set"])
        self.assertTrue(kwargs.get("upsert"))


    def test_save_update_existing_token(self):
        """Test updating an existing UserM365Token (upsert=True results in update)."""
        existing_token_data = UserM365Token(
            user_id="user456",
            encrypted_refresh_token="enc_refresh_token_v2",
            access_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
            scopes=["Mail.Read", "User.Read"]
        )

        mock_update_result = MagicMock(spec=pymongo.results.UpdateResult)
        mock_update_result.upserted_id = None
        mock_update_result.modified_count = 1
        mock_update_result.matched_count = 1
        self.mock_collection_instance.update_one.return_value = mock_update_result

        success = self.token_repo.save(existing_token_data)
        self.assertTrue(success)
        args, kwargs = self.mock_collection_instance.update_one.call_args
        self.assertEqual(args[0], {"user_id": "user456"})
        self.assertEqual(args[1]["$set"]["encrypted_refresh_token"], "enc_refresh_token_v2")


    def test_get_by_user_id_found(self):
        """Test retrieving an existing token by user_id."""
        user_id = "user789"
        mock_document = {
            "user_id": user_id,
            "encrypted_refresh_token": "found_token",
            "access_token_expires_at": datetime.now(timezone.utc),
            "scopes": ["profile"],
            "created_at": datetime.now(timezone.utc) - timedelta(days=1),
            "updated_at": datetime.now(timezone.utc),
            # "_id" would be present in real DB doc, but _to_domain_object pops it
        }
        self.mock_collection_instance.find_one.return_value = mock_document

        result = self.token_repo.get_by_user_id(user_id)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, UserM365Token)
        self.assertEqual(result.user_id, user_id)
        self.assertEqual(result.encrypted_refresh_token, "found_token")
        self.mock_collection_instance.find_one.assert_called_once_with({"user_id": user_id})

    def test_get_by_user_id_not_found(self):
        """Test retrieving a non-existent token."""
        user_id = "user_not_found"
        self.mock_collection_instance.find_one.return_value = None
        result = self.token_repo.get_by_user_id(user_id)
        self.assertIsNone(result)

    def test_delete_by_user_id_success(self):
        """Test deleting an existing token."""
        user_id = "user_to_delete"
        mock_delete_result = MagicMock(spec=pymongo.results.DeleteResult)
        mock_delete_result.deleted_count = 1
        self.mock_collection_instance.delete_one.return_value = mock_delete_result

        success = self.token_repo.delete_by_user_id(user_id)

        self.assertTrue(success)
        self.mock_collection_instance.delete_one.assert_called_once_with({"user_id": user_id})

    def test_delete_by_user_id_not_found(self):
        """Test deleting a non-existent token."""
        user_id = "user_not_there_for_delete"
        mock_delete_result = MagicMock(spec=pymongo.results.DeleteResult)
        mock_delete_result.deleted_count = 0
        self.mock_collection_instance.delete_one.return_value = mock_delete_result

        success = self.token_repo.delete_by_user_id(user_id)
        self.assertFalse(success)

if __name__ == '__main__':
    unittest.main()
```
