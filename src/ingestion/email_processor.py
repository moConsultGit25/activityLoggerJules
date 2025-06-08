import email
from email import policy
from email.parser import BytesParser

def parse_eml_file(eml_file_path):
    """
    Parses an .eml file and extracts relevant information.

    Args:
        eml_file_path (str): The path to the .eml file.

    Returns:
        dict: A dictionary containing the extracted fields (sender, recipient, subject, body),
              or None if an error occurs.
    """
    try:
        with open(eml_file_path, 'rb') as fp:
            msg = BytesParser(policy=policy.default).parse(fp)

        sender = msg['from']
        recipient = msg['to']
        subject = msg['subject']

        body = None
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get('Content-Disposition'))

                if content_type == 'text/plain' and 'attachment' not in content_disposition:
                    body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                    break
            if body is None: # If no plain text part is found, try to get the first text part
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type.startswith('text/'):
                        body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                        break
        else:
            body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8')

        return {
            'sender': sender,
            'recipient': recipient,
            'subject': subject,
            'body': body
        }
    except FileNotFoundError:
        print(f"Error: File not found at {eml_file_path}")
        return None
    except Exception as e:
        print(f"Error parsing email file: {e}")
        return None

if __name__ == '__main__':
    # This is an example of how to use the function.
    # Create a dummy .eml file for testing.
    dummy_eml_content = """From: sender@example.com
To: recipient@example.com
Subject: Test Email
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"

This is the body of the test email.
"""
    with open("test_email.eml", "w") as f:
        f.write(dummy_eml_content)

    parsed_data = parse_eml_file("test_email.eml")
    if parsed_data:
        print("Email parsed successfully:")
        for key, value in parsed_data.items():
            print(f"{key.capitalize()}: {value}")

    # Test with a non-existent file
    parse_eml_file("non_existent_email.eml")

    # Clean up the dummy file
    import os
    os.remove("test_email.eml")
