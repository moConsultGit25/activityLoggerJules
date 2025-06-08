# tests/ingestion_context/infrastructure/test_email_parser.py
import unittest
import os
import tempfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Adjust import path based on project structure.
# Assumes tests are run from the project root where 'src' is a top-level directory.
from src.ingestion_context.infrastructure.email_parser import parse_eml_file_to_dict

class TestEmailParser(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.test_dir.cleanup()

    def _create_temp_eml(self, filename="test_email.eml", content=None,
                         sender="sender@example.com", recipient="recipient@example.com",
                         subject="Test Subject", body="This is a test body.",
                         message_id_header="<test.msg.id@example.com>"):
        eml_path = os.path.join(self.test_dir.name, filename)
        if content is None:
            msg = MIMEText(body, 'plain', 'utf-8') # Specify encoding for MIMEText
            msg['Subject'] = subject
            msg['From'] = sender
            msg['To'] = recipient
            msg['Message-ID'] = message_id_header
            # Ensure content is string when writing to file in text mode
            content = msg.as_string()

        # Write as bytes if original parser expects 'rb', or text if 'r'
        # The current parse_eml_file_to_dict uses 'rb'
        with open(eml_path, 'wb') as f: # Changed to 'wb'
            if isinstance(content, str):
                f.write(content.encode('utf-8')) # Encode string to bytes
            else: # If content is already bytes (e.g. from msg.as_bytes())
                f.write(content)
        return eml_path

    def test_parse_simple_eml(self):
        subject = "Simple Test Parser"
        sender = "parser_sender@example.com"
        recipient = "parser_recipient@example.com"
        body = "Hello, this is the body of a simple email for the parser."
        message_id = "<simple.parser.test@example.com>"

        eml_path = self._create_temp_eml(
            subject=subject, sender=sender, recipient=recipient, body=body, message_id_header=message_id
        )

        parsed_data = parse_eml_file_to_dict(eml_path)

        self.assertIsNotNone(parsed_data)
        self.assertEqual(parsed_data['subject'], subject)
        self.assertEqual(parsed_data['sender'], sender)
        self.assertEqual(parsed_data['recipient'], recipient)
        self.assertEqual(parsed_data['message_id_header'], message_id)
        self.assertEqual(parsed_data['body'].strip(), body)
        self.assertIn(body, parsed_data['raw_eml_content']) # Raw content should contain body

    def test_parse_multipart_eml_prefers_plain_text(self):
        subject = "Multipart Parser Test"
        text_body = "This is the plain text part for parser."
        html_body = "<html><body><p>This is the HTML part for parser.</p></body></html>"
        message_id = "<multipart.parser.test@example.com>"

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = "multipart_sender@example.com"
        msg['To'] = "multipart_recipient@example.com"
        msg['Message-ID'] = message_id

        part1 = MIMEText(text_body, 'plain', 'utf-8')
        part2 = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(part1)
        msg.attach(part2)

        eml_path = self._create_temp_eml(filename="multipart_parser.eml", content=msg.as_bytes()) # Use as_bytes()
        parsed_data = parse_eml_file_to_dict(eml_path)

        self.assertIsNotNone(parsed_data)
        self.assertEqual(parsed_data['subject'], subject)
        self.assertEqual(parsed_data['message_id_header'], message_id)
        self.assertEqual(parsed_data['body'].strip(), text_body) # Parser should extract plain text
        self.assertIn(text_body, parsed_data['raw_eml_content'])
        self.assertIn(html_body, parsed_data['raw_eml_content'])


    def test_parse_nonexistent_file(self):
        parsed_data = parse_eml_file_to_dict("non_existent_parser_file.eml")
        self.assertIsNone(parsed_data) # Expects None for file not found

    def test_parse_invalid_eml_content(self):
        # Create a file with non-EML text content
        invalid_eml_path = os.path.join(self.test_dir.name, "invalid_format.eml")
        with open(invalid_eml_path, 'wb') as f: # Write bytes
            f.write(b"This is just some random text, not a valid EML file structure.")

        parsed_data = parse_eml_file_to_dict(invalid_eml_path)
        # The parser might still extract some parts or fail gracefully.
        # Current implementation tries to parse and might return partial data or None on error.
        # Given the current parser, it will likely return None or a dict with mostly None values if it hits an error early.
        # Let's check based on the provided parser's behavior which prints an error and returns None.
        self.assertIsNone(parsed_data, "Parser should return None for badly malformed EML files.")

    def test_parse_eml_with_no_message_id_header(self):
        eml_path = self._create_temp_eml(body="Body for no message ID test", message_id_header=None)
        parsed_data = parse_eml_file_to_dict(eml_path)
        self.assertIsNotNone(parsed_data)
        self.assertIsNone(parsed_data['message_id_header'])


if __name__ == '__main__':
    unittest.main()
