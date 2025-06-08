# tests/activity_log_context/interfaces/test_event_handlers.py
import unittest
from unittest.mock import patch, MagicMock
import datetime

from src.activity_log_context.interfaces.event_handlers import handle_content_analyzed
from src.shared_kernel.events import ContentAnalyzedEvent
from src.activity_log_context.domain.activity_record import ActivityRecord # For asserting type if needed

class TestActivityLogEventHandlers(unittest.TestCase):

    @patch('src.activity_log_context.interfaces.event_handlers.log_service_instance') # Mock the global log_service_instance
    def test_handle_content_analyzed_calls_log_service(self, mock_log_service):
        # --- Arrange ---
        # Prepare a sample ContentAnalyzedEvent
        analyzed_event = ContentAnalyzedEvent(
            raw_email_id="test_id_for_log_handler",
            sender="sender_for_log@example.com",
            recipient="recipient_for_log@example.com",
            subject="Log Handler Test Subject",
            body="Original body for log handler.",
            received_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            source_identifier="/path/to/log_trigger_email.eml",
            summary="Summary to be logged.",
            disposition="Disposition to be logged",
            keywords_found=["log", "handler"],
            analyzed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )

        # Configure the mock log_service's method to simulate returning an ActivityRecord
        # (or True/False depending on its actual return signature for success)
        mock_activity_record_dummy = MagicMock(spec=ActivityRecord)
        mock_activity_record_dummy.record_id = "dummy_logged_record_id"
        mock_log_service.record_activity_from_event_data.return_value = mock_activity_record_dummy

        # --- Act ---
        handle_content_analyzed(analyzed_event)

        # --- Assert ---
        # 1. Verify LogService.record_activity_from_event_data was called correctly
        mock_log_service.record_activity_from_event_data.assert_called_once_with(analyzed_event)

    @patch('src.activity_log_context.interfaces.event_handlers.log_service_instance')
    def test_handle_content_analyzed_log_service_fails(self, mock_log_service):
        # --- Arrange ---
        analyzed_event = ContentAnalyzedEvent(raw_email_id="log_fail_id", subject="Log Fail",
                                     # Populate other required fields minimally
                                     sender="s", recipient="r", body="b", received_at="ts1",
                                     source_identifier="sid1", summary="sum", disposition="disp",
                                     analyzed_at="ts_a")

        # Simulate log_service method returning None (or raising an exception if that's its behavior)
        mock_log_service.record_activity_from_event_data.return_value = None

        # --- Act ---
        # The handler itself doesn't do much error handling other than what LogService does.
        # We are mainly testing the call.
        handle_content_analyzed(analyzed_event)

        # --- Assert ---
        mock_log_service.record_activity_from_event_data.assert_called_once_with(analyzed_event)
        # No specific assertion on the handler's output as it just prints.
        # The key is that it called the service.

if __name__ == '__main__':
    unittest.main()
