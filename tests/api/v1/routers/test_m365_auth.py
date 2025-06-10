# tests/api/v1/routers/test_m365_auth.py
import unittest
from unittest.mock import patch, MagicMock, ANY
from fastapi.testclient import TestClient
from fastapi import status, HTTPException # Added HTTPException
from datetime import datetime, timezone, timedelta
import os
import importlib # For reloading router module to pick up patched env vars

from src.api.main import app as fastapi_app
from src.auth_context.domain.user import User as DomainUser
from src.auth_context.domain.user_m365_token import UserM365Token
# from src.api.v1.schemas.auth_schemas import M365ConnectionStatus # For response validation (auto by TestClient)
from cryptography.fernet import Fernet # For generating test M365_TOKEN_ENCRYPTION_KEY

# Test keys - must be consistent for serializer between client and test
TEST_JWT_SECRET_KEY = "test_jwt_secret_for_m365_auth_tests_super_secure"
TEST_STATE_SERIALIZER_SECRET_KEY = TEST_JWT_SECRET_KEY # Reusing for simplicity in tests
TEST_M365_TOKEN_ENCRYPTION_KEY = Fernet.generate_key().decode()

# Apply test environment variables BEFORE the router module (and its global serializer) is loaded.
# This is tricky with TestClient as it loads the app.
# A common way is to ensure these are set before TestClient(app) is called.
# Here, we will use patch.dict in setUpClass or ensure they are set for the test session.
# For this subtask, we will patch os.environ, then reload the router module where state_serializer is defined.

# Patch environment variables that affect m365_auth.py at module level
@patch.dict(os.environ, {
    "JWT_SECRET_KEY": TEST_JWT_SECRET_KEY, # Fallback for STATE_SERIALIZER_SECRET_KEY
    "STATE_SERIALIZER_SECRET_KEY": TEST_STATE_SERIALIZER_SECRET_KEY,
    # Required for M365OAuthClient instantiation by the dependency function
    "AZURE_CLIENT_ID": "test_client_id_for_api",
    "AZURE_CLIENT_SECRET": "test_client_secret_for_api",
    "AZURE_TENANT_ID": "test_tenant_id_for_api",
    "M365_REDIRECT_URI": "http://localhost:8000/api/v1/auth/m365/callback", # Matches default in client
    "M365_SCOPES": "User.Read Mail.Read offline_access",
    "M365_TOKEN_ENCRYPTION_KEY": TEST_M365_TOKEN_ENCRYPTION_KEY,
}, clear=True) # clear=True ensures only these are set during the import/reload
class TestM365AuthRoutes(unittest.TestCase):

    @classmethod
    @patch.dict(os.environ, { # Re-apply for class setup if needed, or ensure it's done before imports
        "JWT_SECRET_KEY": TEST_JWT_SECRET_KEY,
        "STATE_SERIALIZER_SECRET_KEY": TEST_STATE_SERIALIZER_SECRET_KEY,
        "AZURE_CLIENT_ID": "test_client_id_for_api",
        "AZURE_CLIENT_SECRET": "test_client_secret_for_api",
        "AZURE_TENANT_ID": "test_tenant_id_for_api",
        "M365_REDIRECT_URI": "http://localhost:8000/api/v1/auth/m365/callback",
        "M365_SCOPES": "User.Read Mail.Read offline_access",
        "M365_TOKEN_ENCRYPTION_KEY": TEST_M365_TOKEN_ENCRYPTION_KEY,
    }, clear=True)
    def setUpClass(cls):
        # Reload router module to ensure it picks up the patched environment for its global serializer
        from src.api.v1.routers import m365_auth
        importlib.reload(m365_auth)
        cls.client = TestClient(fastapi_app) # Initialize TestClient after env is patched and module reloaded

    def setUp(self):
        # This user will be returned by the get_current_active_user dependency
        self.mock_user = DomainUser(id="testuser123", username="test@example.com", hashed_password="hashed_pw", is_active=True)

        # Patch the dependencies used by the router
        # Patching get_current_active_user from where it's *used* (in dependencies.py via m365_auth.py)
        self.patcher_get_user = patch('src.api.dependencies.get_current_active_user', return_value=self.mock_user)
        # Patching the dependency functions that provide service/repo instances
        self.patcher_get_m365_oauth_client = patch('src.api.v1.routers.m365_auth.get_m365_oauth_client')
        self.patcher_get_m365_token_repo = patch('src.api.v1.routers.m365_auth.get_m365_token_repository')
        # Patch encrypt_token used within the callback route
        self.patcher_encrypt_token = patch('src.api.v1.routers.m365_auth.encrypt_token')

        self.MockGetCurrentUser = self.patcher_get_user.start()
        self.MockGetM365OAuthClient = self.patcher_get_m365_oauth_client.start()
        self.MockGetM365TokenRepo = self.patcher_get_m365_token_repo.start()
        self.MockEncryptToken = self.patcher_encrypt_token.start()

        # Configure default mock instances
        self.mock_m365_client_instance = self.MockGetM365OAuthClient.return_value
        self.mock_token_repo_instance = self.MockGetM365TokenRepo.return_value
        self.MockEncryptToken.side_effect = lambda token: f"encrypted_{token}" if token else None


    def tearDown(self):
        self.patcher_get_user.stop()
        self.patcher_get_m365_oauth_client.stop()
        self.patcher_get_m365_token_repo.stop()
        self.patcher_encrypt_token.stop()

    def test_m365_authorize_success(self):
        mock_auth_flow = {"auth_uri": "https://microsoft.com/auth", "state": "msal_state_123"}
        self.mock_m365_client_instance.msal_app.initiate_auth_code_flow.return_value = mock_auth_flow

        response = self.client.get("/api/v1/auth/m365/authorize", allow_redirects=False)

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response.headers["location"], "https://microsoft.com/auth")
        self.assertIn("m365_oauth_flow_details", response.cookies)
        # Further cookie content check would require importing and using the test state_serializer here

    def test_m365_callback_success(self):
        # 1. Prepare stashed flow details and create a valid cookie for it
        stashed_flow_details = {"state": "test_state", "redirect_uri": "http://localhost:8000/api/v1/auth/m365/callback"}
        # Use the actual state_serializer from the router module (which should have test key due to setUpClass patch)
        from src.api.v1.routers.m365_auth import state_serializer as router_state_serializer
        signed_cookie_value = router_state_serializer.dumps(stashed_flow_details)
        cookies = {"m365_oauth_flow_details": signed_cookie_value}

        # 2. Mock MSAL token acquisition
        mock_m365_token_response = {
            "access_token": "m365_at", "refresh_token": "m365_rt",
            "id_token_claims": {"preferred_username": "user@m365.com"}, "expires_in": 3600
        }
        self.mock_m365_client_instance.acquire_token_by_auth_code_flow.return_value = mock_m365_token_response

        # 3. Mock repository save
        self.mock_token_repo_instance.save.return_value = True

        # 4. Make the call to callback endpoint
        callback_params = {"code": "m365_auth_code", "state": "test_state"}
        response = self.client.get("/api/v1/auth/m365/callback", params=callback_params, cookies=cookies, allow_redirects=False)

        # 5. Assertions
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertTrue(response.headers["location"].endswith("?message=Microsoft 365 account connected successfully."))
        self.MockEncryptToken.assert_called_once_with("m365_rt")
        self.mock_token_repo_instance.save.assert_called_once()
        saved_token: UserM365Token = self.mock_token_repo_instance.save.call_args[0][0]
        self.assertEqual(saved_token.user_id, self.mock_user.id)
        self.assertEqual(saved_token.encrypted_refresh_token, "encrypted_m365_rt")
        self.assertAlmostEqual(saved_token.access_token_expires_at, datetime.now(timezone.utc) + timedelta(seconds=3600), delta=timedelta(seconds=10))

    def test_m365_disconnect_success(self):
        self.mock_token_repo_instance.delete_by_user_id.return_value = True
        response = self.client.post("/api/v1/auth/m365/disconnect")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("disconnected successfully", response.json()["message"])
        self.mock_token_repo_instance.delete_by_user_id.assert_called_once_with(self.mock_user.id)

    def test_get_m365_connection_status_connected(self):
        mock_user_token = UserM365Token(
            user_id=self.mock_user.id,
            encrypted_refresh_token="rt_enc",
            id_token_claims={"preferred_username": "m365@example.com"}
        )
        self.mock_token_repo_instance.get_by_user_id.return_value = mock_user_token
        response = self.client.get("/api/v1/auth/m365/status")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["is_connected"])
        self.assertEqual(data["account_email"], "m365@example.com")

    def test_get_m365_connection_status_not_connected(self):
        self.mock_token_repo_instance.get_by_user_id.return_value = None
        response = self.client.get("/api/v1/auth/m365/status")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertFalse(data["is_connected"])
        self.assertIsNone(data["account_email"])

    def test_m365_callback_state_mismatch_or_tampered_cookie(self):
        # Simulate a tampered/invalid cookie by not setting it or setting an invalid one
        # The state_serializer.loads in the endpoint should raise BadSignature/SignatureExpired
        # This can be directly tested by mocking state_serializer.loads if needed,
        # but TestClient with invalid cookie is more of an integration test.

        # Case 1: No cookie
        callback_params = {"code": "m365_auth_code", "state": "any_state"}
        response = self.client.get("/api/v1/auth/m365/callback", params=callback_params, allow_redirects=False)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("OAuth flow details missing", response.json()["detail"])

        # Case 2: Tampered cookie value
        cookies = {"m365_oauth_flow_details": "this.is.not.a.valid.signed.value"}
        response = self.client.get("/api/v1/auth/m365/callback", params=callback_params, cookies=cookies, allow_redirects=False)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid or expired OAuth state", response.json()["detail"])


if __name__ == '__main__':
    # This is important for the os.environ patching at class level to take effect before module imports
    # when running this file directly.
    unittest.main()
```
