# tests/activity_log_context/infrastructure/test_activity_repository.py
import unittest
from unittest.mock import patch, MagicMock
import dataclasses

from src.activity_log_context.infrastructure.activity_repository import MongoActivityRepository
from src.activity_log_context.domain.activity_record import ActivityRecord

class TestMongoActivityRepository(unittest.TestCase):

    @patch('src.activity_log_context.infrastructure.activity_repository.pymongo.MongoClient')
    def setUp(self, MockMongoClient): # Inject the mock into setUp
        # Configure the mock client and its methods
        self.mock_client_instance = MockMongoClient.return_value
        self.mock_db_instance = self.mock_client_instance.__getitem__.return_value # db = client[db_name]
        self.mock_collection_instance = self.mock_db_instance.__getitem__.return_value # collection = db[collection_name]

        # Mock the admin command used for pinging to simulate successful connection
        self.mock_client_instance.admin.command.return_value = {'ok': 1}

        # Instantiate the repository. It will use the mocked MongoClient.
        self.repo = MongoActivityRepository(mongo_uri="mongodb://fakehost:27017/", db_name="fakedb")

        # Ensure the mock client was called during repo initialization
        MockMongoClient.assert_called_with("mongodb://fakehost:27017/", serverSelectionTimeoutMS=5000)


    def test_add_activity_record_success(self):
        # --- Arrange ---
        activity = ActivityRecord(
            record_id="test_add_id_001",
            ingested_at="ts1", source_channel="test", source_identifier="id1",
            subject="Test Add"
            # Other fields can use defaults or be None
        )
        activity_dict = dataclasses.asdict(activity)

        # Configure mock collection's insert_one method
        mock_insert_result = MagicMock()
        mock_insert_result.inserted_id = "mongo_generated_id_123"
        self.mock_collection_instance.insert_one.return_value = mock_insert_result

        # --- Act ---
        success = self.repo.add(activity)

        # --- Assert ---
        self.assertTrue(success)
        self.mock_collection_instance.insert_one.assert_called_once_with(activity_dict)

    def test_get_by_id_found(self):
        # --- Arrange ---
        record_id_to_find = "find_me_id_002"
        # This is the dict as it would come from MongoDB
        mock_db_document = {
            "_id": "mongo_id_xyz",
            "record_id": record_id_to_find,
            "ingested_at": "ts2",
            "source_channel": "email",
            "source_identifier": "file.eml",
            "subject": "Found Me!",
            # other fields populated as they would be in DB
            "sender": "s@e.com", "recipient": "r@e.com", "summary": "Sum", "disposition": "Disp",
            "full_content_reference": "ref", "logged_at": "ts_log", "metadata": {}
        }
        self.mock_collection_instance.find_one.return_value = mock_db_document

        # --- Act ---
        result = self.repo.get_by_id(record_id_to_find)

        # --- Assert ---
        self.assertIsNotNone(result)
        self.assertIsInstance(result, ActivityRecord)
        self.assertEqual(result.record_id, record_id_to_find)
        self.assertEqual(result.subject, "Found Me!")
        self.mock_collection_instance.find_one.assert_called_once_with({"record_id": record_id_to_find})

    def test_get_by_id_not_found(self):
        # --- Arrange ---
        record_id_to_find = "not_found_id_003"
        self.mock_collection_instance.find_one.return_value = None # Simulate not found

        # --- Act ---
        result = self.repo.get_by_id(record_id_to_find)

        # --- Assert ---
        self.assertIsNone(result)
        self.mock_collection_instance.find_one.assert_called_once_with({"record_id": record_id_to_find})

    def test_list_all_returns_records(self):
        # --- Arrange ---
        mock_db_documents = [
            {"_id": "id1", "record_id": "rec1", "subject": "Rec 1", "ingested_at": "ts", "source_channel": "c", "source_identifier": "sid"},
            {"_id": "id2", "record_id": "rec2", "subject": "Rec 2", "ingested_at": "ts", "source_channel": "c", "source_identifier": "sid"},
        ]
        # Mock the cursor returned by find()
        mock_cursor = MagicMock()
        mock_cursor.limit.return_value = mock_db_documents # find().limit() returns iterable
        self.mock_collection_instance.find.return_value = mock_cursor

        # --- Act ---
        results = self.repo.list_all(limit=10)

        # --- Assert ---
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], ActivityRecord)
        self.assertEqual(results[0].record_id, "rec1")
        self.assertEqual(results[1].subject, "Rec 2")
        self.mock_collection_instance.find.assert_called_once_with()
        mock_cursor.limit.assert_called_once_with(10)

    def test_add_fails_due_to_operation_failure(self):
        # --- Arrange ---
        activity = ActivityRecord(record_id="fail_add_id", subject="Fail Add", ingested_at="ts", source_channel="c", source_identifier="sid")
        # Simulate a pymongo OperationFailure
        self.mock_collection_instance.insert_one.side_effect = pymongo.errors.OperationFailure("Mocked DB error")

        # --- Act ---
        success = self.repo.add(activity)

        # --- Assert ---
        self.assertFalse(success)

    @patch('src.activity_log_context.infrastructure.activity_repository.pymongo.MongoClient')
    def test_repository_init_connection_failure(self, MockMongoClientFailure):
        # --- Arrange ---
        # Simulate MongoClient raising ConnectionFailure
        MockMongoClientFailure.side_effect = pymongo.errors.ConnectionFailure("Mocked connection error")

        # --- Act & Assert ---
        # The constructor itself prints the error. We check if client is None.
        # Need to be careful as self.repo in setUp would have used the other mock.
        # So, instantiate a new one here.
        failed_repo = MongoActivityRepository()
        self.assertIsNone(failed_repo.client)
        self.assertIsNone(failed_repo.collection)


if __name__ == '__main__':
    # Need to import pymongo.errors for the side_effect in test_add_fails_due_to_operation_failure
    import pymongo.errors
    unittest.main()
