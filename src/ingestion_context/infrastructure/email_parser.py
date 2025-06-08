# src/ingestion_context/infrastructure/email_parser.py
import email
from email import policy
from email.parser import BytesParser
from typing import Dict, Optional, Any # For type hinting

def parse_eml_file_to_dict(eml_file_path: str) -> Optional[Dict[str, Any]]:
    """
    Parses an .eml file and extracts relevant information into a dictionary.

    Args:
        eml_file_path (str): The path to the .eml file.

    Returns:
        dict: A dictionary containing the extracted fields (sender, recipient, subject, body, message_id),
              or None if an error occurs.
    """
    try:
        with open(eml_file_path, 'rb') as fp:
            msg = BytesParser(policy=policy.default).parse(fp)

        sender = msg['from']
        recipient = msg['to']
        subject = msg['subject']
        message_id_header = msg['message-id'] # Extract Message-ID header

        body = None
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get('Content-Disposition'))

                # Prefer plain text part that is not an attachment
                if content_type == 'text/plain' and 'attachment' not in content_disposition:
                    try:
                        body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                    except (UnicodeDecodeError, AttributeError) as e:
                        print(f"Warning: Could not decode plain text part for {eml_file_path} due to {e}, trying as raw bytes.")
                        # Fallback or specific handling for undecodable content if necessary
                        body = str(part.get_payload(decode=True)) # Represent as string of bytes
                    break
            if body is None: # If no plain text part is found, try to get the first text part
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type.startswith('text/'):
                        try:
                            body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                        except (UnicodeDecodeError, AttributeError) as e:
                            print(f"Warning: Could not decode generic text part for {eml_file_path} due to {e}.")
                            body = str(part.get_payload(decode=True))
                        break
        else: # Not multipart
            try:
                body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8')
            except (UnicodeDecodeError, AttributeError) as e:
                print(f"Warning: Could not decode non-multipart body for {eml_file_path} due to {e}.")
                body = str(msg.get_payload(decode=True))

        # It's also useful to return the full raw content of the EML for storage if needed
        # Rewind file pointer and read raw content as string (or bytes)
        fp.seek(0)
        raw_eml_content = fp.read() # Read as bytes
        try:
            raw_eml_content_str = raw_eml_content.decode('utf-8', errors='replace')
        except UnicodeDecodeError: # Should not happen if errors='replace'
             raw_eml_content_str = raw_eml_content.decode('latin-1', errors='replace') # Fallback


        return {
            'sender': sender,
            'recipient': recipient,
            'subject': subject,
            'body': body, # This is the extracted plain text body
            'message_id_header': message_id_header, # Original Message-ID from EML
            'raw_eml_content': raw_eml_content_str # Full raw EML content as string
        }
    except FileNotFoundError:
        print(f"Error: Email source file not found at {eml_file_path}")
        return None
    except Exception as e:
        print(f"Error parsing email file {eml_file_path}: {e}")
        return None

# Example (can be removed or kept for direct testing of the parser)
if __name__ == '__main__':
    # Create a dummy .eml file for testing.
    dummy_eml_path = "temp_parser_test_email.eml"
    dummy_eml_content = """From: sender_parser@example.com
To: recipient_parser@example.com
Subject: Parser Test Email
Message-ID: <parser.test.123@example.com>
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"

This is the body of the parser test email.
It has some simple text.
"""
    with open(dummy_eml_path, "w", encoding='utf-8') as f:
        f.write(dummy_eml_content)

    print(f"Testing parser with: {dummy_eml_path}")
    parsed_dict = parse_eml_file_to_dict(dummy_eml_path)
    if parsed_dict:
        print("\nEmail parsed successfully by infrastructure parser:")
        print(f"  Sender: {parsed_dict.get('sender')}")
        print(f"  Recipient: {parsed_dict.get('recipient')}")
        print(f"  Subject: {parsed_dict.get('subject')}")
        print(f"  Message-ID Header: {parsed_dict.get('message_id_header')}")
        print(f"  Body Snippet: {parsed_dict.get('body', '')[:50]}...")
        # print(f"  Raw Content Snippet: {parsed_dict.get('raw_eml_content', '')[:100]}...")
    else:
        print("Parsing failed.")

    import os
    os.remove(dummy_eml_path)
