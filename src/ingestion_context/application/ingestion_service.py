# src/ingestion_context/application/ingestion_service.py
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta

from ..domain.raw_email import RawEmail
from ..infrastructure.email_parser import parse_eml_file_to_dict
from ..infrastructure.graph_email_client import GraphEmailClient
from ..infrastructure.gmail_api_client import GmailApiClient # New
from src.shared_kernel.events import dispatcher, EmailIngestedEvent

# For M365 user token handling
from src.auth_context.infrastructure.user_m365_token_repository import MongoUserM365TokenRepository
from src.auth_context.infrastructure.m365_oauth_client import M365OAuthClient
from src.auth_context.application.encryption_utils import decrypt_token, encrypt_token # Shared
from src.auth_context.domain.user_m365_token import UserM365Token

# For Google user token handling (New)
from src.auth_context.infrastructure.user_google_token_repository import MongoUserGoogleTokenRepository
from src.auth_context.infrastructure.google_oauth_client import GoogleOAuthClient
from src.auth_context.domain.user_google_token import UserGoogleToken
from google.oauth2.credentials import Credentials as GoogleCredentials # New

import uuid
import tempfile
import os
import asyncio
import logging

logger = logging.getLogger(__name__)

class IngestionService:
    def __init__(self):
        logger.info("IngestionService initialized.")
        # Clients and Repositories are instantiated on-demand within methods.

    def ingest_email_from_file(self, file_path: str, source_identifier_override: Optional[str] = None) -> RawEmail | None:
        # (Implementation as before)
        logger.info(f"Attempting to ingest email from file: {file_path}")
        parsed_data = parse_eml_file_to_dict(file_path)
        if parsed_data is None:
            logger.error(f"Parsing failed for file: {file_path}")
            return None
        domain_message_id = parsed_data.get('message_id_header','').strip('<>') or str(uuid.uuid4())
        try:
            email_body_for_event = parsed_data.get('body', '')
            raw_email = RawEmail(
                message_id=domain_message_id, sender=parsed_data.get('sender'),
                recipient=parsed_data.get('recipient'), subject=parsed_data.get('subject'),
                raw_content=parsed_data.get('raw_eml_content', ''), source_file_path=file_path
            )
            logger.info(f"Created RawEmail ID: {raw_email.message_id} from file {file_path}")
            event_source_id = source_identifier_override or raw_email.source_file_path or raw_email.message_id
            event = EmailIngestedEvent(
                raw_email_id=raw_email.message_id, sender=raw_email.sender, recipient=raw_email.recipient,
                subject=raw_email.subject, body=email_body_for_event, received_at=raw_email.received_at,
                source_identifier=event_source_id
            )
            dispatcher.publish(event)
            return raw_email
        except Exception as e:
            logger.error(f"Error creating RawEmail or publishing event for {file_path}: {e}", exc_info=True)
            return None

    async def _get_valid_m365_access_token(self, user_id: str, token_repo: MongoUserM365TokenRepository) -> Optional[str]:
        # (Implementation as before, with refined error handling)
        user_m365_token_obj = token_repo.get_by_user_id(user_id)
        if not user_m365_token_obj or not user_m365_token_obj.encrypted_refresh_token:
            logger.warning(f"M365 token/refresh_token not found for user_id: {user_id}. Deleting record if exists.")
            if user_m365_token_obj: token_repo.delete_by_user_id(user_id)
            return None
        decrypted_rf = decrypt_token(user_m365_token_obj.encrypted_refresh_token)
        if not decrypted_rf:
            logger.error(f"User {user_id}: Failed to decrypt M365 refresh token. Deleting record.")
            token_repo.delete_by_user_id(user_id)
            return None
        try:
            oauth_client = M365OAuthClient()
            token_response = oauth_client.acquire_token_by_refresh_token(refresh_token=decrypted_rf)
        except ValueError as ve: logger.error(f"M365OAuthClient config error: {ve}"); return None
        if token_response and "access_token" in token_response:
            user_m365_token_obj.update_tokens(token_response, encrypt_token)
            if not token_repo.save(user_m365_token_obj):
                 logger.error(f"User {user_id}: Failed to save updated M365 token post-refresh.")
            logger.info(f"User {user_id}: M365 access token obtained/refreshed.")
            return token_response["access_token"]
        else:
            err_desc = token_response.get("error_description", "Unknown error") if token_response else "No response"
            logger.error(f"User {user_id}: Failed to refresh M365 token. Error: {err_desc}.")
            if token_response and token_response.get("error") in ["invalid_grant", "interaction_required", "unauthorized_client"]:
                logger.info(f"User {user_id}: Deleting invalid M365 token due to refresh failure.")
                token_repo.delete_by_user_id(user_id)
            return None

    async def process_emails_from_target_mailbox(self, user_id: str, max_emails: int = 10, mark_as_read: bool = False) -> List[str]:
        # (Implementation as before, using _get_valid_m365_access_token)
        logger.info(f"Starting M365 mailbox processing for user_id: {user_id} (max: {max_emails}).")
        processed_ids: List[str] = []
        token_repo = MongoUserM365TokenRepository()
        access_token = await self._get_valid_m365_access_token(user_id, token_repo)
        if not access_token: return processed_ids
        try: graph_client = GraphEmailClient()
        except Exception as e: logger.error(f"GraphEmailClient init error: {e}", exc_info=True); return processed_ids

        messages = await graph_client.get_unread_emails(access_token=access_token, top=max_emails)
        if messages is None: return processed_ids
        if not messages: logger.info(f"No M365 unread emails for user {user_id}."); return processed_ids

        logger.info(f"Found {len(messages)} M365 unread emails for user {user_id}.")
        for msg_meta in messages:
            msg_id_graph = msg_meta.get('id')
            if not msg_id_graph: continue
            mime = await graph_client.get_mime_content(access_token=access_token, message_id=msg_id_graph)
            if mime:
                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".eml", mode="w", encoding="utf-8") as tmp:
                        tmp.write(mime); tmp_path = tmp.name
                    source_id = msg_meta.get('webLink') or f"graph://user/{user_id}/message/{msg_id_graph}"
                    raw_email = self.ingest_email_from_file(tmp_path, source_identifier_override=source_id)
                    if raw_email:
                        processed_ids.append(raw_email.message_id)
                        if mark_as_read: await graph_client.mark_email_as_read(access_token, msg_id_graph)
                finally:
                    if tmp_path and os.path.exists(tmp_path): os.remove(tmp_path)
        logger.info(f"Finished M365 processing for user {user_id}. Processed {len(processed_ids)} emails.")
        return processed_ids

    async def _get_valid_google_access_token_details(self, user_id: str, token_repo: MongoUserGoogleTokenRepository) -> Optional[Dict[str, Any]]:
        """Helper to retrieve and manage Google access token, including refresh. Returns token response dict."""
        user_google_token_obj = token_repo.get_by_user_id(user_id)
        if not user_google_token_obj or not user_google_token_obj.encrypted_refresh_token:
            logger.warning(f"Google token/refresh_token not found for user_id: {user_id}. Deleting record if exists.")
            if user_google_token_obj: token_repo.delete_by_user_id(user_id)
            return None
        decrypted_rf = decrypt_token(user_google_token_obj.encrypted_refresh_token)
        if not decrypted_rf:
            logger.error(f"User {user_id}: Failed to decrypt Google refresh token. Deleting record.")
            token_repo.delete_by_user_id(user_id)
            return None
        try:
            oauth_client = GoogleOAuthClient()
            # The refresh_access_token method in GoogleOAuthClient returns a dict like the original token response
            token_response = oauth_client.refresh_access_token(refresh_token=decrypted_rf)
        except ValueError as ve: logger.error(f"GoogleOAuthClient config error: {ve}"); return None

        if token_response and "access_token" in token_response:
            user_google_token_obj.update_tokens(token_response, encrypt_token) # Handles new refresh_token if any
            if not token_repo.save(user_google_token_obj):
                 logger.error(f"User {user_id}: Failed to save updated Google token post-refresh.")
            logger.info(f"User {user_id}: Google access token obtained/refreshed.")
            return token_response # Contains new access_token, expiry, potentially new (rarely) refresh_token
        else:
            err_desc = "Unknown error or no access_token in response"
            if token_response and token_response.get("error"): # google-auth lib might raise RefreshError before this
                err_desc = token_response.get("error_description", token_response.get("error"))
            logger.error(f"User {user_id}: Failed to refresh Google token. Error: {err_desc}.")
            if token_response and token_response.get("error") in ["invalid_grant", "revoked_token", "invalid_token"]: # Example errors
                logger.info(f"User {user_id}: Deleting invalid Google token due to refresh failure.")
                token_repo.delete_by_user_id(user_id)
            return None

    async def process_user_google_mailbox(self, user_id: str, max_emails: int = 10, mark_as_read: bool = True) -> List[str]:
        logger.info(f"Starting Google Gmail processing for user_id: {user_id} (max: {max_emails}).")
        processed_raw_email_ids: List[str] = []
        google_token_repo = MongoUserGoogleTokenRepository()

        token_details = await self._get_valid_google_access_token_details(user_id, google_token_repo)
        if not token_details or not token_details.get("access_token"):
            logger.warning(f"Could not obtain valid Google access token for user_id: {user_id}. Aborting Gmail processing.")
            return processed_raw_email_ids

        current_access_token = token_details["access_token"]
        # Create GoogleCredentials object for GmailApiClient
        # GoogleOAuthClient already has client_id, client_secret, token_uri.
        # We need to ensure scopes are correctly passed if not already part of credentials.
        # The refresh_token used here is the decrypted one, which is fine as Credentials object is in-memory.
        google_creds = GoogleCredentials(
            token=current_access_token,
            refresh_token=decrypt_token(google_token_repo.get_by_user_id(user_id).encrypted_refresh_token), # Get latest RT
            token_uri=GoogleOAuthClient().client_config["web"]["token_uri"], # From a new instance or pass config
            client_id=GoogleOAuthClient().client_id,
            client_secret=GoogleOAuthClient().client_secret,
            scopes=google_token_repo.get_by_user_id(user_id).scopes # Use stored scopes
        )
        # Update expiry on credentials object
        if token_details.get("expires_at_datetime"):
            google_creds.expiry = token_details["expires_at_datetime"]


        try: gmail_api_client = GmailApiClient(credentials=google_creds)
        except ValueError as ve: logger.error(f"GmailApiClient init error: {ve}"); return processed_raw_email_ids

        # Gmail API calls are blocking, so wrap them with asyncio.to_thread
        message_list = await asyncio.to_thread(gmail_api_client.list_messages, query="is:unread", max_results=max_emails)

        if not message_list: # Handles None or empty list
            logger.info(f"No unread Gmail messages found for user {user_id}.")
            return processed_raw_email_ids

        logger.info(f"Found {len(message_list)} unread Gmail messages for user {user_id}.")
        for msg_meta in message_list:
            msg_id = msg_meta.get('id')
            if not msg_id: continue
            logger.info(f"Processing Gmail message ID: {msg_id} for user {user_id}")

            mime_content_str = await asyncio.to_thread(gmail_api_client.get_mime_content, message_id=msg_id)
            if mime_content_str:
                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".eml", mode="w", encoding="utf-8") as tmp:
                        tmp.write(mime_content_str); tmp_path = tmp.name
                    source_id = f"gmail_message_id:{msg_id}"
                    raw_email = self.ingest_email_from_file(tmp_path, source_identifier_override=source_id)
                    if raw_email:
                        processed_raw_email_ids.append(raw_email.message_id)
                        logger.info(f"Successfully ingested email from Gmail. Domain ID: {raw_email.message_id}, Gmail ID: {msg_id}, User: {user_id}")
                        if mark_as_read:
                            await asyncio.to_thread(gmail_api_client.mark_as_read, message_id=msg_id)
                finally:
                    if tmp_path and os.path.exists(tmp_path): os.remove(tmp_path)
            else:
                logger.warning(f"Could not retrieve MIME content for Gmail message ID {msg_id} for user {user_id}.")

        logger.info(f"Finished Gmail processing for user {user_id}. Processed {len(processed_raw_email_ids)} emails.")
        return processed_raw_email_ids

# Updated Example Usage for IngestionService (main_service_test)
async def main_service_test():
    # (Setup dummy handler as before)
    # ...
    # (File ingestion test as before)
    # ...
    # (M365 Graph ingestion test as before)
    # ...

    # --- Test Google Gmail ingestion ---
    print("\n--- IngestionService User Google Gmail Processing Test ---")
    test_user_for_gmail_sync = os.environ.get("TEST_USER_ID_WITH_GOOGLE_TOKEN")
    if not os.environ.get("GOOGLE_TOKEN_ENCRYPTION_KEY"):
        print("Skipping Gmail sync test: GOOGLE_TOKEN_ENCRYPTION_KEY not set.")
    elif not test_user_for_gmail_sync:
        print("Skipping Gmail sync test: TEST_USER_ID_WITH_GOOGLE_TOKEN env var not set.")
    elif not all(os.environ.get(v) for v in ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"]):
        print("Skipping Gmail sync test: Google OAuth client credentials not fully set.")
    else:
        print(f"Attempting to process Gmail emails for user_id: {test_user_for_gmail_sync}...")
        try:
            service = IngestionService() # Re-init for safety if needed, or use existing
            processed_gmail_ids = await service.process_user_google_mailbox(
                user_id=test_user_for_gmail_sync, max_emails=2, mark_as_read=False
            )
            print(f"Successfully processed {len(processed_gmail_ids)} emails from Gmail for user {test_user_for_gmail_sync}: {processed_gmail_ids}")
        except Exception as e_gmail_test:
            print(f"Error during Gmail processing test for user {test_user_for_gmail_sync}: {e_gmail_test}", exc_info=True)

    print("\n--- End of IngestionService Demonstrations ---")

if __name__ == '__main__':
    if not logging.getLogger().handlers:
         logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    asyncio.run(main_service_test())

```
