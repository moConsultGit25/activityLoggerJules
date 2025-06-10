# src/ingestion_context/infrastructure/gmail_api_client.py
import logging
import base64
from typing import List, Dict, Optional, Any # Added Any for type hinting

from googleapiclient.discovery import build as build_google_api_client, Resource
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials as GoogleCredentials

logger = logging.getLogger(__name__)

class GmailApiClient:
    """
    Client for interacting with the Gmail API using user-delegated credentials.
    Note: The google-api-python-client's execute() method is blocking.
    When using this client in an async context (like an async Celery task or FastAPI route),
    its methods should be called using `await asyncio.to_thread(client_method, ...)`
    to avoid blocking the event loop.
    """
    def __init__(self, credentials: GoogleCredentials):
        """
        Initializes the Gmail API client with user credentials.
        :param credentials: google.oauth2.credentials.Credentials object for the user.
                            This object should be valid (e.g., refreshed if necessary)
                            before being passed to this client.
        """
        if not credentials or not credentials.valid:
            # While credentials.valid checks current access token, a refresh token might still be usable.
            # The service using this client should ensure a valid (refreshed) access token is
            # part of the credentials object or handle refresh just before API calls.
            # For simplicity, we rely on the caller to provide usable credentials.
            logger.warning("GmailApiClient initialized with credentials that are not immediately valid. "
                           "Token refresh might be needed before API calls.")
            # If credentials object has no token at all (e.g. only refresh_token), build() will fail later.
            # A more robust check would be if credentials.token is None and credentials.refresh_token is also None.

        try:
            # cache_discovery=False is recommended for server-side/long-running apps
            # to prevent issues with stale API discovery documents.
            self.service: Resource = build_google_api_client(
                'gmail', 'v1', credentials=credentials, cache_discovery=False
            )
            logger.info("Gmail API service client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Gmail API service client: {e}", exc_info=True)
            # This typically indicates a problem with credentials or Google library setup.
            raise ValueError(f"GmailApiClient could not be created: {e}")


    def list_messages(
        self,
        user_id: str = "me",
        query: str = "is:unread",
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Lists messages in the user's mailbox matching the query.
        Returns a list of message resource dictionaries (id, threadId).
        NOTE: This is a blocking I/O call and should be wrapped with asyncio.to_thread if called from async code.
        """
        messages_data: List[Dict[str, Any]] = []
        next_page_token: Optional[str] = None

        # Ensure max_results is positive
        if max_results <= 0:
            return []

        try:
            while True:
                # Calculate how many more messages to fetch in this page request
                num_to_fetch_this_page = min(max_results - len(messages_data), 100) # Gmail API maxResults per page
                if num_to_fetch_this_page <= 0: # Already fetched enough
                    break

                response = self.service.users().messages().list(
                    userId=user_id,
                    q=query,
                    maxResults=num_to_fetch_this_page,
                    pageToken=next_page_token
                ).execute() # Blocking call

                current_page_messages = response.get('messages', [])
                messages_data.extend(current_page_messages)

                next_page_token = response.get('nextPageToken')
                if not next_page_token or len(messages_data) >= max_results:
                    break # No more pages or we've hit the desired max_results

            logger.info(f"Gmail API: Found {len(messages_data)} messages for query '{query}' (requested max: {max_results}).")
            return messages_data # Already ensured not to exceed max_results by loop logic
        except HttpError as error:
            logger.error(f"Gmail API error in list_messages (query='{query}'): {error.status_code} - {error._get_reason()}", exc_info=True)
            # Specific error handling (e.g., for 401/403 if token expired and not refreshed by google-auth lib)
            # The google-auth lib should attempt to refresh the token if it's close to expiry or expired,
            # assuming a refresh_token is present in the credentials object.
            # If refresh fails, it raises google.auth.exceptions.RefreshError.
            return []
        except Exception as e:
            logger.error(f"Unexpected error in list_messages: {e}", exc_info=True)
            return []

    def get_mime_content(self, message_id: str, user_id: str = "me") -> Optional[str]:
        """
        Gets the full raw MIME content of a single message.
        Returns the MIME content as a string, or None on error.
        NOTE: This is a blocking I/O call.
        """
        try:
            message_response = self.service.users().messages().get(
                userId=user_id,
                id=message_id,
                format='raw' # Returns base64url encoded string in message_response['raw']
            ).execute() # Blocking call

            raw_mime_base64url = message_response.get('raw')
            if raw_mime_base64url:
                # Decode base64url string (URL-safe base64)
                mime_bytes = base64.urlsafe_b64decode(raw_mime_base64url)
                # Attempt to decode as UTF-8, then fall back to Latin-1.
                # For true robustness, an email parsing library should handle the raw bytes.
                try:
                    return mime_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    logger.warning(f"Could not decode MIME for message {message_id} as UTF-8. Trying latin-1.")
                    return mime_bytes.decode('latin-1', errors='replace') # Use 'replace' for problematic chars
            else:
                logger.warning(f"No raw MIME content found for message {message_id}.")
                return None
        except HttpError as error:
            logger.error(f"Gmail API error in get_mime_content for message {message_id}: {error.status_code} - {error._get_reason()}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get_mime_content for message {message_id}: {e}", exc_info=True)
            return None

    def mark_as_read(self, message_id: str, user_id: str = "me") -> bool:
        """
        Marks a message as read by removing the 'UNREAD' label.
        Returns True on success, False on failure.
        NOTE: This is a blocking I/O call.
        """
        try:
            # To mark as read, we remove the 'UNREAD' label.
            # To mark as unread, we would add the 'UNREAD' label.
            modify_request_body = {'removeLabelIds': ['UNREAD']}
            self.service.users().messages().modify(
                userId=user_id,
                id=message_id,
                body=modify_request_body
            ).execute() # Blocking call
            logger.info(f"Gmail message {message_id} marked as read for user {user_id}.")
            return True
        except HttpError as error:
            logger.error(f"Gmail API error marking message {message_id} as read: {error.status_code} - {error._get_reason()}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error marking message {message_id} as read: {e}", exc_info=True)
            return False

# Example Usage (conceptual, requires valid credentials object)
async def main_test_gmail_client(): # Make it async for testing with asyncio.to_thread
    import asyncio
    print("--- GmailApiClient Demonstration (Conceptual) ---")

    # This test requires a MANUALLY OBTAINED and VALID google.oauth2.credentials.Credentials object.
    # In a real app, this comes from the GoogleOAuthClient and user token storage.

    # Placeholder for credentials - replace with actual way to get credentials for a test user
    mock_credentials = None

    # Example: Load from a saved token file (if you have one from a previous OAuth flow)
    # try:
    #     if os.path.exists('token.json'): # Example path
    #         mock_credentials = GoogleCredentials.from_authorized_user_file('token.json', GmailApiClient.SCOPES)
    # except Exception as e_cred:
    #     print(f"Could not load mock_credentials from token.json: {e_cred}")

    if not mock_credentials:
        print("Skipping GmailApiClient demo: Mock credentials are not available.")
        print("To run this, you need to provide a valid GoogleCredentials object.")
        print("This typically involves completing an OAuth flow and saving the token.")
        return

    # Before using, ensure token is valid or refresh it
    # if mock_credentials.expired and mock_credentials.refresh_token:
    #     print("Credentials expired, attempting refresh...")
    #     from google.auth.transport.requests import Request as GoogleAuthReq
    #     mock_credentials.refresh(GoogleAuthReq())
    #     # Save refreshed credentials if needed: with open('token.json', 'w') as token_file: token_file.write(mock_credentials.to_json())

    if not mock_credentials.valid:
        print("Skipping GmailApiClient demo: Mock credentials are not valid even after potential refresh attempt.")
        return

    try:
        gmail_client = GmailApiClient(credentials=mock_credentials)
    except ValueError as ve:
        print(f"Could not initialize GmailApiClient: {ve}")
        return

    print("\n1. Listing unread messages (top 2)...")
    # Wrap blocking call for async context
    unread_messages = await asyncio.to_thread(gmail_client.list_messages, user_id="me", query="is:unread", max_results=2)

    if unread_messages:
        print(f"Found {len(unread_messages)} unread messages:")
        for email_meta in unread_messages:
            print(f"  - ID: {email_meta['id']}, ThreadID: {email_meta.get('threadId')}")

            if unread_messages: # Process first found unread email
                target_message_id = unread_messages[0]['id']
                print(f"\n2. Getting MIME content for message ID: {target_message_id}...")
                mime_content = await asyncio.to_thread(gmail_client.get_mime_content, message_id=target_message_id, user_id="me")
                if mime_content:
                    print(f"MIME content retrieved (first 100 chars):\n{mime_content[:100]}...")

                    # print(f"\n3. Marking message ID {target_message_id} as read...")
                    # mark_success = await asyncio.to_thread(gmail_client.mark_as_read, message_id=target_message_id, user_id="me")
                    # print(f"Mark as read successful: {mark_success}")
                else:
                    print("Failed to retrieve MIME content.")
                break # Only process one email for this demo
    else:
        print("No unread messages found or an error occurred.")

    print("\n--- End of GmailApiClient Demonstration ---")

if __name__ == '__main__':
    # To run this: python -m src.ingestion_context.infrastructure.gmail_api_client
    # You would need to set up a 'token.json' or provide mock_credentials in some way.
    if not logging.getLogger().handlers: # Ensure basic logging for demo
         logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    asyncio.run(main_test_gmail_client())

```
