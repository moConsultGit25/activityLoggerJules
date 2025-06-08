# src/ingestion_context/application/ingestion_service.py
from ..domain.raw_email import RawEmail
from ..infrastructure.email_parser import parse_eml_file_to_dict
from src.shared_kernel.events import dispatcher, EmailIngestedEvent # Import dispatcher and event

import datetime # Already present, but ensure it's used if needed for event
import uuid

class IngestionService:
    """
    Application service for the Ingestion Context.
    Orchestrates the process of ingesting raw emails, creating domain objects,
    and publishing domain events.
    """
    def __init__(self):
        print("IngestionService initialized.")

    def ingest_email_from_file(self, file_path: str) -> RawEmail | None:
        """
        Processes an email file, creates a RawEmail domain object,
        and publishes an EmailIngestedEvent.

        Args:
            file_path (str): The path to the .eml file.

        Returns:
            RawEmail | None: The RawEmail domain object if successful, else None.
        """
        print(f"Attempting to ingest email from file: {file_path}")

        parsed_data = parse_eml_file_to_dict(file_path)

        if parsed_data is None:
            print(f"Parsing failed for file: {file_path}")
            return None

        domain_message_id = parsed_data.get('message_id_header')
        if domain_message_id:
            domain_message_id = domain_message_id.strip('<>')
        else:
            domain_message_id = str(uuid.uuid4())

        try:
            # The 'body' from parsed_data is the extracted plain text body.
            # The 'raw_eml_content' from parsed_data is the full EML content.
            # RawEmail.raw_content will store the full EML.
            # EmailIngestedEvent.body will store the plain text body for analysis.

            email_body_for_event = parsed_data.get('body', '') # Use parsed plain text body for event

            raw_email = RawEmail(
                message_id=domain_message_id,
                sender=parsed_data.get('sender'), # Let None propagate if not present
                recipient=parsed_data.get('recipient'),
                subject=parsed_data.get('subject'),
                raw_content=parsed_data.get('raw_eml_content', ''),
                source_file_path=file_path
                # received_at is set by RawEmail's default factory
            )

            print(f"Successfully created RawEmail domain object with message_id: {raw_email.message_id}")

            # Publish EmailIngestedEvent
            # Ensure all fields required by the (revised) EmailIngestedEvent are populated.
            event = EmailIngestedEvent(
                raw_email_id=raw_email.message_id,
                sender=raw_email.sender,
                recipient=raw_email.recipient,
                subject=raw_email.subject,
                body=email_body_for_event, # Pass the cleaner body for analysis
                received_at=raw_email.received_at, # This comes from RawEmail's default factory
                source_identifier=raw_email.source_file_path or raw_email.message_id # Prefer file path if avail
            )
            dispatcher.publish(event) # Use the global dispatcher instance

            # In a real application, repository save would happen here:
            # self.raw_email_repository.save(raw_email)

            return raw_email

        except Exception as e:
            print(f"Error creating RawEmail domain object or publishing event for {file_path}: {e}")
            return None

# Example usage for demonstration or basic testing
if __name__ == '__main__':
    # --- Setup a dummy handler for EmailIngestedEvent for this test ---
    # This is to see the event being published. In a real app, handlers are in other contexts.
    def _test_local_email_ingested_handler(event: EmailIngestedEvent):
        print(f"\n[LOCAL TEST HANDLER] Received EmailIngestedEvent:")
        print(f"  Raw Email ID: {event.raw_email_id}")
        print(f"  Subject: {event.subject}")
        print(f"  Body for analysis (snippet): {event.body[:100] if event.body else 'N/A'}...")
        print(f"  Source Identifier: {event.source_identifier}")

    dispatcher.subscribe(EmailIngestedEvent, _test_local_email_ingested_handler)
    # --- End of dummy handler setup ---

    dummy_service_eml_path = "dummy_service_test_email_for_event.eml"
    dummy_eml_content_for_service = """From: event_sender@example.com
To: event_recipient@example.com
Subject: Service Ingestion Event Test
Message-ID: <service.event.test.789@example.com>
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"

This is the body of the email processed by IngestionService for event publishing.
It's designed to trigger an EmailIngestedEvent.
"""
    with open(dummy_service_eml_path, "w", encoding='utf-8') as f_dummy:
        f_dummy.write(dummy_eml_content_for_service)

    print("\n--- IngestionService Event Publishing Demonstration ---")
    service = IngestionService()

    print(f"\nAttempting to ingest: {dummy_service_eml_path}")
    ingested_email_object = service.ingest_email_from_file(dummy_service_eml_path)

    if ingested_email_object:
        print("\nIngested Email Domain Object (from service return):")
        print(f"  Message ID: {ingested_email_object.message_id}")
        print(f"  Sender: {ingested_email_object.sender}")
    else:
        print(f"Ingestion failed for {dummy_service_eml_path}")

    # Clean up dummy file
    import os
    if os.path.exists(dummy_service_eml_path):
        os.remove(dummy_service_eml_path)

    # Unsubscribe the local test handler if necessary, though for a simple script run it's not critical
    # dispatcher._handlers[EmailIngestedEvent].remove(_test_local_email_ingested_handler) # Illustrative
    print("\n--- End of IngestionService Event Demonstration ---")
