# src/ingestion_context/application/ingestion_service.py
from ..domain.raw_email import RawEmail
from ..infrastructure.email_parser import parse_eml_file_to_dict
from ..infrastructure.graph_email_client import GraphEmailClient # New import
from src.shared_kernel.events import dispatcher, EmailIngestedEvent

import datetime
import uuid
import tempfile # For NamedTemporaryFile
import os # For os.remove
import asyncio # For running async graph client methods

class IngestionService:
    """
    Application service for the Ingestion Context.
    Orchestrates ingestion from files or Microsoft Graph, creates domain objects,
    and publishes domain events.
    """
    def __init__(self):
        print("IngestionService initialized.")
        self.graph_email_client: GraphEmailClient | None = None # Initialize lazily or based on config

    def _initialize_graph_client(self) -> bool:
        if self.graph_email_client is None:
            try:
                self.graph_email_client = GraphEmailClient()
                print("GraphEmailClient initialized successfully within IngestionService.")
                return True
            except ValueError as e: # Catches missing env vars from GraphEmailClient constructor
                print(f"IngestionService Error: Failed to initialize GraphEmailClient: {e}")
                print("Ensure AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID, and GRAPH_TARGET_USER_ID are set.")
                return False
        return True # Already initialized

    def ingest_email_from_file(self, file_path: str, source_identifier_override: Optional[str] = None) -> RawEmail | None:
        """
        Processes an email file, creates a RawEmail domain object,
        and publishes an EmailIngestedEvent.

        Args:
            file_path (str): The path to the .eml file.
            source_identifier_override (Optional[str]): If provided, use this as the source_identifier
                                                       for the event instead of file_path. Useful for Graph ingestion
                                                       where original message ID is more relevant.
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
            domain_message_id = str(uuid.uuid4()) # Fallback if no Message-ID in EML

        try:
            email_body_for_event = parsed_data.get('body', '')
            raw_email = RawEmail(
                message_id=domain_message_id, # Use EML Message-ID or generated UUID
                sender=parsed_data.get('sender'),
                recipient=parsed_data.get('recipient'),
                subject=parsed_data.get('subject'),
                raw_content=parsed_data.get('raw_eml_content', ''),
                source_file_path=file_path # Keep track of the temp file path for file-based ingestion
                # received_at is set by RawEmail's default factory
            )
            print(f"Successfully created RawEmail domain object with message_id: {raw_email.message_id}")

            event_source_id = source_identifier_override if source_identifier_override else (raw_email.source_file_path or raw_email.message_id)

            event = EmailIngestedEvent(
                raw_email_id=raw_email.message_id, # This is our internal domain ID
                sender=raw_email.sender,
                recipient=raw_email.recipient,
                subject=raw_email.subject,
                body=email_body_for_event,
                received_at=raw_email.received_at,
                source_identifier=event_source_id
            )
            dispatcher.publish(event)
            return raw_email
        except Exception as e:
            print(f"Error creating RawEmail object or publishing event for {file_path}: {e}")
            return None

    async def process_emails_from_target_mailbox(self, max_emails: int = 10, mark_as_read: bool = False) -> List[str]:
        """
        Fetches unread emails from Microsoft Graph, processes them, and optionally marks them as read.
        """
        print(f"IngestionService: Starting processing of emails from target mailbox (max: {max_emails}).")
        processed_email_ids: List[str] = []

        if not self._initialize_graph_client() or self.graph_email_client is None:
            print("IngestionService: GraphEmailClient not available. Aborting mailbox processing.")
            return processed_email_ids

        unread_messages = await self.graph_email_client.get_unread_emails(top=max_emails)
        if unread_messages is None: # Error occurred in client
            print("IngestionService: Failed to retrieve unread emails from Graph.")
            return processed_email_ids

        if not unread_messages:
            print("IngestionService: No unread emails found in the target mailbox.")
            return processed_email_ids

        print(f"IngestionService: Found {len(unread_messages)} unread emails to process.")
        for message_meta in unread_messages:
            message_id_graph = message_meta.get('id')
            if not message_id_graph:
                print("IngestionService: Found message metadata without an ID. Skipping.")
                continue

            print(f"IngestionService: Processing message ID (Graph): {message_id_graph}, Subject: '{message_meta.get('subject', 'N/A')}'")
            mime_content = await self.graph_email_client.get_mime_content(message_id_graph)

            if mime_content:
                temp_file_path = None
                try:
                    # Save MIME content to a temporary .eml file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".eml", mode="w", encoding="utf-8") as tmp_file:
                        tmp_file.write(mime_content)
                        temp_file_path = tmp_file.name

                    print(f"IngestionService: MIME content for message {message_id_graph} saved to temp file: {temp_file_path}")

                    # Process this temporary EML file using existing logic
                    # Pass message_id_graph as source_identifier_override for better tracking
                    raw_email_obj = self.ingest_email_from_file(temp_file_path, source_identifier_override=f"graph://{message_id_graph}")

                    if raw_email_obj:
                        processed_email_ids.append(raw_email_obj.message_id)
                        print(f"IngestionService: Successfully ingested email from Graph. Domain ID: {raw_email_obj.message_id}, Graph ID: {message_id_graph}")

                        if mark_as_read and self.graph_email_client: # Check graph_client again just in case
                           await self.graph_email_client.mark_email_as_read(message_id_graph)
                    else:
                        print(f"IngestionService: Failed to ingest EML content from Graph message ID {message_id_graph}.")

                except Exception as e_proc:
                    print(f"IngestionService: Error during processing of Graph message {message_id_graph}: {e_proc}")
                finally:
                    if temp_file_path and os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                        print(f"IngestionService: Cleaned up temp file: {temp_file_path}")
            else:
                print(f"IngestionService: Could not retrieve MIME content for message ID {message_id_graph}.")

        print(f"IngestionService: Finished processing mailbox. Processed {len(processed_email_ids)} emails successfully.")
        return processed_email_ids


# Updated Example Usage for IngestionService
async def main_service_test(): # Renamed to avoid conflict if other files use 'main'
    # --- Setup a dummy handler for EmailIngestedEvent for this test ---
    def _test_local_email_ingested_handler(event: EmailIngestedEvent):
        print(f"\n[LOCAL TEST HANDLER] Received EmailIngestedEvent:")
        print(f"  Raw Email ID: {event.raw_email_id}")
        print(f"  Subject: {event.subject}")
        print(f"  Source Identifier: {event.source_identifier}")
    dispatcher.subscribe(EmailIngestedEvent, _test_local_email_ingested_handler)

    service = IngestionService()

    # --- Test file ingestion ---
    print("\n--- IngestionService File Ingestion Test ---")
    dummy_eml_path = "dummy_service_test_email_for_event.eml"
    # (Content for dummy_eml_path as in previous version of this file)
    with open(dummy_eml_path, "w", encoding='utf-8') as f_dummy:
         f_dummy.write("From: file_sender@example.com\nSubject: File Test\n\nBody for file test.")
    ingested_file_email = service.ingest_email_from_file(dummy_eml_path)
    if ingested_file_email: print(f"File ingestion result ID: {ingested_file_email.message_id}")
    if os.path.exists(dummy_eml_path): os.remove(dummy_eml_path)


    # --- Test Graph ingestion (requires environment variables to be set) ---
    print("\n--- IngestionService Graph Mailbox Processing Test ---")
    # Check if graph client related env vars are likely set (basic check)
    if os.environ.get("AZURE_CLIENT_ID") and os.environ.get("GRAPH_TARGET_USER_ID"):
        print("Attempting to process emails from Graph mailbox (ensure test emails are present and unread)...")
        processed_graph_ids = await service.process_emails_from_target_mailbox(max_emails=2, mark_as_read=False) # Set mark_as_read=True to test that feature
        if processed_graph_ids:
            print(f"Successfully processed {len(processed_graph_ids)} emails from Graph: {processed_graph_ids}")
        else:
            print("No emails processed from Graph, or an error occurred. Check logs and ensure target mailbox has unread emails.")
    else:
        print("Skipping Graph mailbox processing test as required environment variables (AZURE_CLIENT_ID, etc.) are not set.")

    print("\n--- End of IngestionService Demonstrations ---")

if __name__ == '__main__':
    # To run this: python -m src.ingestion_context.application.ingestion_service
    # Ensure you are in the project root directory.
    asyncio.run(main_service_test())
