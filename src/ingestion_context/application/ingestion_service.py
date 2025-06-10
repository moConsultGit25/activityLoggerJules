# src/ingestion_context/application/ingestion_service.py
from typing import List, Optional, Any, Dict # Added Any, Dict
from datetime import datetime, timezone, timedelta # For token expiry check

from ..domain.raw_email import RawEmail
from ..infrastructure.email_parser import parse_eml_file_to_dict
from ..infrastructure.graph_email_client import GraphEmailClient
from src.shared_kernel.events import dispatcher, EmailIngestedEvent

# For M365 user token handling
from src.auth_context.infrastructure.user_m365_token_repository import MongoUserM365TokenRepository
from src.auth_context.infrastructure.m365_oauth_client import M365OAuthClient
from src.auth_context.application.encryption_utils import decrypt_token, encrypt_token
from src.auth_context.domain.user_m365_token import UserM365Token

import uuid
import tempfile
import os
import asyncio
import logging # Added logger

logger = logging.getLogger(__name__)

class IngestionService:
    def __init__(self):
        logger.info("IngestionService initialized.")
        # GraphEmailClient is now instantiated per user request with their token, so no self.graph_email_client here.
        # M365OAuthClient is also instantiated on-demand when token refresh is needed.
        # MongoUserM365TokenRepository will be instantiated on-demand.

    def ingest_email_from_file(self, file_path: str, source_identifier_override: Optional[str] = None) -> RawEmail | None:
        logger.info(f"Attempting to ingest email from file: {file_path}")
        parsed_data = parse_eml_file_to_dict(file_path)
        if parsed_data is None:
            logger.error(f"Parsing failed for file: {file_path}")
            return None

        domain_message_id = parsed_data.get('message_id_header')
        if domain_message_id:
            domain_message_id = domain_message_id.strip('<>')
        else:
            domain_message_id = str(uuid.uuid4())

        try:
            email_body_for_event = parsed_data.get('body', '')
            raw_email = RawEmail(
                message_id=domain_message_id,
                sender=parsed_data.get('sender'),
                recipient=parsed_data.get('recipient'),
                subject=parsed_data.get('subject'),
                raw_content=parsed_data.get('raw_eml_content', ''),
                source_file_path=file_path
            )
            logger.info(f"Successfully created RawEmail domain object with message_id: {raw_email.message_id} from file {file_path}")

            event_source_id = source_identifier_override if source_identifier_override else (raw_email.source_file_path or raw_email.message_id)

            event = EmailIngestedEvent(
                raw_email_id=raw_email.message_id,
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
            logger.error(f"Error creating RawEmail object or publishing event for {file_path}: {e}", exc_info=True)
            return None

    async def _get_valid_m365_access_token(self, user_id: str, token_repo: MongoUserM365TokenRepository) -> Optional[str]:
        """Helper to retrieve and manage M365 access token, including refresh."""
        user_m365_token_obj = token_repo.get_by_user_id(user_id)
        if not user_m365_token_obj:
            logger.warning(f"No M365 token found for user_id: {user_id}. User needs to connect M365 account.")
            return None

        if not user_m365_token_obj.encrypted_refresh_token:
            logger.warning(f"No M365 refresh token found for user_id: {user_id}. User needs to re-authenticate M365.")
            return None # Or trigger re-auth

        # Check if access token is expired or nearing expiry (e.g., within next 5 minutes)
        # For simplicity, we will always try to get a fresh access token using the refresh token
        # for each batch operation. MSAL's ConfidentialClientApplication can cache tokens if needed,
        # but for user-delegated tokens in a server app, it's often safer to fetch new ones using refresh token.
        # A more optimized approach would store the access token and its expiry, and only refresh if needed.
        # However, the current UserM365Token doesn't store the access token itself.

        decrypted_refresh_token = decrypt_token(user_m365_token_obj.encrypted_refresh_token)
        if not decrypted_refresh_token:
            logger.error(f"User {user_id}: Failed to decrypt M365 refresh token or no refresh token present. Re-authentication required.")
            # It's good practice to remove the record if the refresh token is undecryptable or missing,
            # as it's no longer useful and might indicate corruption or an invalid state.
            token_repo.delete_by_user_id(user_id)
            logger.info(f"User {user_id}: Deleted M365 token record due to missing/undecryptable refresh token.")
            return None

        try:
            oauth_client = M365OAuthClient()
            token_response = oauth_client.acquire_token_by_refresh_token(refresh_token=decrypted_refresh_token)
        except ValueError as ve: # Catch M365OAuthClient init errors (missing env vars for client itself)
            logger.error(f"M365OAuthClient configuration error: {ve}")
            return None # Cannot proceed

        if token_response and "access_token" in token_response:
            current_access_token = token_response["access_token"]

            user_m365_token_obj.update_tokens(token_response, encrypt_token) # This updates expiry and potentially new refresh token
            if not token_repo.save(user_m365_token_obj):
                logger.error(f"User {user_id}: Failed to save updated M365 token to repository after refresh. Proceeding with current access token but refresh might fail next time.")
                # Depending on policy, could raise an error or just log. For now, log and proceed.

            logger.info(f"User {user_id}: Successfully obtained/refreshed M365 access token.")
            return current_access_token
        else:
            # Token acquisition failed (e.g., invalid_grant, interaction_required)
            error_details = token_response.get("error_description", "Unknown error") if token_response else "No response from token endpoint"
            logger.error(f"User {user_id}: Failed to acquire new M365 access token using refresh token. Error: {error_details}. Re-authentication likely required.")

            # If MSAL indicates the refresh token is invalid (e.g., "invalid_grant" can mean many things,
            # but often it's an issue with the refresh token itself being expired, revoked, or malformed).
            # Common AAD error codes for invalid refresh tokens: AADSTS70008, AADSTS700082, AADSTS70000 when grant is RT.
            # MSAL library might wrap these into a general "invalid_grant" or specific error types if using its exceptions.
            if token_response and token_response.get("error") in ["invalid_grant", "interaction_required", "unauthorized_client"]: # Add more specific MSAL errors if known
                logger.info(f"User {user_id}: Deleting invalid M365 token record due to refresh failure (error: {token_response.get('error')}).")
                token_repo.delete_by_user_id(user_id)
            return None # Signal that re-authentication by the user is needed


    async def process_emails_from_target_mailbox(self, user_id: str, max_emails: int = 10, mark_as_read: bool = False) -> List[str]:
        logger.info(f"IngestionService: Starting M365 mailbox processing for user_id: {user_id} (max: {max_emails}).")
        processed_raw_email_ids: List[str] = []

        token_repo = MongoUserM365TokenRepository() # Instantiate repository
        current_access_token = await self._get_valid_m365_access_token(user_id, token_repo)

        if not current_access_token:
            logger.warning(f"Could not obtain valid M365 access token for user_id: {user_id}. Aborting mailbox processing.")
            return processed_raw_email_ids

        try:
            graph_client = GraphEmailClient() # This client now just makes API calls with a provided token
        except Exception as e_graph_init:
            logger.error(f"Failed to initialize GraphEmailClient (unexpected): {e_graph_init}", exc_info=True)
            return processed_raw_email_ids


        unread_messages = await graph_client.get_unread_emails(access_token=current_access_token, top=max_emails)
        if unread_messages is None:
            logger.error(f"Failed to retrieve unread emails from Graph for user_id: {user_id}.")
            return processed_raw_email_ids

        if not unread_messages:
            logger.info(f"No unread emails found in the target mailbox for user_id: {user_id}.")
            return processed_raw_email_ids

        logger.info(f"Found {len(unread_messages)} unread emails to process for user_id: {user_id}.")
        for message_meta in unread_messages:
            message_id_graph = message_meta.get('id')
            if not message_id_graph:
                logger.warning("Found message metadata without an ID. Skipping.")
                continue

            logger.info(f"Processing Graph message ID: {message_id_graph}, Subject: '{message_meta.get('subject', 'N/A')}' for user_id: {user_id}")
            mime_content = await graph_client.get_mime_content(access_token=current_access_token, message_id=message_id_graph)

            if mime_content:
                temp_file_path = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".eml", mode="w", encoding="utf-8") as tmp_file:
                        tmp_file.write(mime_content)
                        temp_file_path = tmp_file.name

                    logger.debug(f"MIME content for message {message_id_graph} saved to temp file: {temp_file_path}")

                    # Use Graph Message-ID or WebLink as the source_identifier_override for better tracking
                    source_identifier = message_meta.get('webLink') or f"graph://user/{user_id}/message/{message_id_graph}"

                    raw_email_obj = self.ingest_email_from_file(temp_file_path, source_identifier_override=source_identifier)

                    if raw_email_obj:
                        processed_raw_email_ids.append(raw_email_obj.message_id)
                        logger.info(f"Successfully ingested email from Graph. Domain ID: {raw_email_obj.message_id}, Graph ID: {message_id_graph}, User ID: {user_id}")

                        if mark_as_read:
                           await graph_client.mark_email_as_read(access_token=current_access_token, message_id=message_id_graph)
                    else:
                        logger.error(f"Failed to ingest EML content from Graph message ID {message_id_graph} for user_id: {user_id}.")

                except Exception as e_proc:
                    logger.error(f"Error during processing of Graph message {message_id_graph} for user_id: {user_id}: {e_proc}", exc_info=True)
                finally:
                    if temp_file_path and os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
            else:
                logger.warning(f"Could not retrieve MIME content for Graph message ID {message_id_graph} for user_id: {user_id}.")

        logger.info(f"Finished M365 mailbox processing for user_id: {user_id}. Processed {len(processed_raw_email_ids)} emails successfully.")
        return processed_raw_email_ids


# Updated Example Usage for IngestionService
async def main_service_test():
    # (Setup dummy handler as before)
    def _test_local_email_ingested_handler(event: EmailIngestedEvent):
        print(f"\n[LOCAL TEST HANDLER] Received EmailIngestedEvent:")
        print(f"  Raw Email ID: {event.raw_email_id}, Subject: {event.subject}, Source: {event.source_identifier}")
    dispatcher.subscribe(EmailIngestedEvent, _test_local_email_ingested_handler)

    service = IngestionService()

    # --- Test file ingestion (remains the same) ---
    print("\n--- IngestionService File Ingestion Test ---")
    # ... (file ingestion test code as before) ...

    # --- Test Graph ingestion (now requires a user_id and stored M365 token) ---
    print("\n--- IngestionService User M365 Mailbox Processing Test ---")

    # FOR THIS TEST TO WORK:
    # 1. Ensure M365_TOKEN_ENCRYPTION_KEY is set in your environment.
    # 2. You need a user_id for whom a valid (encrypted) refresh token is stored in MongoDB
    #    in the 'user_m365_tokens' collection (auth_db_default DB).
    #    This token would have been obtained via the M365 OAuth flow (e.g., API endpoints).
    # 3. The Azure AD app (identified by AZURE_CLIENT_ID etc. in M365OAuthClient) must have
    #    the necessary delegated permissions (Mail.Read, User.Read, offline_access).

    test_user_for_graph_sync = os.environ.get("TEST_USER_ID_WITH_M365_TOKEN") # Set this env var to a user_id with a token

    if not os.environ.get("M365_TOKEN_ENCRYPTION_KEY"):
        print("Skipping Graph user mailbox test: M365_TOKEN_ENCRYPTION_KEY is not set.")
    elif not test_user_for_graph_sync:
        print("Skipping Graph user mailbox test: TEST_USER_ID_WITH_M365_TOKEN env var not set.")
        print("  (This test needs a user_id that has previously connected their M365 account).")
    elif not all(os.environ.get(v) for v in ["AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID", "M365_REDIRECT_URI"]):
        print("Skipping Graph user mailbox test: Azure AD M365OAuthClient credentials not fully set in environment.")
    else:
        print(f"Attempting to process M365 emails for user_id: {test_user_for_graph_sync} (ensure test emails are unread)...")
        try:
            processed_graph_ids = await service.process_emails_from_target_mailbox(
                user_id=test_user_for_graph_sync,
                max_emails=2,
                mark_as_read=False # Set to True to test marking as read
            )
            if processed_graph_ids is not None: # Returns empty list if no emails or error, not None unless major issue
                print(f"Successfully processed {len(processed_graph_ids)} emails from Graph for user {test_user_for_graph_sync}: {processed_graph_ids}")
            else: # Should ideally not be None, but rather an empty list or raise exception
                print(f"M365 mailbox processing for user {test_user_for_graph_sync} returned None or failed. Check logs.")
        except Exception as e_graph_test:
            print(f"Error during Graph mailbox processing test for user {test_user_for_graph_sync}: {e_graph_test}", exc_info=True)

    print("\n--- End of IngestionService Demonstrations ---")

if __name__ == '__main__':
    # Basic logging for demo if no other config
    if not logging.getLogger().handlers:
         logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # To run this: python -m src.ingestion_context.application.ingestion_service
    asyncio.run(main_service_test())
