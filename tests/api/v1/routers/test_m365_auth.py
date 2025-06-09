# tests/api/v1/routers/test_m365_auth.py
import unittest
from unittest.mock import patch, MagicMock, ANY
from fastapi.testclient import TestClient
from fastapi import status, Request # Added Request for type hinting
from itsdangerous import URLSafeTimedSerializer
import os
from datetime import datetime, timezone, timedelta

# Assuming your FastAPI app instance is in src.api.main
from src.api.main import app as fastapi_app
from src.auth_context.domain.user import User as DomainUser
from src.auth_context.domain.user_m365_token import UserM365Token

# For mocking dependencies
# from src.auth_context.infrastructure.m365_oauth_client import M365OAuthClient
# from src.auth_context.infrastructure.user_m365_token_repository import MongoUserM365TokenRepository

# Use a fixed secret key for serializer in tests for predictable cookies
TEST_STATE_SERIALIZER_SECRET_KEY = "test-serializer-secret-key-for-m365-oauth"
TEST_JWT_SECRET_KEY = "test-jwt-secret-for-api-tests" # If reusing for state serializer

# It's important that the state_serializer in the router uses this test key during tests.
# This can be achieved by patching os.environ before the router module is loaded by TestClient,
# or by directly patching the state_serializer instance within the router module if possible.

@patch.dict(os.environ, {
    "STATE_SERIALIZER_SECRET_KEY": TEST_STATE_SERIALIZER_SECRET_KEY,
    "JWT_SECRET_KEY": TEST_JWT_SECRET_KEY, # In case STATE_SERIALIZER_SECRET_KEY falls back to JWT_SECRET_KEY
    "M365_TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode() # Ensure encryption utils work
})
class TestM365AuthRoutes(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(fastapi_app)
        # This test serializer must use the same key and salt as the one in m365_auth.py router
        self.state_serializer = URLSafeTimedSerializer(TEST_STATE_SERIALIZER_SECRET_KEY, salt="m365-oauth-state-cookie")

        # Mock authenticated user for dependency
        self.mock_user = DomainUser(id="testuser123", username="testuser@example.com", hashed_password="hashed_pw")

        # Patch get_current_active_user dependency used by these routes
        # This is a common pattern. An alternative is to override dependencies in FastAPI app for tests.
        self.patcher_get_user = patch('src.api.v1.routers.m365_auth.get_current_active_user', return_value=self.mock_user)
        self.mock_get_current_active_user = self.patcher_get_user.start()
        self.addCleanup(self.patcher_get_user.stop)


    @patch('src.api.v1.routers.m365_auth.get_m365_oauth_client')
    def test_m365_authorize_redirect_success(self, mock_get_oauth_client):
        """Test successful initiation of M365 OAuth flow, expecting a redirect."""
        mock_oauth_client_instance = mock_get_oauth_client.return_value
        mock_auth_flow_details = {
            "auth_uri": "https://microsoft.login.com/authorize?param=value",
            "state": "generated_msal_state_123"
        }
        mock_oauth_client_instance.msal_app.initiate_auth_code_flow.return_value = mock_auth_flow_details

        response = self.client.get("/api/v1/auth/m365/authorize", allow_redirects=False) # Prevent auto-redirect for testing

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response.headers["location"], mock_auth_flow_details["auth_uri"])
        self.assertIn("m365_oauth_flow_details", response.cookies)

        # Verify cookie content
        cookie_value = response.cookies["m365_oauth_flow_details"]
        loaded_flow_details = self.state_serializer.loads(cookie_value)
        self.assertEqual(loaded_flow_details["state"], mock_auth_flow_details["state"])


    @patch('src.api.v1.routers.m365_auth.get_m365_oauth_client')
    def test_m365_authorize_client_config_error(self, mock_get_oauth_client):
        """Test M365 authorize initiation fails if M365OAuthClient has config error."""
        mock_get_oauth_client.side_effect = HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="M365 OAuth client is not configured"
        )
        response = self.client.get("/api/v1/auth/m365/authorize", allow_redirects=False)
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("M365 OAuth client is not configured", response.json()["detail"])


    @patch('src.api.v1.routers.m365_auth.get_m365_token_repository')
    @patch('src.api.v1.routers.m365_auth.get_m365_oauth_client')
    @patch('src.auth_context.application.encryption_utils.encrypt_token') # Mock encryption
    def test_m365_callback_success(self, mock_encrypt_token, mock_get_oauth_client, mock_get_token_repo):
        """Test successful M365 OAuth callback processing."""
        # --- Arrange ---
        mock_oauth_client = mock_get_oauth_client.return_value
        mock_token_repo = mock_get_token_repo.return_value

        # 1. Stash flow details in a cookie (as if /authorize was called)
        original_auth_flow_details = {
            "state": "callback_state_test_123",
            # Other details MSAL might put here, e.g., pkce_verifier
        }
        signed_flow_cookie = self.state_serializer.dumps(original_auth_flow_details)
        self.client.cookies.set("m365_oauth_flow_details", signed_flow_cookie)

        # 2. Mock M365OAuthClient's acquire_token_by_auth_code_flow response
        mock_token_response_from_msal = {
            "access_token": "mock_m365_access_token",
            "refresh_token": "mock_m365_refresh_token",
            "id_token_claims": {"preferred_username": "m365user@example.com", "oid": "m365_oid"},
            "expires_in": 3600
        }
        mock_oauth_client.acquire_token_by_auth_code_flow.return_value = mock_token_response_from_msal

        # 3. Mock encryption_utils.encrypt_token
        mock_encrypted_refresh_token = "encrypted_mock_m365_refresh_token"
        mock_encrypt_token.return_value = mock_encrypted_refresh_token

        # 4. Mock token_repo.save
        mock_token_repo.save.return_value = True

        # --- Act ---
        # Simulate the callback from Microsoft with code and state
        callback_url = f"/api/v1/auth/m365/callback?code=mock_auth_code&state={original_auth_flow_details['state']}"
        response = self.client.get(callback_url, allow_redirects=False) # Get redirect response

        # --- Assert ---
        self.assertEqual(response.status_code, status.HTTP_302_FOUND) # Should redirect to dashboard
        self.assertTrue(response.headers["location"].endswith("?message=Microsoft 365 account connected successfully."))

        # Verify acquire_token_by_auth_code_flow was called correctly
        mock_oauth_client.acquire_token_by_auth_code_flow.assert_called_once()
        call_args = mock_oauth_client.acquire_token_by_auth_code_flow.call_args[0]
        self.assertEqual(call_args[0], original_auth_flow_details) # stashed flow
        self.assertIn("code=mock_auth_code", call_args[1]['code']) # auth response params
        self.assertIn(original_auth_flow_details['state'], call_args[1]['state'])


        # Verify encrypt_token was called
        mock_encrypt_token.assert_called_once_with("mock_m365_refresh_token")

        # Verify repository save was called with correct UserM365Token data
        mock_token_repo.save.assert_called_once()
        saved_token_arg = mock_token_repo.save.call_args[0][0]
        self.assertIsInstance(saved_token_arg, UserM365Token)
        self.assertEqual(saved_token_arg.user_id, self.mock_user.id)
        self.assertEqual(saved_token_arg.encrypted_refresh_token, mock_encrypted_refresh_token)
        self.assertIsNotNone(saved_token_arg.access_token_expires_at)
        self.assertEqual(saved_token_arg.id_token_claims["preferred_username"], "m365user@example.com")

        # Verify cookie was cleared
        # TestClient doesn't easily show deleted cookies in the response object directly.
        # We'd typically check subsequent requests or the Set-Cookie header if it explicitly expires it.
        # For now, trust the code's response.delete_cookie("m365_oauth_flow_details")

    def test_m365_callback_no_flow_cookie(self):
        """Test callback fails if m365_oauth_flow_details cookie is missing."""
        response = self.client.get("/api/v1/auth/m365/callback?code=anycode&state=anystate", allow_redirects=False)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("OAuth flow details missing", response.json()["detail"])

    # Add more tests: callback with invalid state, token acquisition failure, repo save failure etc.

    @patch('src.api.v1.routers.m365_auth.get_m365_token_repository')
    def test_m365_disconnect_success(self, mock_get_token_repo):
        mock_token_repo = mock_get_token_repo.return_value
        mock_token_repo.delete_by_user_id.return_value = True # Simulate successful deletion

        response = self.client.post("/api/v1/auth/m365/disconnect")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("disconnected successfully", response.json()["message"])
        mock_token_repo.delete_by_user_id.assert_called_once_with(self.mock_user.id)

    @patch('src.api.v1.routers.m365_auth.get_m365_token_repository')
    def test_m365_disconnect_no_token_found(self, mock_get_token_repo):
        mock_token_repo = mock_get_token_repo.return_value
        mock_token_repo.delete_by_user_id.return_value = False # Simulate no token found to delete

        response = self.client.post("/api/v1/auth/m365/disconnect")
        self.assertEqual(response.status_code, status.HTTP_200_OK) # Still OK, but different message
        self.assertIn("No Microsoft 365 account was connected", response.json()["message"])

    @patch('src.api.v1.routers.m365_auth.get_m365_token_repository')
    def test_get_m365_connection_status_connected(self, mock_get_token_repo):
        mock_token_repo_inst = mock_get_token_repo.return_value
        mock_stored_token = UserM365Token(
            user_id=self.mock_user.id,
            encrypted_refresh_token="some_encrypted_token",
            id_token_claims={"preferred_username": "m365user@example.com"}
        )
        mock_token_repo_inst.get_by_user_id.return_value = mock_stored_token

        response = self.client.get("/api/v1/auth/m365/status")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["is_connected"])
        self.assertEqual(data["account_email"], "m365user@example.com")

    @patch('src.api.v1.routers.m365_auth.get_m365_token_repository')
    def test_get_m365_connection_status_not_connected(self, mock_get_token_repo):
        mock_token_repo_inst = mock_get_token_repo.return_value
        mock_token_repo_inst.get_by_user_id.return_value = None # No token found

        response = self.client.get("/api/v1/auth/m365/status")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertFalse(data["is_connected"])
        self.assertIsNone(data["account_email"])

if __name__ == '__main__':
    from cryptography.fernet import Fernet # Needed for patch.dict for M365_TOKEN_ENCRYPTION_KEY
    unittest.main()
```
