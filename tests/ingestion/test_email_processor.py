import unittest
import os
import tempfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Adjust import path based on project structure
# Assuming 'src' is in PYTHONPATH or tests are run from project root
from src.ingestion.email_processor import parse_eml_file

class TestEmailProcessor(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory to store .eml files for tests
        self.test_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        # Clean up the temporary directory
        self.test_dir.cleanup()

    def _create_temp_eml(self, filename="test_email.eml", content=None, sender="sender@example.com",
                         recipient="recipient@example.com", subject="Test Subject", body="This is a test body."):
        eml_path = os.path.join(self.test_dir.name, filename)
        if content is None:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = sender
            msg['To'] = recipient
            content = msg.as_string()

        with open(eml_path, 'w') as f:
            f.write(content)
        return eml_path

    def test_parse_simple_eml(self):
        subject = "Simple Test"
        sender = "tester@domain.com"
        recipient = "receiver@otherdomain.com"
        body = "Hello, this is the body of a simple email."
        eml_path = self._create_temp_eml(subject=subject, sender=sender, recipient=recipient, body=body)

        parsed_data = parse_eml_file(eml_path)

        self.assertIsNotNone(parsed_data)
        self.assertEqual(parsed_data['subject'], subject)
        self.assertEqual(parsed_data['sender'], sender)
        self.assertEqual(parsed_data['recipient'], recipient)
        self.assertEqual(parsed_data['body'].strip(), body) # .strip() because email library might add newlines

    def test_parse_multipart_eml(self):
        subject = "Multipart Test"
        sender = "multipart@example.com"
        recipient = "multi_receiver@example.com"
        text_body = "This is the plain text part."
        html_body = "<html><body><p>This is the HTML part.</p></body></html>"

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient

        part1 = MIMEText(text_body, 'plain')
        part2 = MIMEText(html_body, 'html')
        msg.attach(part1)
        msg.attach(part2)

        eml_path = self._create_temp_eml(filename="multipart.eml", content=msg.as_string())
        parsed_data = parse_eml_file(eml_path)

        self.assertIsNotNone(parsed_data)
        self.assertEqual(parsed_data['subject'], subject)
        self.assertEqual(parsed_data['sender'], sender)
        self.assertEqual(parsed_data['recipient'], recipient)
        # The parser prefers plain text
        self.assertEqual(parsed_data['body'].strip(), text_body)


    def test_parse_nonexistent_file(self):
        # parse_eml_file is expected to print an error and return None
        # We can also check if it logs an error if a logging mechanism is integrated into it
        parsed_data = parse_eml_file("non_existent_file.eml")
        self.assertIsNone(parsed_data) # As per current implementation

    def test_parse_invalid_eml(self):
        eml_path = self._create_temp_eml(filename="invalid.eml", content="This is not a valid email format.")
        # parse_eml_file is expected to print an error and return None
        parsed_data = parse_eml_file(eml_path)
        self.assertIsNone(parsed_data) # As per current implementation

    def test_parse_eml_no_body(self):
        subject = "No Body Test"
        sender = "nobody@example.com"
        recipient = "receiver@example.com"

        msg = MIMEText('') # Empty body
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient

        eml_path = self._create_temp_eml(filename="no_body.eml", content=msg.as_string())
        parsed_data = parse_eml_file(eml_path)

        self.assertIsNotNone(parsed_data)
        self.assertEqual(parsed_data['subject'], subject)
        self.assertEqual(parsed_data['sender'], sender)
        self.assertEqual(parsed_data['recipient'], recipient)
        self.assertEqual(parsed_data['body'], "")

if __name__ == '__main__':
    unittest.main()
