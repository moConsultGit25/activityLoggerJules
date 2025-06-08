# src/ingestion_context/infrastructure/graph_email_client.py
import os
import msal
import httpx
from typing import List, Dict, Optional, Any

# Configuration: Load from environment variables
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET")
AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID")
GRAPH_TARGET_USER_ID = os.environ.get("GRAPH_TARGET_USER_ID") # User's email or object ID
GRAPH_MAIL_FOLDER_ID = os.environ.get("GRAPH_MAIL_FOLDER", "Inbox") # Default to Inbox

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
GRAPH_API_SCOPES = ["https://graph.microsoft.com/.default"]


class GraphEmailClient:
    """
    Client to interact with Microsoft Graph API for reading emails.
    Uses client credentials flow (app-only permissions).
    """
    def __init__(self):
        self.client_id = AZURE_CLIENT_ID
        self.client_secret = AZURE_CLIENT_SECRET
        self.tenant_id = AZURE_TENANT_ID
        self.target_user_id = GRAPH_TARGET_USER_ID
        self.mail_folder_id = GRAPH_MAIL_FOLDER_ID

        if not all([self.client_id, self.client_secret, self.tenant_id, self.target_user_id]):
            raise ValueError("Missing Azure AD app credentials or Target User ID in environment variables.")

        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.msal_app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
            # token_cache can be configured here for persistent caching if needed
        )
        self._access_token: Optional[Dict[str, Any]] = None # Simple in-memory cache for token

    def get_access_token(self) -> Optional[str]:
        """
        Acquires an access token for Microsoft Graph API using client credentials flow.
        Uses MSAL's built-in caching; this method checks simple in-memory cache first.
        """
        # Check cached token first (MSAL also has its own caching)
        if self._access_token:
            # MSAL tokens have 'expires_in' and 'token_type'.
            # A more robust cache would check expiration. For simplicity, MSAL handles this.
            # Here, we just assume if it exists, MSAL will refresh if needed or it's valid.
            pass # MSAL will handle refresh if needed based on its cache.

        result = self.msal_app.acquire_token_silent(scopes=GRAPH_API_SCOPES, account=None)
        if not result:
            print("GraphEmailClient: No suitable token in cache, acquiring new one...")
            result = self.msal_app.acquire_token_for_client(scopes=GRAPH_API_SCOPES)

        if "access_token" in result:
            self._access_token = result # Cache the whole token result for potential future use (e.g. expires_in)
            print("GraphEmailClient: Access token acquired successfully.")
            return result["access_token"]
        else:
            error_details = result.get("error_description", "No error description provided.")
            print(f"GraphEmailClient: Failed to acquire access token. Error: {result.get('error')}. Details: {error_details}")
            return None

    async def get_unread_emails(self, top: int = 10) -> Optional[List[Dict[str, Any]]]:
        """
        Fetches metadata of unread emails from the specified user's mail folder.
        """
        token = self.get_access_token()
        if not token:
            return None

        # Construct the URL for fetching messages
        # $select can be used to limit fields: e.g., id,subject,sender,receivedDateTime,isRead
        # $filter for unread: isRead eq false
        messages_url = (
            f"{GRAPH_API_ENDPOINT}/users/{self.target_user_id}/mailFolders/{self.mail_folder_id}/messages"
            f"?$filter=isRead eq false&$top={top}&$select=id,subject,sender,receivedDateTime,createdDateTime"
        )

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(messages_url, headers=headers)
                response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                email_data = response.json()
                print(f"GraphEmailClient: Found {len(email_data.get('value', []))} unread emails.")
                return email_data.get("value", [])
            except httpx.HTTPStatusError as e:
                print(f"GraphEmailClient: HTTP error getting unread emails: {e.response.status_code} - {e.response.text}")
                return None
            except Exception as e:
                print(f"GraphEmailClient: Unexpected error getting unread emails: {e}")
                return None

    async def get_mime_content(self, message_id: str) -> Optional[str]:
        """
        Retrieves the full MIME content of a specific email message.
        """
        token = self.get_access_token()
        if not token:
            return None

        mime_url = f"{GRAPH_API_ENDPOINT}/users/{self.target_user_id}/messages/{message_id}/$value"
        headers = {"Authorization": f"Bearer {token}"} # No specific Accept header for $value, it's text/plain

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(mime_url, headers=headers)
                response.raise_for_status()
                # The response for $value is the raw MIME content, typically text/plain
                print(f"GraphEmailClient: MIME content retrieved for message ID {message_id}.")
                return response.text
            except httpx.HTTPStatusError as e:
                print(f"GraphEmailClient: HTTP error getting MIME content for message {message_id}: {e.response.status_code} - {e.response.text}")
                return None
            except Exception as e:
                print(f"GraphEmailClient: Unexpected error getting MIME content: {e}")
                return None

    async def mark_email_as_read(self, message_id: str) -> bool:
        """
        Marks a specific email message as read.
        """
        token = self.get_access_token()
        if not token:
            return False

        message_url = f"{GRAPH_API_ENDPOINT}/users/{self.target_user_id}/messages/{message_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {"isRead": True}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(message_url, headers=headers, json=payload)
                response.raise_for_status()
                print(f"GraphEmailClient: Message ID {message_id} marked as read.")
                return True
            except httpx.HTTPStatusError as e:
                print(f"GraphEmailClient: HTTP error marking email as read for message {message_id}: {e.response.status_code} - {e.response.text}")
                return False
            except Exception as e:
                print(f"GraphEmailClient: Unexpected error marking email as read: {e}")
                return False


# Example Usage (for direct testing of this client)
async def main_test_graph_client():
    print("--- GraphEmailClient Demonstration ---")
    # Ensure environment variables are set before running this test:
    # AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID, GRAPH_TARGET_USER_ID
    if not all([AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID, GRAPH_TARGET_USER_ID]):
        print("Please set Azure AD and Graph API environment variables for this demo.")
        print("Required: AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID, GRAPH_TARGET_USER_ID")
        return

    graph_client = GraphEmailClient()

    print("\n1. Attempting to get access token...")
    token = graph_client.get_access_token()
    if token:
        print(f"Access token obtained (first 20 chars): {token[:20]}...")
    else:
        print("Failed to get access token. Further tests will likely fail.")
        return

    print("\n2. Attempting to get unread emails (top 2)...")
    unread_emails = await graph_client.get_unread_emails(top=2)
    if unread_emails is not None: # Could be an empty list if no unread emails
        print(f"Found {len(unread_emails)} unread emails.")
        for email_meta in unread_emails:
            print(f"  - ID: {email_meta['id']}, Subject: {email_meta.get('subject', 'N/A')}")

            if len(unread_emails) > 0: # Process first found unread email
                target_message_id = unread_emails[0]['id']
                print(f"\n3. Attempting to get MIME content for message ID: {target_message_id}...")
                mime_content = await graph_client.get_mime_content(target_message_id)
                if mime_content:
                    print(f"MIME content retrieved (first 100 chars):\n{mime_content[:100]}...")

                    # print(f"\n4. Attempting to mark message ID {target_message_id} as read...")
                    # mark_success = await graph_client.mark_email_as_read(target_message_id)
                    # print(f"Mark as read successful: {mark_success}")
                else:
                    print("Failed to retrieve MIME content.")
                break # Only process one email for this demo
    else:
        print("Failed to get unread emails list or no unread emails found.")

    print("\n--- End of GraphEmailClient Demonstration ---")

if __name__ == '__main__':
    import asyncio
    # To run this: python -m src.ingestion_context.infrastructure.graph_email_client
    # Make sure you are in the project root directory.
    # You'll need to set the environment variables.

    # Check if required env vars are set before trying to run async main
    if "AZURE_CLIENT_ID" not in os.environ:
        print("Demo requires environment variables like AZURE_CLIENT_ID, etc. to be set.")
    else:
        asyncio.run(main_test_graph_client())
