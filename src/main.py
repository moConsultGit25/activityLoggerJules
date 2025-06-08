import argparse
import datetime
import os
import uuid # For generating unique email IDs if not present in EML

from ingestion.email_processor import parse_eml_file
from summarization.summarizer import summarize_text
from disposition.classifier import classify_email_content
from logging.logger import log_activity, DEFAULT_LOG_DIR

def main_process(email_file_path, log_file_path):
    """
    Orchestrates the processing of a single email file.
    """
    print(f"Processing email file: {email_file_path}")

    parsed_email = parse_eml_file(email_file_path)

    if not parsed_email:
        print(f"Failed to parse email file: {email_file_path}")
        return

    email_id = parsed_email.get('message-id') or str(uuid.uuid4()) # Use EML Message-ID or generate one
    sender = parsed_email.get('sender')
    recipient = parsed_email.get('recipient')
    subject = parsed_email.get('subject', '') # Default to empty string if no subject
    body = parsed_email.get('body', '')    # Default to empty string if no body

    if not body and subject: # If body is empty, try to use subject for summarization/classification
        print("Email body is empty, using subject for content analysis.")
        content_to_analyze = subject
    elif not body and not subject:
        print("Email body and subject are empty. Cannot process further.")
        # Optionally log this minimal info
        activity_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'email_id': email_id,
            'sender': sender,
            'recipient': recipient,
            'subject': subject,
            'summary': 'Empty email content',
            'disposition': 'Unprocessable',
            'original_file_path': email_file_path
        }
        log_activity(log_file_path, activity_data)
        return
    else:
        content_to_analyze = body

    summary = summarize_text(content_to_analyze, num_sentences=2)

    # Classify based on combined subject and body for more context, if available
    classification_text = subject + " " + body if subject and body else content_to_analyze
    disposition = classify_email_content(classification_text)

    activity_data = {
        'timestamp': datetime.datetime.now().isoformat(),
        'email_id': email_id,
        'sender': sender,
        'recipient': recipient,
        'subject': subject,
        'summary': summary,
        'disposition': disposition,
        'original_file_path': email_file_path
    }

    log_activity(log_file_path, activity_data)
    print(f"Email processed. Sender: {sender}, Subject: {subject}, Disposition: {disposition}")
    print(f"Activity logged to: {log_file_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Process and log email files.")
    parser.add_argument("--email-file", required=True, help="Path to the .eml file to process.")
    parser.add_argument("--log-file",
                        default=os.path.join(DEFAULT_LOG_DIR, "activity_log.csv"),
                        help=f"Path to the CSV log file. Defaults to 'data/activity_log.csv'.")

    args = parser.parse_args()

    # Ensure the directory for the log file exists, if it's not the default which logger handles
    log_dir = os.path.dirname(args.log_file)
    if log_dir and not os.path.exists(log_dir) :
        try:
            os.makedirs(log_dir)
            print(f"Created log directory: {log_dir}")
        except OSError as e:
            print(f"Error creating log directory {log_dir}: {e}")
            # Decide if to exit or let log_activity handle it
            # For now, let log_activity attempt to create it if it's the default path

    if not os.path.isfile(args.email_file):
        print(f"Error: Email file not found at {args.email_file}")
    else:
        main_process(args.email_file, args.log_file)
