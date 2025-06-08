# tests/ingestion_context/application/test_ingestion_service.py
import unittest
from unittest.mock import patch, MagicMock
import uuid
import datetime

from src.ingestion_context.application.ingestion_service import IngestionService
from src.ingestion_context.domain.raw_email import RawEmail
from src.shared_kernel.events import EmailIngestedEvent

class TestIngestionService(unittest.TestCase):

    @patch('src.ingestion_context.application.ingestion_service.parse_eml_file_to_dict')
    @patch('src.ingestion_context.application.ingestion_service.dispatcher') # Mock the global dispatcher
    def test_ingest_email_from_file_success(self, mock_dispatcher, mock_parse_eml):
        # --- Arrange ---
        test_file_path = "/test/dummy_email.eml"
        parsed_data_dict = {
            'sender': 'sender@example.com',
            'recipient': 'recipient@example.com',
            'subject': 'Test Subject from Parser',
            'body': 'This is the parsed email body.',
            'message_id_header': '<parser.id.123@example.com>',
            'raw_eml_content': 'From: sender...\nTo:...\nSubject:...\n\nBody...'
        }
        mock_parse_eml.return_value = parsed_data_dict

        service = IngestionService()

        # --- Act ---
        result_raw_email = service.ingest_email_from_file(test_file_path)

        # --- Assert ---
        # 1. Check if parser was called correctly
        mock_parse_eml.assert_called_once_with(test_file_path)

        # 2. Check if RawEmail object is created correctly
        self.assertIsNotNone(result_raw_email)
        self.assertIsInstance(result_raw_email, RawEmail)
        self.assertEqual(result_raw_email.sender, parsed_data_dict['sender'])
        self.assertEqual(result_raw_email.recipient, parsed_data_dict['recipient'])
        self.assertEqual(result_raw_email.subject, parsed_data_dict['subject'])
        self.assertEqual(result_raw_email.raw_content, parsed_data_dict['raw_eml_content'])
        self.assertEqual(result_raw_email.source_file_path, test_file_path)
        # Message ID should be the cleaned one from header or a UUID if header was None
        self.assertEqual(result_raw_email.message_id, 'parser.id.123@example.com')
        self.assertIsNotNone(result_raw_email.received_at) # Should be set by default factory

        # 3. Check if EmailIngestedEvent was published with correct data
        self.assertEqual(mock_dispatcher.publish.call_count, 1)
        published_event_arg = mock_dispatcher.publish.call_args[0][0] # Get the first arg of the first call

        self.assertIsInstance(published_event_arg, EmailIngestedEvent)
        self.assertEqual(published_event_arg.raw_email_id, result_raw_email.message_id)
        self.assertEqual(published_event_arg.sender, result_raw_email.sender)
        self.assertEqual(published_event_arg.recipient, result_raw_email.recipient)
        self.assertEqual(published_event_arg.subject, result_raw_email.subject)
        self.assertEqual(published_event_arg.body, parsed_data_dict['body']) # Event body is the parsed plain text
        self.assertEqual(published_event_arg.received_at, result_raw_email.received_at)
        self.assertEqual(published_event_arg.source_identifier, test_file_path)

    @patch('src.ingestion_context.application.ingestion_service.parse_eml_file_to_dict')
    @patch('src.ingestion_context.application.ingestion_service.dispatcher')
    def test_ingest_email_from_file_parser_fails(self, mock_dispatcher, mock_parse_eml):
        # --- Arrange ---
        test_file_path = "/test/bad_email.eml"
        mock_parse_eml.return_value = None # Simulate parser failure

        service = IngestionService()

        # --- Act ---
        result_raw_email = service.ingest_email_from_file(test_file_path)

        # --- Assert ---
        mock_parse_eml.assert_called_once_with(test_file_path)
        self.assertIsNone(result_raw_email)
        mock_dispatcher.publish.assert_not_called() # No event should be published

    @patch('src.ingestion_context.application.ingestion_service.parse_eml_file_to_dict')
    @patch('src.ingestion_context.application.ingestion_service.dispatcher')
    @patch('uuid.uuid4') # Mock uuid.uuid4 to control generated IDs
    def test_ingest_email_no_message_id_header(self, mock_uuid4, mock_dispatcher, mock_parse_eml):
        # --- Arrange ---
        test_file_path = "/test/no_header_email.eml"
        fixed_uuid = uuid.UUID('12345678-1234-5678-1234-567812345678')
        mock_uuid4.return_value = fixed_uuid

        parsed_data_dict = {
            'sender': 'sender@example.com',
            'recipient': 'recipient@example.com',
            'subject': 'No Message-ID Header',
            'body': 'Body content.',
            'message_id_header': None, # Simulate no Message-ID header
            'raw_eml_content': 'Raw EML content here'
        }
        mock_parse_eml.return_value = parsed_data_dict
        service = IngestionService()

        # --- Act ---
        result_raw_email = service.ingest_email_from_file(test_file_path)

        # --- Assert ---
        self.assertIsNotNone(result_raw_email)
        self.assertEqual(result_raw_email.message_id, str(fixed_uuid)) # Should use UUID

        mock_dispatcher.publish.assert_called_once()
        published_event_arg = mock_dispatcher.publish.call_args[0][0]
        self.assertEqual(published_event_arg.raw_email_id, str(fixed_uuid))


if __name__ == '__main__':
    unittest.main()
