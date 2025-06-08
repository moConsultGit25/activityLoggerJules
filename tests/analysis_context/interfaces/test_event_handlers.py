# tests/analysis_context/interfaces/test_event_handlers.py
import unittest
from unittest.mock import patch, MagicMock
import datetime

from src.analysis_context.interfaces.event_handlers import handle_email_ingested
from src.shared_kernel.events import EmailIngestedEvent, ContentAnalyzedEvent
from src.analysis_context.domain.analyzed_content import AnalyzedContent

class TestAnalysisEventHandlers(unittest.TestCase):

    @patch('src.analysis_context.interfaces.event_handlers.dispatcher') # Mock global dispatcher
    @patch('src.analysis_context.interfaces.event_handlers.analysis_service') # Mock analysis_service instance
    def test_handle_email_ingested_success(self, mock_analysis_service, mock_dispatcher):
        # --- Arrange ---
        # Prepare a sample EmailIngestedEvent
        ingested_event = EmailIngestedEvent(
            raw_email_id="test_id_for_analysis_handler",
            sender="sender@example.com",
            recipient="recipient@example.com",
            subject="Handler Test Subject",
            body="This is the body for analysis handler. Needs processing.",
            received_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            source_identifier="/path/to/email.eml"
        )

        # Configure the mock analysis_service to return an AnalyzedContent object
        mock_analyzed_content = AnalyzedContent(
            raw_email_id=ingested_event.raw_email_id,
            summary="Mocked summary.",
            disposition="Mocked Disposition",
            keywords_found=["mocked", "keyword"],
            analysis_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        mock_analysis_service.analyze_text_content.return_value = mock_analyzed_content

        # --- Act ---
        handle_email_ingested(ingested_event)

        # --- Assert ---
        # 1. Verify AnalysisService.analyze_text_content was called correctly
        mock_analysis_service.analyze_text_content.assert_called_once_with(
            raw_email_id=ingested_event.raw_email_id,
            text_to_analyze=ingested_event.body,
            subject_text=ingested_event.subject
        )

        # 2. Verify ContentAnalyzedEvent was published with correct data
        self.assertEqual(mock_dispatcher.publish.call_count, 1)
        published_event_arg = mock_dispatcher.publish.call_args[0][0]

        self.assertIsInstance(published_event_arg, ContentAnalyzedEvent)
        self.assertEqual(published_event_arg.raw_email_id, ingested_event.raw_email_id)
        self.assertEqual(published_event_arg.sender, ingested_event.sender)
        self.assertEqual(published_event_arg.recipient, ingested_event.recipient)
        self.assertEqual(published_event_arg.subject, ingested_event.subject)
        self.assertEqual(published_event_arg.body, ingested_event.body)
        self.assertEqual(published_event_arg.received_at, ingested_event.received_at)
        self.assertEqual(published_event_arg.source_identifier, ingested_event.source_identifier)
        self.assertEqual(published_event_arg.summary, mock_analyzed_content.summary)
        self.assertEqual(published_event_arg.disposition, mock_analyzed_content.disposition)
        self.assertEqual(published_event_arg.keywords_found, mock_analyzed_content.keywords_found)
        self.assertEqual(published_event_arg.analyzed_at, mock_analyzed_content.analysis_timestamp)

    @patch('src.analysis_context.interfaces.event_handlers.dispatcher')
    @patch('src.analysis_context.interfaces.event_handlers.analysis_service')
    def test_handle_email_ingested_analysis_fails(self, mock_analysis_service, mock_dispatcher):
        # --- Arrange ---
        ingested_event = EmailIngestedEvent(
            raw_email_id="fail_analysis_id",
            sender="s@e.com", recipient="r@e.com", subject="Sub", body="Body",
            received_at="timestamp", source_identifier="path"
        )
        # Simulate analysis_service returning None (failure)
        mock_analysis_service.analyze_text_content.return_value = None

        # --- Act ---
        handle_email_ingested(ingested_event)

        # --- Assert ---
        mock_analysis_service.analyze_text_content.assert_called_once()
        mock_dispatcher.publish.assert_not_called() # No ContentAnalyzedEvent should be published

if __name__ == '__main__':
    unittest.main()
