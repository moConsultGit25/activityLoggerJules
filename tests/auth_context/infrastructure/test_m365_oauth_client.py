# tests/auth_context/infrastructure/test_m365_oauth_client.py
import unittest
from unittest.mock import patch, MagicMock
import os
import importlib # For reloading the module

# Module to be tested
from src.auth_context.infrastructure import m365_oauth_client # import the module itself

class TestM365OAuthClient(unittest.TestCase):

    MOCK_ENV_VARS_FULL = {
        "AZURE_CLIENT_ID": "test_client_id",
        "AZURE_CLIENT_SECRET": "test_client_secret",
        "AZURE_TENANT_ID": "test_tenant_id",
        "M365_REDIRECT_URI": "http://localhost/callback",
        "M365_SCOPES": "Mail.Read User.Read offline_access"
    }

    MOCK_ENV_VARS_MINIMAL_FOR_INIT = {
        "AZURE_CLIENT_ID": "test_client_id",
        "AZURE_CLIENT_SECRET": "test_client_secret",
        "AZURE_TENANT_ID": "test_tenant_id",
        "M365_REDIRECT_URI": "http://localhost/callback",
        # M365_SCOPES will use default from M365OAuthClient if not set here
    }

    def tearDown(self):
        # Clean up any environment variables that might have been set by tests
        # to avoid interference. This is belt-and-suspenders with clear=True in patch.dict.
        for key in self.MOCK_ENV_VARS_FULL.keys():
            if os.environ.get(key):
                del os.environ[key]
        # Reload module to reset its global state based on cleared env vars (if any were module-level)
        importlib.reload(m365_oauth_client)


    @patch.dict(os.environ, {}, clear=True) # Start with totally empty os.environ
    def test_init_missing_all_credentials(self):
        with patch.object(m365_oauth_client.logger, 'error') as mock_logger_error:
            with self.assertRaises(ValueError) as context:
                importlib.reload(m365_oauth_client) # Reload to pick up empty env
                m365_oauth_client.M365OAuthClient()
            self.assertIn("Azure AD app credentials must be configured", str(context.exception))
            mock_logger_error.assert_any_call("Azure AD credentials (client ID, secret, tenant ID) are not fully configured.")

    @patch.dict(os.environ, {"AZURE_CLIENT_ID": "id", "AZURE_CLIENT_SECRET": "secret", "AZURE_TENANT_ID": "tid"}, clear=True)
    def test_init_missing_redirect_uri(self):
        with patch.object(m365_oauth_client.logger, 'error') as mock_logger_error:
            with self.assertRaises(ValueError) as context:
                importlib.reload(m365_oauth_client)
                m365_oauth_client.M365OAuthClient()
            self.assertIn("M365_REDIRECT_URI must be configured", str(context.exception))
            mock_logger_error.assert_any_call("M365_REDIRECT_URI environment variable is not set. This is required for OAuth flow.")

    @patch.dict(os.environ, MOCK_ENV_VARS_FULL, clear=True)
    @patch('msal.ConfidentialClientApplication')
    def test_init_success_and_properties(self, MockMSALApp):
        importlib.reload(m365_oauth_client) # Reload to pick up MOCK_ENV_VARS_FULL
        client = m365_oauth_client.M365OAuthClient()

        self.assertEqual(client.client_id, self.MOCK_ENV_VARS_FULL["AZURE_CLIENT_ID"])
        self.assertEqual(client.client_secret, self.MOCK_ENV_VARS_FULL["AZURE_CLIENT_SECRET"])
        self.assertEqual(client.tenant_id, self.MOCK_ENV_VARS_FULL["AZURE_TENANT_ID"])
        self.assertEqual(client.authority, f"https://login.microsoftonline.com/{self.MOCK_ENV_VARS_FULL['AZURE_TENANT_ID']}")
        self.assertEqual(client.redirect_uri, self.MOCK_ENV_VARS_FULL["M365_REDIRECT_URI"])
        self.assertEqual(client.scopes, self.MOCK_ENV_VARS_FULL["M365_SCOPES"].split())

        MockMSALApp.assert_called_once_with(
            client_id=self.MOCK_ENV_VARS_FULL["AZURE_CLIENT_ID"],
            authority=client.authority,
            client_credential=self.MOCK_ENV_VARS_FULL["AZURE_CLIENT_SECRET"]
        )

    @patch.dict(os.environ, MOCK_ENV_VARS_MINIMAL_FOR_INIT, clear=True) # M365_SCOPES is not set, will use default
    @patch('msal.ConfidentialClientApplication')
    def test_init_uses_default_scopes_if_not_set(self, MockMSALApp):
        importlib.reload(m365_oauth_client)
        client = m365_oauth_client.M365OAuthClient()
        self.assertEqual(client.scopes, "User.Read Mail.Read offline_access".split())


    @patch.dict(os.environ, MOCK_ENV_VARS_FULL, clear=True)
    @patch('msal.ConfidentialClientApplication')
    def test_get_authorization_request_url(self, MockMSALApp):
        importlib.reload(m365_oauth_client)
        mock_msal_instance = MockMSALApp.return_value
        client = m365_oauth_client.M365OAuthClient()

        expected_auth_uri = "https://example.com/auth"
        expected_state_from_msal = "msal_generated_state_123"
        mock_msal_instance.initiate_auth_code_flow.return_value = {
            "auth_uri": expected_auth_uri,
            "state": expected_state_from_msal
        }

        # Test case 1: client passes state=None (MSAL generates it)
        auth_uri, state = client.get_authorization_request_url(state=None)
        mock_msal_instance.initiate_auth_code_flow.assert_called_with(
            scopes=client.scopes,
            redirect_uri=client.redirect_uri,
            state=None
        )
        self.assertEqual(auth_uri, expected_auth_uri)
        self.assertEqual(state, expected_state_from_msal)

        # Test case 2: client passes a specific state
        mock_msal_instance.reset_mock()
        specific_state = "my_custom_state_456"
        mock_msal_instance.initiate_auth_code_flow.return_value = {
            "auth_uri": expected_auth_uri, # URI might be same
            "state": specific_state # MSAL flow should use this state
        }
        auth_uri, state = client.get_authorization_request_url(state=specific_state)
        mock_msal_instance.initiate_auth_code_flow.assert_called_with(
            scopes=client.scopes,
            redirect_uri=client.redirect_uri,
            state=specific_state
        )
        self.assertEqual(state, specific_state)


    @patch.dict(os.environ, MOCK_ENV_VARS_FULL, clear=True)
    @patch('msal.ConfidentialClientApplication')
    def test_acquire_token_by_auth_code_flow_success(self, MockMSALApp):
        importlib.reload(m365_oauth_client)
        mock_msal_instance = MockMSALApp.return_value
        client = m365_oauth_client.M365OAuthClient()

        auth_code_flow_stashed = {"state": "s123", "some_other_msal_param": "val"}
        auth_response_params = {"code": "123xyz", "state": "s123"}
        expected_tokens = {"access_token": "at", "refresh_token": "rt", "id_token_claims": {"sub": "user"}}
        mock_msal_instance.acquire_token_by_auth_code_flow.return_value = expected_tokens

        tokens = client.acquire_token_by_auth_code_flow(auth_code_flow_stashed, auth_response_params)

        mock_msal_instance.acquire_token_by_auth_code_flow.assert_called_once_with(
            auth_code_flow=auth_code_flow_stashed,
            auth_response=auth_response_params,
            scopes=client.scopes
        )
        self.assertEqual(tokens, expected_tokens)

    @patch.dict(os.environ, MOCK_ENV_VARS_FULL, clear=True)
    @patch('msal.ConfidentialClientApplication')
    def test_acquire_token_by_auth_code_flow_msal_error(self, MockMSALApp):
        importlib.reload(m365_oauth_client)
        mock_msal_instance = MockMSALApp.return_value
        client = m365_oauth_client.M365OAuthClient()

        auth_code_flow_stashed = {"state": "s123"}
        auth_response_params = {"code": "123xyz", "state": "s123"}
        msal_error_response = {"error": "invalid_grant", "error_description": "Bad code."}
        mock_msal_instance.acquire_token_by_auth_code_flow.return_value = msal_error_response

        with patch.object(m365_oauth_client.logger, 'error') as mock_logger:
            tokens = client.acquire_token_by_auth_code_flow(auth_code_flow_stashed, auth_response_params)
            self.assertIsNone(tokens)
            mock_logger.assert_called_with(f"Error acquiring token via auth code flow: {msal_error_response.get('error')}. Description: {msal_error_response.get('error_description')}")

    @patch.dict(os.environ, MOCK_ENV_VARS_FULL, clear=True)
    @patch('msal.ConfidentialClientApplication')
    def test_acquire_token_by_refresh_token_success(self, MockMSALApp):
        importlib.reload(m365_oauth_client)
        mock_msal_instance = MockMSALApp.return_value
        client = m365_oauth_client.M365OAuthClient()

        refresh_token_val = "old_rt"
        expected_tokens = {"access_token": "new_at", "refresh_token": "new_rt_optional"}
        mock_msal_instance.acquire_token_by_refresh_token.return_value = expected_tokens

        tokens = client.acquire_token_by_refresh_token(refresh_token_val)
        mock_msal_instance.acquire_token_by_refresh_token.assert_called_once_with(
            refresh_token=refresh_token_val,
            scopes=client.scopes
        )
        self.assertEqual(tokens, expected_tokens)

    @patch.dict(os.environ, MOCK_ENV_VARS_FULL, clear=True)
    @patch('msal.ConfidentialClientApplication')
    def test_acquire_token_by_refresh_token_msal_error(self, MockMSALApp):
        importlib.reload(m365_oauth_client)
        mock_msal_instance = MockMSALApp.return_value
        client = m365_oauth_client.M365OAuthClient()

        refresh_token_val = "old_rt"
        msal_error_response = {"error": "invalid_grant", "error_description": "Refresh token expired."}
        mock_msal_instance.acquire_token_by_refresh_token.return_value = msal_error_response

        with patch.object(m365_oauth_client.logger, 'error') as mock_logger:
            tokens = client.acquire_token_by_refresh_token(refresh_token_val)
            self.assertIsNone(tokens)
            mock_logger.assert_called_with(f"Error acquiring token by refresh token: {msal_error_response.get('error')}. Description: {msal_error_response.get('error_description')}")


if __name__ == '__main__':
    unittest.main()
```
