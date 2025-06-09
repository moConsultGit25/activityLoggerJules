# tests/auth_context/infrastructure/test_m365_oauth_client.py
import unittest
from unittest.mock import patch, MagicMock
import os

# Module to test
from src.auth_context.infrastructure.m365_oauth_client import M365OAuthClient

class TestM365OAuthClient(unittest.TestCase):

    @patch.dict(os.environ, {
        "AZURE_CLIENT_ID": "test_client_id",
        "AZURE_CLIENT_SECRET": "test_client_secret",
        "AZURE_TENANT_ID": "test_tenant_id",
        "M365_REDIRECT_URI": "http://localhost/callback",
        "M365_SCOPES": "User.Read Mail.Read offline_access"
    })
    @patch('msal.ConfidentialClientApplication')
    def test_init_success(self, MockConfidentialClientApplication):
        """Test successful initialization of M365OAuthClient."""
        mock_msal_app_instance = MockConfidentialClientApplication.return_value
        client = M365OAuthClient()

        MockConfidentialClientApplication.assert_called_once_with(
            client_id="test_client_id",
            authority=f"https://login.microsoftonline.com/test_tenant_id",
            client_credential="test_client_secret"
        )
        self.assertEqual(client.client_id, "test_client_id")
        self.assertEqual(client.redirect_uri, "http://localhost/callback")
        self.assertEqual(client.scopes, ["User.Read", "Mail.Read", "offline_access"])
        self.assertIsNotNone(mock_msal_app_instance) # To ensure it was assigned

    @patch.dict(os.environ, {"AZURE_CLIENT_ID": "test_id"}) # Missing other required vars
    def test_init_missing_env_vars_raises_value_error(self):
        """Test that ValueError is raised if essential env vars are missing."""
        with self.assertRaises(ValueError) as context:
            M365OAuthClient()
        self.assertIn("Azure AD app credentials must be configured", str(context.exception))

    @patch.dict(os.environ, {
        "AZURE_CLIENT_ID": "test_client_id",
        "AZURE_CLIENT_SECRET": "test_client_secret",
        "AZURE_TENANT_ID": "test_tenant_id",
        "M365_REDIRECT_URI": "http://localhost/callback", # M365_SCOPES will use default
    })
    @patch('msal.ConfidentialClientApplication')
    def test_get_authorization_request_url(self, MockConfidentialClientApplication):
        """Test generation of authorization request URL."""
        mock_msal_app = MockConfidentialClientApplication.return_value
        expected_auth_uri = "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/authorize?..."
        expected_state = "mocked_state_value"
        mock_msal_app.initiate_auth_code_flow.return_value = {
            "auth_uri": expected_auth_uri,
            "state": expected_state
            # Other potential keys: pkce_verifier (if applicable)
        }

        client = M365OAuthClient()
        auth_uri, state = client.get_authorization_request_url(state="passed_state_value_if_any") # or state=None to test MSAL generation

        mock_msal_app.initiate_auth_code_flow.assert_called_once_with(
            scopes=client.scopes,
            redirect_uri=client.redirect_uri,
            state="passed_state_value_if_any"
        )
        self.assertEqual(auth_uri, expected_auth_uri)
        self.assertEqual(state, expected_state)

    @patch.dict(os.environ, {
        "AZURE_CLIENT_ID": "cid", "AZURE_CLIENT_SECRET": "cs", "AZURE_TENANT_ID": "tid",
        "M365_REDIRECT_URI": "uri", "M365_SCOPES": "s1 s2"
    })
    @patch('msal.ConfidentialClientApplication')
    def test_acquire_token_by_auth_code_flow_success(self, MockConfidentialClientApplication):
        """Test successful token acquisition using auth code flow."""
        mock_msal_app = MockConfidentialClientApplication.return_value
        mock_token_response = {
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
            "id_token_claims": {"oid": "user_object_id"}
        }
        mock_msal_app.acquire_token_by_auth_code_flow.return_value = mock_token_response

        client = M365OAuthClient()
        auth_code_flow_stashed = {"state": "some_stashed_state_from_initiate_flow"} # Example stashed flow
        auth_response_params = {"code": "auth_code_from_redirect", "state": "some_stashed_state_from_initiate_flow"}

        token_package = client.acquire_token_by_auth_code_flow(auth_code_flow_stashed, auth_response_params)

        mock_msal_app.acquire_token_by_auth_code_flow.assert_called_once_with(
            auth_code_flow=auth_code_flow_stashed,
            auth_response=auth_response_params,
            scopes=client.scopes
        )
        self.assertIsNotNone(token_package)
        self.assertEqual(token_package["access_token"], "mock_access_token")

    @patch.dict(os.environ, {
        "AZURE_CLIENT_ID": "cid", "AZURE_CLIENT_SECRET": "cs", "AZURE_TENANT_ID": "tid",
        "M365_REDIRECT_URI": "uri", "M365_SCOPES": "s1 s2"
    })
    @patch('msal.ConfidentialClientApplication')
    def test_acquire_token_by_auth_code_flow_error(self, MockConfidentialClientApplication):
        """Test error handling during token acquisition by auth code flow."""
        mock_msal_app = MockConfidentialClientApplication.return_value
        mock_error_response = {"error": "invalid_grant", "error_description": "AADSTS70000: Provided grant is invalid or malformed."}
        mock_msal_app.acquire_token_by_auth_code_flow.return_value = mock_error_response

        client = M365OAuthClient()
        auth_code_flow_stashed = {"state": "state"}
        auth_response_params = {"code": "bad_code", "state": "state"}

        token_package = client.acquire_token_by_auth_code_flow(auth_code_flow_stashed, auth_response_params)
        self.assertIsNone(token_package)

    @patch.dict(os.environ, {
        "AZURE_CLIENT_ID": "cid", "AZURE_CLIENT_SECRET": "cs", "AZURE_TENANT_ID": "tid",
        "M365_REDIRECT_URI": "uri", "M365_SCOPES": "s1 s2"
    })
    @patch('msal.ConfidentialClientApplication')
    def test_acquire_token_by_refresh_token_success(self, MockConfidentialClientApplication):
        """Test successful token acquisition using a refresh token."""
        mock_msal_app = MockConfidentialClientApplication.return_value
        mock_refresh_response = {"access_token": "new_access_token", "refresh_token": "optional_new_refresh_token"}
        mock_msal_app.acquire_token_by_refresh_token.return_value = mock_refresh_response

        client = M365OAuthClient()
        token_package = client.acquire_token_by_refresh_token("old_refresh_token")

        mock_msal_app.acquire_token_by_refresh_token.assert_called_once_with(
            refresh_token="old_refresh_token",
            scopes=client.scopes
        )
        self.assertIsNotNone(token_package)
        self.assertEqual(token_package["access_token"], "new_access_token")

if __name__ == '__main__':
    unittest.main()
```
