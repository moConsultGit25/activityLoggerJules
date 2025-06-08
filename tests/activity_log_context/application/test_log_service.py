# tests/activity_log_context/application/test_log_service.py
import unittest
from unittest.mock import patch, MagicMock
import datetime

from src.activity_log_context.application.log_service import LogService
from src.activity_log_context.domain.activity_record import ActivityRecord
from src.shared_kernel.events import ContentAnalyzedEvent # For testing the event-driven method

class TestLogService(unittest.TestCase):

    @patch('src.activity_log_context.application.log_service.MongoActivityRepository')
    def setUp(self, MockMongoActivityRepository):
        # Create a mock instance of the repository
        self.mock_repo_instance = MockMongoActivityRepository.return_value
        # Simulate a successful connection for the repository by default
        self.mock_repo_instance.collection = MagicMock() # Make it not None

        # Instantiate LogService with the mocked repository
        self.log_service = LogService(activity_log_repo=self.mock_repo_instance)

    def test_record_activity_from_event_data_success(self):
        # --- Arrange ---
        event = ContentAnalyzedEvent(
            raw_email_id="event_id_001",
            sender="sender_from_event@example.com",
            recipient="recipient_from_event@example.com",
            subject="Subject from Event",
            body="Original body from event.",
            received_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            source_identifier="/path/to/event_source.eml",
            summary="This is the event summary.",
            disposition="EventDisposition",
            keywords_found=["event", "test"],
            analyzed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )

        # Configure the mock repository's add method to return True (success)
        self.mock_repo_instance.add.return_value = True

        # --- Act ---
        result_activity_record = self.log_service.record_activity_from_event_data(event)

        # --- Assert ---
        # 1. Verify an ActivityRecord object was returned
        self.assertIsNotNone(result_activity_record)
        self.assertIsInstance(result_activity_record, ActivityRecord)

        # 2. Verify the repository's add method was called once with the ActivityRecord
        self.mock_repo_instance.add.assert_called_once()
        call_args = self.mock_repo_instance.add.call_args[0]
        self.assertIsInstance(call_args[0], ActivityRecord)

        # 3. Verify data mapping from event to ActivityRecord
        created_record = call_args[0]
        self.assertEqual(created_record.ingested_at, event.received_at)
        self.assertEqual(created_record.source_identifier, event.source_identifier)
        self.assertEqual(created_record.sender, event.sender)
        self.assertEqual(created_record.recipient, event.recipient)
        self.assertEqual(created_record.subject, event.subject)
        self.assertEqual(created_record.summary, event.summary)
        self.assertEqual(created_record.disposition, event.disposition)
        self.assertEqual(created_record.metadata['analyzed_at'], event.analyzed_at)
        self.assertEqual(created_record.metadata['keywords_found'], event.keywords_found)
        self.assertIn(event.body[:200], created_record.metadata['original_body_snippet'])


    def test_record_activity_from_event_data_repo_add_fails(self):
        # --- Arrange ---
        event = ContentAnalyzedEvent(raw_email_id="event_id_002", subject="Repo Fail Test",
                                     # Populate other required fields minimally
                                     sender="s", recipient="r", body="b", received_at="ts1",
                                     source_identifier="sid1", summary="sum", disposition="disp",
                                     analyzed_at="ts_a")

        # Configure mock repository's add method to return False (failure)
        self.mock_repo_instance.add.return_value = False

        # --- Act ---
        result_activity_record = self.log_service.record_activity_from_event_data(event)

        # --- Assert ---
        self.assertIsNone(result_activity_record) # Should return None on failure
        self.mock_repo_instance.add.assert_called_once() # Still should be called

    @patch('src.activity_log_context.application.log_service.MongoActivityRepository')
    def test_log_service_init_no_repo_provided(self, MockRepoConstructor):
        # Test that if no repo is passed, LogService instantiates one itself.
        # This also implicitly tests if the default repo connection message is printed.
        mock_repo_created_instance = MockRepoConstructor.return_value
        mock_repo_created_instance.collection = MagicMock() # Simulate successful connection

        service = LogService() # Initialize without passing a repo

        MockRepoConstructor.assert_called_once() # Should have been called to create default repo
        self.assertIsNotNone(service.activity_log_repo)


if __name__ == '__main__':
    unittest.main()
