# src/ingestion_context/infrastructure/graph_email_client.py
import os
import httpx # MSAL is no longer directly used in this client for token acquisition
from typing import List, Dict, Optional, Any
import logging # Added logger

logger = logging.getLogger(__name__)

# Configuration - these are now less critical for the client itself,
# but good to keep for context or if some non-user-specific Graph calls were ever needed.
# AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID") # Not directly used by client methods anymore
# AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID") # Not directly used by client methods anymore
GRAPH_MAIL_FOLDER_ID = os.environ.get("GRAPH_MAIL_FOLDER", "Inbox") # Default to Inbox, can be overridden

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
# GRAPH_API_SCOPES are defined in M365OAuthClient and when requesting token.

class GraphEmailClient:
    """
    Client to interact with Microsoft Graph API for reading emails using a user-delegated access token.
    It no longer handles token acquisition itself; tokens are passed to its methods.
    API calls are made to the '/me' endpoint, representing the authenticated user.
    """
    def __init__(self):
        # No authentication setup here. This client is now a simple API request executor.
        self.mail_folder_id = GRAPH_MAIL_FOLDER_ID # Still uses this for default folder
        logger.info(f"GraphEmailClient initialized. It will operate on user's behalf using provided tokens. Default folder: {self.mail_folder_id}")

    async def get_unread_emails(self, access_token: str, folder_id: Optional[str] = None, top: int = 10) -> Optional[List[Dict[str, Any]]]:
        """
        Fetches metadata of unread emails from the authenticated user's mail folder.
        Uses the '/me' endpoint.
        """
        if not access_token:
            logger.error("get_unread_emails: No access token provided.")
            return None

        target_folder = folder_id if folder_id else self.mail_folder_id

        messages_url = (
            f"{GRAPH_API_ENDPOINT}/me/mailFolders/{target_folder}/messages"
            f"?$filter=isRead eq false&$top={top}&$select=id,subject,sender,receivedDateTime,createdDateTime,webLink"
        )

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(messages_url, headers=headers)
                response.raise_for_status()
                email_data = response.json()
                found_emails = email_data.get("value", [])
                logger.info(f"GraphEmailClient: Found {len(found_emails)} unread emails in folder '{target_folder}' for user.")
                return found_emails
            except httpx.HTTPStatusError as e:
                logger.error(f"GraphEmailClient: HTTP error getting unread emails: {e.response.status_code} - {e.response.text}")
                return None
            except Exception as e:
                logger.error(f"GraphEmailClient: Unexpected error getting unread emails: {e}", exc_info=True)
                return None

    async def get_mime_content(self, access_token: str, message_id: str) -> Optional[str]:
        """
        Retrieves the full MIME content of a specific email message for the authenticated user.
        Uses the '/me' endpoint.
        """
        if not access_token:
            logger.error("get_mime_content: No access token provided.")
            return None
        if not message_id:
            logger.error("get_mime_content: No message_id provided.")
            return None

        mime_url = f"{GRAPH_API_ENDPOINT}/me/messages/{message_id}/$value"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(mime_url, headers=headers)
                response.raise_for_status()
                logger.info(f"GraphEmailClient: MIME content retrieved for message ID {message_id}.")
                return response.text
            except httpx.HTTPStatusError as e:
                logger.error(f"GraphEmailClient: HTTP error getting MIME content for message {message_id}: {e.response.status_code} - {e.response.text}")
                return None
            except Exception as e:
                logger.error(f"GraphEmailClient: Unexpected error getting MIME content for message {message_id}: {e}", exc_info=True)
                return None

    async def mark_email_as_read(self, access_token: str, message_id: str) -> bool:
        """
        Marks a specific email message as read for the authenticated user.
        Uses the '/me' endpoint.
        """
        if not access_token:
            logger.error("mark_email_as_read: No access token provided.")
            return False
        if not message_id:
            logger.error("mark_email_as_read: No message_id provided.")
            return False

        message_url = f"{GRAPH_API_ENDPOINT}/me/messages/{message_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {"isRead": True}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(message_url, headers=headers, json=payload)
                response.raise_for_status()
                logger.info(f"GraphEmailClient: Message ID {message_id} marked as read for user.")
                return True
            except httpx.HTTPStatusError as e:
                logger.error(f"GraphEmailClient: HTTP error marking email as read for message {message_id}: {e.response.status_code} - {e.response.text}")
                return False
            except Exception as e:
                logger.error(f"GraphEmailClient: Unexpected error marking email as read for message {message_id}: {e}", exc_info=True)
                return False

# Example Usage (conceptual, as it requires a valid access token)
async def main_test_graph_client_with_user_token():
    print("--- GraphEmailClient with User Token Demonstration ---")
    # This test requires a MANUALLY OBTAINED valid user access_token with Mail.Read scope.
    # In a real scenario, this token comes from the M365OAuthClient flow.

    USER_ACCESS_TOKEN = os.environ.get("TEST_USER_M365_ACCESS_TOKEN") # For testing, set this env var

    if not USER_ACCESS_TOKEN:
        print("Please set the TEST_USER_M365_ACCESS_TOKEN environment variable with a valid Graph API access token for this demo.")
        return

    graph_client = GraphEmailClient() # No auth in constructor now

    print("\n1. Attempting to get unread emails (top 2) using provided user token...")
    unread_emails = await graph_client.get_unread_emails(access_token=USER_ACCESS_TOKEN, top=2)

    if unread_emails is not None:
        print(f"Found {len(unread_emails)} unread emails for the authenticated user.")
        for email_meta in unread_emails:
            print(f"  - ID: {email_meta['id']}, Subject: {email_meta.get('subject', 'N/A')}")

            if len(unread_emails) > 0: # Process first found unread email
                target_message_id = unread_emails[0]['id']
                print(f"\n2. Attempting to get MIME content for message ID: {target_message_id}...")
                mime_content = await graph_client.get_mime_content(access_token=USER_ACCESS_TOKEN, message_id=target_message_id)
                if mime_content:
                    print(f"MIME content retrieved (first 100 chars):\n{mime_content[:100]}...")

                    # print(f"\n3. Attempting to mark message ID {target_message_id} as read...")
                    # mark_success = await graph_client.mark_email_as_read(access_token=USER_ACCESS_TOKEN, message_id=target_message_id)
                    # print(f"Mark as read successful: {mark_success}")
                else:
                    print("Failed to retrieve MIME content.")
                break # Only process one email for this demo
    else:
        print("Failed to get unread emails list or no unread emails found (or token invalid/expired).")

    print("\n--- End of GraphEmailClient with User Token Demonstration ---")

if __name__ == '__main__':
    import asyncio
    # To run this: python -m src.ingestion_context.infrastructure.graph_email_client
    # Make sure you are in the project root directory.
    # You'll need to set TEST_USER_M365_ACCESS_TOKEN environment variable.
    asyncio.run(main_test_graph_client_with_user_token())
