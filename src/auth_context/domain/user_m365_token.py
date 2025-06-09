# src/auth_context/domain/user_m365_token.py
import dataclasses
from datetime import datetime, timezone, timedelta # Added timedelta for calculating expires_at
from typing import Optional, List, Dict # Added Dict for id_token_claims


@dataclasses.dataclass
class UserM365Token:
    """
    Represents stored Microsoft 365 OAuth tokens for a user.
    The refresh token is stored encrypted in the database.
    """
    user_id: str  # Foreign key to the main User.id in your system

    # The refresh token is sensitive and should be stored encrypted.
    # The encryption/decryption happens at the service layer before saving/after loading.
    # The repository layer will handle this as a string.
    encrypted_refresh_token: Optional[str] = None

    # Access token is short-lived and typically not stored, but its expiry can be.
    # This helps in determining if a new access token needs to be fetched using the refresh token.
    access_token_expires_at: Optional[datetime] = None # UTC datetime

    # Store the scopes for which these tokens were granted.
    scopes: Optional[List[str]] = None

    # Optional: Store some claims from the ID token for quick reference, if needed.
    # e.g., user's M365 object ID (oid) or tenant ID (tid) if multi-tenant scenarios.
    id_token_claims: Optional[Dict[str, Any]] = None

    # Timestamps for record management
    created_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc))

    # If a user could link multiple M365 accounts, a separate primary key for this record would be needed.
    # For now, assuming one M365 token set per user_id (user_id is effectively the PK).
    # Example if needed:
    # m365_token_record_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))


    def update_tokens(self, token_response: Dict, encryption_func) -> None:
        """
        Helper method to update token data from a token response dictionary (e.g., from MSAL).
        The encryption_func is passed in to handle encrypting the refresh token.
        """
        new_refresh_token = token_response.get("refresh_token")
        if new_refresh_token:
            self.encrypted_refresh_token = encryption_func(new_refresh_token)
            logger.debug(f"UserM365Token: Updated and encrypted refresh token for user {self.user_id}.")

        access_token = token_response.get("access_token") # Not stored, but used for expires_at
        expires_in_seconds = token_response.get("expires_in")
        if access_token and expires_in_seconds:
            self.access_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in_seconds) - 30) # -30s buffer
            logger.debug(f"UserM365Token: Updated access token expiry for user {self.user_id} to {self.access_token_expires_at}.")

        scopes_str = token_response.get("scope") # MSAL often returns scopes as a space-separated string
        if scopes_str:
            self.scopes = scopes_str.split()

        id_token_claims_from_resp = token_response.get("id_token_claims")
        if id_token_claims_from_resp:
            self.id_token_claims = id_token_claims_from_resp # Store all claims or select specific ones

        self.updated_at = datetime.now(timezone.utc)

# Need logger for the helper method
import logging # Moved to top level for the module
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    # Example usage
    user_token = UserM365Token(
        user_id="user_abc_123",
        encrypted_refresh_token="dummy_encrypted_refresh_token", # This would be output of encrypt_token()
        access_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        scopes=["Mail.Read", "User.Read", "offline_access"],
        id_token_claims={"oid": "m365_user_object_id", "tid": "m365_tenant_id"}
    )
    print(f"Created UserM365Token instance for user_id: {user_token.user_id}")
    print(f"  Refresh Token (Encrypted): {user_token.encrypted_refresh_token}")
    print(f"  Access Token Expires At: {user_token.access_token_expires_at}")
    print(f"  Scopes: {user_token.scopes}")
    print(f"  Updated At: {user_token.updated_at}")

    # Example of using the helper (encryption_func would be encrypt_token from encryption_utils)
    mock_token_response = {
        "refresh_token": "new_plain_refresh_token",
        "access_token": "new_plain_access_token",
        "expires_in": 3600, # 1 hour
        "scope": "Mail.Read User.Read offline_access openid profile email",
        "id_token_claims": {"oid": "new_oid", "tid": "new_tid", "preferred_username": "user@example.com"}
    }

    # Dummy encryption function for demo
    def _dummy_encrypt(token_str):
        return f"encrypted_{token_str}" if token_str else None

    user_token.update_tokens(mock_token_response, _dummy_encrypt)
    print("\nAfter updating with mock token response:")
    print(f"  Encrypted Refresh Token: {user_token.encrypted_refresh_token}")
    print(f"  Access Token Expires At: {user_token.access_token_expires_at}")
    print(f"  Scopes: {user_token.scopes}")
    print(f"  ID Token Claims: {user_token.id_token_claims}")
    print(f"  Updated At: {user_token.updated_at}")
```
