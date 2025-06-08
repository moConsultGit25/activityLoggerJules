import csv
import os
from datetime import datetime

DEFAULT_LOG_DIR = "data" # As per requirement, log files intended to be stored here by default

LOG_HEADERS = [
    'timestamp', 'email_id', 'sender', 'recipient',
    'subject', 'summary', 'disposition', 'original_file_path'
]

def log_activity(log_file_path, activity_data):
    """
    Logs activity data to a CSV file.

    Args:
        log_file_path (str): Path to the CSV log file.
        activity_data (dict): A dictionary containing the data to log.
                              It should ideally contain keys matching LOG_HEADERS.
    """
    try:
        # Ensure the directory for the log file exists
        log_dir = os.path.dirname(log_file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            print(f"Created directory: {log_dir}")

        file_exists = os.path.isfile(log_file_path)

        with open(log_file_path, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=LOG_HEADERS)

            if not file_exists:
                writer.writeheader()
                print(f"Created log file and wrote header: {log_file_path}")

            # Ensure only known fields are written
            filtered_data = {key: activity_data.get(key) for key in LOG_HEADERS}
            writer.writerow(filtered_data)

    except IOError as e:
        print(f"IOError writing to log file {log_file_path}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while logging: {e}")

if __name__ == '__main__':
    # Example Usage

    # Define a default log file path within the 'data' directory
    example_log_file = os.path.join(DEFAULT_LOG_DIR, "activity_log.csv")

    # Ensure the data directory exists for the example
    if not os.path.exists(DEFAULT_LOG_DIR):
        os.makedirs(DEFAULT_LOG_DIR)

    print(f"Logging examples to: {example_log_file}\n")

    # Example 1: First log entry, file and header should be created
    log_data_1 = {
        'timestamp': datetime.now().isoformat(),
        'email_id': 'email123',
        'sender': 'sender1@example.com',
        'recipient': 'recipient1@example.com',
        'subject': 'Test Email 1 - Sales Inquiry',
        'summary': 'First sentence. Second sentence.',
        'disposition': 'Sales Inquiry',
        'original_file_path': 'path/to/email1.eml'
    }
    print("Logging data 1...")
    log_activity(example_log_file, log_data_1)

    # Example 2: Second log entry, should append to existing file
    log_data_2 = {
        'timestamp': datetime.now().isoformat(),
        'email_id': 'email456',
        'sender': 'sender2@example.com',
        'recipient': 'recipient2@example.com',
        'subject': 'Help needed with product - Support Request',
        'summary': 'Having an issue. Need help.',
        'disposition': 'Support Request',
        'original_file_path': 'path/to/email2.eml'
    }
    print("\nLogging data 2...")
    log_activity(example_log_file, log_data_2)

    # Example 3: Log entry with some missing fields (should still work, missing fields will be empty)
    log_data_3 = {
        'timestamp': datetime.now().isoformat(),
        'email_id': 'email789',
        'sender': 'sender3@example.com',
        # 'recipient': 'recipient3@example.com', # Missing recipient
        'subject': 'Invoice #INV001 - Finance',
        'summary': 'Invoice details.',
        'disposition': 'Finance',
        # 'original_file_path': 'path/to/email3.eml' # Missing path
    }
    print("\nLogging data 3 (with missing fields)...")
    log_activity(example_log_file, log_data_3)

    # Example 4: Log entry with extra fields (extra fields should be ignored)
    log_data_4 = {
        'timestamp': datetime.now().isoformat(),
        'email_id': 'email101',
        'sender': 'sender4@example.com',
        'recipient': 'recipient4@example.com',
        'subject': 'General Question',
        'summary': 'A quick question.',
        'disposition': 'General',
        'original_file_path': 'path/to/email4.eml',
        'custom_field_not_in_header': 'this should be ignored'
    }
    print("\nLogging data 4 (with extra fields)...")
    log_activity(example_log_file, log_data_4)

    print(f"\nCheck the log file at: {example_log_file}")

    # Demonstrate logging to a different file path
    custom_log_file = os.path.join(DEFAULT_LOG_DIR, "custom_log.csv")
    print(f"\nLogging an entry to a custom log file: {custom_log_file}")
    log_data_custom = {
        'timestamp': datetime.now().isoformat(),
        'email_id': 'custom001',
        'sender': 'custom@example.com',
        'subject': 'Custom Log Test',
        'summary': 'This is a test for a different log file.',
        'disposition': 'General',
        'original_file_path': 'path/to/custom_email.eml'
    }
    log_activity(custom_log_file, log_data_custom)
    print(f"Check the custom log file at: {custom_log_file}")

    # To verify, you would typically open the CSV files and check their content.
    # For automated testing, you'd read the file back and assert its contents.
    # Example of how to read it back (optional, for verification):
    # if os.path.exists(example_log_file):
    #     with open(example_log_file, 'r', newline='', encoding='utf-8') as f_read:
    #         reader = csv.reader(f_read)
    #         print("\nContents of example_log_file:")
    #         for row in reader:
    #             print(row)

    # if os.path.exists(custom_log_file):
    #     with open(custom_log_file, 'r', newline='', encoding='utf-8') as f_read:
    #         reader = csv.reader(f_read)
    #         print("\nContents of custom_log_file:")
    #         for row in reader:
    #             print(row)
