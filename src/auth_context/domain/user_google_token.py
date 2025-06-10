# src/auth_context/domain/user_google_token.py
import dataclasses
from datetime import datetime, timezone, timedelta # Added timedelta
from typing import List, Dict, Any, Optional
import logging # For logging in helper

logger = logging.getLogger(__name__)

@dataclasses.dataclass
class UserGoogleToken:
    """
    Represents stored Google OAuth tokens for a user, primarily for Gmail API access.
    The refresh token is stored encrypted in the database.
    """
    user_id: str  # Foreign key to the main User.id in your application
    encrypted_refresh_token: Optional[str] = None # Stored encrypted

    # Store expiry of the access token that was valid when refresh token was last used/obtained.
    # This helps to know if a refresh is likely needed without trying a Graph API call first.
    access_token_expires_at: Optional[datetime] = None # UTC datetime

    # Store the scopes for which these tokens were granted.
    scopes: Optional[List[str]] = None

    # Optional: Store some claims from the ID token for quick reference, if needed.
    # e.g., user's Google subject ID (sub), email, etc.
    id_token_claims: Optional[Dict[str, Any]] = None

    # Timestamps for record management
    created_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc))

    # If a user could link multiple Google accounts (e.g. personal and work),
    # a separate primary key for this record would be needed.
    # For now, assuming one Google token set per user_id (user_id is effectively the PK).
    # Example if needed:
    # google_token_record_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))

    def update_tokens(self, token_response: Dict[str, Any], encryption_func: callable) -> None:
        """
        Helper method to update token data from a Google token response dictionary.
        The encryption_func is passed in to handle encrypting the refresh token.

        Args:
            token_response (Dict[str, Any]): The token dictionary from GoogleOAuthClient,
                                             e.g., from fetch_tokens_by_auth_code or refresh_access_token.
            encryption_func (callable): A function that takes a plaintext token string and returns
                                        an encrypted string (e.g., encrypt_token from encryption_utils).
        """
        logger.debug(f"UserGoogleToken: Updating tokens for user {self.user_id} from response: {list(token_response.keys())}")

        # Google usually issues a refresh token only once during the initial authorization code exchange
        # when 'access_type=offline' and 'prompt=consent' are used.
        # Subsequent access token refreshes using that refresh token do NOT typically return a new refresh token.
        # So, only update encrypted_refresh_token if a new one is explicitly provided in the response.
        new_refresh_token = token_response.get("refresh_token")
        if new_refresh_token: # This will usually only happen on the first token acquisition
            encrypted_new_rt = encryption_func(new_refresh_token)
            if encrypted_new_rt:
                self.encrypted_refresh_token = encrypted_new_rt
                logger.info(f"UserGoogleToken: Updated and encrypted new Google refresh token for user {self.user_id}.")
            else:
                logger.error(f"UserGoogleToken: CRITICAL - Failed to encrypt new Google refresh token for user {self.user_id}. Storing it unencrypted is a security risk.")
                # Decide on policy: store unencrypted, raise error, or don't update.
                # For now, if encryption fails but a key was configured, it's a problem.
                # If no key was configured, encryption_func might return plaintext (with warning).
                # The current encryption_utils.encrypt_token returns None on failure if key is present.
                # If encryption is mandatory, this should raise an error.
                # If encryption_func returned None due to error:
                if os.environ.get("GOOGLE_TOKEN_ENCRYPTION_KEY"): # Check if key was set, implying failure
                     logger.error(f"UserGoogleToken: Encryption key is set but encryption_func returned None for refresh token. User: {self.user_id}")
                     # Not updating self.encrypted_refresh_token in this specific error case.
                else: # No key, encryption_func returned plaintext
                     self.encrypted_refresh_token = new_refresh_token # Storing plaintext as per encryption_utils behavior

        # Update access token expiry.
        # GoogleOAuthClient's methods return 'expires_at_datetime' (datetime obj) or 'expires_at_iso' (ISO string).
        # Prefer 'expires_at_datetime' if available.
        new_expiry_dt = token_response.get("expires_at_datetime")
        if isinstance(new_expiry_dt, datetime):
            self.access_token_expires_at = new_expiry_dt
        elif token_response.get("expires_at_iso"): # Fallback to ISO string
            try:
                self.access_token_expires_at = datetime.fromisoformat(token_response["expires_at_iso"].replace('Z', '+00:00'))
            except (ValueError, TypeError) as e:
                logger.warning(f"UserGoogleToken: Could not parse 'expires_at_iso' string: {token_response.get('expires_at_iso')}. Error: {e}")
                # As a further fallback, if 'expires_in' (seconds) is available from raw response (less likely from our client)
                expires_in_seconds = token_response.get("expires_in")
                if isinstance(expires_in_seconds, (int, float)):
                     self.access_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in_seconds) - 30) # -30s buffer
                     logger.info(f"UserGoogleToken: Calculated expiry from 'expires_in' for user {self.user_id}.")

        if self.access_token_expires_at:
             logger.debug(f"UserGoogleToken: Updated Google access token expiry for user {self.user_id} to {self.access_token_expires_at}.")

        # Update scopes if provided in the token response
        new_scopes_list = token_response.get("scopes") # GoogleOAuthClient methods return this as a list
        if isinstance(new_scopes_list, list):
            self.scopes = new_scopes_list

        # Update ID token claims if provided
        # GoogleOAuthClient's fetch_tokens_by_auth_code returns 'id_token_claims' (decoded dict)
        # and refresh_access_token might also return it.
        new_id_token_claims = token_response.get("id_token_claims")
        if isinstance(new_id_token_claims, dict):
            self.id_token_claims = new_id_token_claims
            logger.debug(f"UserGoogleToken: Updated Google ID token claims for user {self.user_id}. Email from claims: {self.id_token_claims.get('email')}")

        self.updated_at = datetime.now(timezone.utc)


if __name__ == '__main__':
    # Example for UserGoogleToken
    test_user_token = UserGoogleToken(
        user_id="google_user_001",
        encrypted_refresh_token="dummy_encrypted_google_rt",
        access_token_expires_at=datetime.now(timezone.utc) + timedelta(minutes=50),
        scopes=["https://www.googleapis.com/auth/gmail.readonly", "openid", "email"],
        id_token_claims={"sub": "google_user_subject_id", "email": "user@gmail.com"}
    )
    print(f"Created UserGoogleToken for user: {test_user_token.user_id}")
    print(f"  Encrypted RT: {test_user_token.encrypted_refresh_token}")
    print(f"  Expires At: {test_user_token.access_token_expires_at}")
    print(f"  Scopes: {test_user_token.scopes}")
    print(f"  Email (from claims): {test_user_token.id_token_claims.get('email')}")

    # Simulate update from a token response
    mock_google_token_resp = {
        "refresh_token": "new_plain_google_refresh_token", # Google usually only gives this on first auth
        "access_token": "new_google_access_token",
        "expires_at_datetime": datetime.now(timezone.utc) + timedelta(seconds=3500),
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly", "openid", "email", "profile"],
        "id_token_claims": {"sub": "google_user_subject_id", "email": "user@gmail.com", "name": "Test User"}
    }

    def _dummy_google_encrypt(token_str): return f"encrypted_google_{token_str}" if token_str else None

    test_user_token.update_tokens(mock_google_token_resp, _dummy_google_encrypt)
    print("\nAfter update_tokens call:")
    print(f"  Encrypted RT: {test_user_token.encrypted_refresh_token}")
    print(f"  Expires At: {test_user_token.access_token_expires_at}")
    print(f"  Scopes: {test_user_token.scopes}")
    print(f"  Name (from claims): {test_user_token.id_token_claims.get('name')}")
    print(f"  Updated At: {test_user_token.updated_at}")

```
