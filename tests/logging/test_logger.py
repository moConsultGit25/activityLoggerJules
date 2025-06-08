import unittest
import os
import csv
import tempfile
from datetime import datetime

# Adjust import path
from src.logging.logger import log_activity, LOG_HEADERS, DEFAULT_LOG_DIR

class TestLogger(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory to store log files for tests
        self.test_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = self.test_dir_obj.name

    def tearDown(self):
        # Clean up the temporary directory
        self.test_dir_obj.cleanup()

    def _read_log_file(self, log_file_path):
        rows = []
        if os.path.exists(log_file_path):
            with open(log_file_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    rows.append(row)
        return rows

    def test_log_single_activity_new_file(self):
        log_file = os.path.join(self.test_dir, "activity_single.csv")

        activity_data = {
            'timestamp': datetime.now().isoformat(),
            'email_id': 'test_email_001',
            'sender': 'sender@test.com',
            'recipient': 'receiver@test.com',
            'subject': 'Log Test 1',
            'summary': 'This is the first summary.',
            'disposition': 'General',
            'original_file_path': 'path/to/email1.eml'
        }

        log_activity(log_file, activity_data)

        self.assertTrue(os.path.exists(log_file))

        logged_content = self._read_log_file(log_file)

        self.assertEqual(len(logged_content), 2) # Header + 1 data row
        self.assertEqual(logged_content[0], LOG_HEADERS)

        # Verify data row (order matters based on LOG_HEADERS)
        expected_row = [activity_data.get(h) for h in LOG_HEADERS]
        self.assertEqual(logged_content[1], expected_row)

    def test_log_append_activity_existing_file(self):
        log_file = os.path.join(self.test_dir, "activity_append.csv")

        activity_data_1 = {
            'timestamp': datetime(2023, 1, 1, 10, 0, 0).isoformat(),
            'email_id': 'append_001',
            'sender': 's1@test.com',
            'recipient': 'r1@test.com',
            'subject': 'Append Test 1',
            'summary': 'Summary one.',
            'disposition': 'Sales Inquiry',
            'original_file_path': 'append/1.eml'
        }
        log_activity(log_file, activity_data_1)

        activity_data_2 = {
            'timestamp': datetime(2023, 1, 1, 11, 0, 0).isoformat(),
            'email_id': 'append_002',
            'sender': 's2@test.com',
            'recipient': 'r2@test.com',
            'subject': 'Append Test 2',
            'summary': 'Summary two.',
            'disposition': 'Support Request',
            'original_file_path': 'append/2.eml'
        }
        log_activity(log_file, activity_data_2)

        logged_content = self._read_log_file(log_file)

        self.assertEqual(len(logged_content), 3) # Header + 2 data rows
        self.assertEqual(logged_content[0], LOG_HEADERS)

        expected_row_1 = [activity_data_1.get(h) for h in LOG_HEADERS]
        self.assertEqual(logged_content[1], expected_row_1)

        expected_row_2 = [activity_data_2.get(h) for h in LOG_HEADERS]
        self.assertEqual(logged_content[2], expected_row_2)

    def test_log_activity_missing_fields(self):
        log_file = os.path.join(self.test_dir, "activity_missing_fields.csv")
        activity_data = {
            'timestamp': datetime.now().isoformat(),
            'email_id': 'missing_001',
            'sender': 's_missing@test.com',
            # recipient is missing
            'subject': 'Missing Fields Test',
            # summary is missing
            'disposition': 'Finance'
            # original_file_path is missing
        }

        log_activity(log_file, activity_data)
        logged_content = self._read_log_file(log_file)

        self.assertEqual(len(logged_content), 2)
        self.assertEqual(logged_content[0], LOG_HEADERS)

        # Construct expected row with Nones for missing fields
        expected_row_values = []
        for header in LOG_HEADERS:
            expected_row_values.append(activity_data.get(header)) # .get() returns None if key is missing

        self.assertEqual(logged_content[1], expected_row_values)


    def test_log_activity_extra_fields(self):
        log_file = os.path.join(self.test_dir, "activity_extra_fields.csv")
        activity_data = {
            'timestamp': datetime.now().isoformat(),
            'email_id': 'extra_001',
            'sender': 's_extra@test.com',
            'recipient': 'r_extra@test.com',
            'subject': 'Extra Fields Test',
            'summary': 'Summary for extra.',
            'disposition': 'General',
            'original_file_path': 'path/extra.eml',
            'bonus_field': 'this should not be logged',
            'another_one': 12345
        }

        log_activity(log_file, activity_data)
        logged_content = self._read_log_file(log_file)

        self.assertEqual(len(logged_content), 2)
        self.assertEqual(logged_content[0], LOG_HEADERS)

        expected_row_values = [activity_data.get(h) for h in LOG_HEADERS]
        self.assertEqual(logged_content[1], expected_row_values) # Ensures only fields in LOG_HEADERS are written

    def test_log_directory_creation(self):
        # Test that log_activity creates the directory if it doesn't exist
        # This assumes DEFAULT_LOG_DIR or a custom path might not exist initially
        # For this test, we use a subdirectory within our self.test_dir
        nested_log_dir = os.path.join(self.test_dir, "new_log_subdir")
        log_file = os.path.join(nested_log_dir, "activity_in_subdir.csv")

        self.assertFalse(os.path.exists(nested_log_dir)) # Should not exist yet

        activity_data = {
            'timestamp': datetime.now().isoformat(),
            'email_id': 'subdir_test_001',
            'sender': 'subdir@test.com',
            'subject': 'Subdir Log Test',
            'summary': 'Testing subdir creation.',
            'disposition': 'General',
            'original_file_path': 'path/subdir_email.eml'
        }

        log_activity(log_file, activity_data)

        self.assertTrue(os.path.exists(nested_log_dir))
        self.assertTrue(os.path.exists(log_file))

        logged_content = self._read_log_file(log_file)
        self.assertEqual(len(logged_content), 2) # Header + 1 data row
        self.assertEqual(logged_content[0], LOG_HEADERS)


if __name__ == '__main__':
    unittest.main()
