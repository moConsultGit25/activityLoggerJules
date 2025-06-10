# tests/auth_context/application/test_encryption_utils.py
import unittest
from unittest.mock import patch, MagicMock
import os
import importlib # For reloading the module to re-evaluate ENV VARS
from cryptography.fernet import Fernet, InvalidToken

# Import the module to be tested
from src.auth_context.application import encryption_utils

class TestEncryptionUtils(unittest.TestCase):

    def generate_valid_key(self) -> str:
        return Fernet.generate_key().decode()

    def setUp(self):
        # Store original env var, if exists, to restore it later
        self.original_env_key = os.environ.get("M365_TOKEN_ENCRYPTION_KEY")

    def tearDown(self):
        # Restore original environment variable to avoid side-effects between tests
        if self.original_env_key is not None:
            os.environ["M365_TOKEN_ENCRYPTION_KEY"] = self.original_env_key
        elif "M365_TOKEN_ENCRYPTION_KEY" in os.environ:
            del os.environ["M365_TOKEN_ENCRYPTION_KEY"]
        # Reload module to reflect original env var state for subsequent tests (if any in same suite run)
        importlib.reload(encryption_utils)


    @patch.dict(os.environ, {}, clear=True) # Start with a clean environment for this test
    def test_no_encryption_key_set(self):
        # Ensure key is not present from a previous test's patch or actual env
        if "M365_TOKEN_ENCRYPTION_KEY" in os.environ:
            del os.environ["M365_TOKEN_ENCRYPTION_KEY"]
        importlib.reload(encryption_utils) # Reload to pick up absent os.environ

        with patch.object(encryption_utils.logger, 'warning') as mock_warning:
            token_to_encrypt = "mysecrettoken"

            encrypted = encryption_utils.encrypt_token(token_to_encrypt)
            self.assertEqual(encrypted, token_to_encrypt)
            mock_warning.assert_any_call("Encryption key not available or invalid; returning token in plaintext (INSECURE).")

            decrypted = encryption_utils.decrypt_token(encrypted)
            self.assertEqual(decrypted, token_to_encrypt)
            mock_warning.assert_any_call("Encryption key not available or invalid; assuming token is plaintext (INSECURE).")

    @patch.dict(os.environ, {}, clear=True)
    def test_invalid_encryption_key_format(self):
        os.environ["M365_TOKEN_ENCRYPTION_KEY"] = "invalid-key-not-base64-and-not-32-bytes"
        # Use with block to ensure logger is patched only during this test's reload and calls
        with patch.object(encryption_utils.logger, 'error') as mock_error, \
             patch.object(encryption_utils.logger, 'warning') as mock_warning:
            importlib.reload(encryption_utils)

            mock_error.assert_any_call("Invalid M365_TOKEN_ENCRYPTION_KEY: Fernet key must be 32 url-safe base64-encoded bytes. Refresh token encryption/decryption will not work.")

            token_to_encrypt = "mysecrettoken"
            encrypted = encryption_utils.encrypt_token(token_to_encrypt)
            self.assertEqual(encrypted, token_to_encrypt)
            mock_warning.assert_any_call("Encryption key not available or invalid; returning token in plaintext (INSECURE).")

            decrypted = encryption_utils.decrypt_token(encrypted)
            self.assertEqual(decrypted, token_to_encrypt)
            mock_warning.assert_any_call("Encryption key not available or invalid; assuming token is plaintext (INSECURE).")

    @patch.dict(os.environ, {}, clear=True)
    def test_encrypt_decrypt_success(self):
        valid_key = self.generate_valid_key()
        os.environ["M365_TOKEN_ENCRYPTION_KEY"] = valid_key
        importlib.reload(encryption_utils)

        original_token = "mysupersecrettoken123!@#$%^&*()_+"
        encrypted_token = encryption_utils.encrypt_token(original_token)

        self.assertIsNotNone(encrypted_token)
        self.assertNotEqual(encrypted_token, original_token)

        decrypted_token = encryption_utils.decrypt_token(encrypted_token)
        self.assertEqual(decrypted_token, original_token)

    @patch.dict(os.environ, {}, clear=True)
    def test_decrypt_invalid_or_tampered_token(self):
        valid_key = self.generate_valid_key()
        os.environ["M365_TOKEN_ENCRYPTION_KEY"] = valid_key
        importlib.reload(encryption_utils)

        tampered_token = "gAAAAABf...thisisnotavalidfernettokenforsure..." # Example of what a Fernet token might look like
        with patch.object(encryption_utils.logger, 'error') as mock_error:
            decrypted = encryption_utils.decrypt_token(tampered_token)
            self.assertIsNone(decrypted)
            mock_error.assert_any_call(
                "Failed to decrypt token: Invalid token. This can happen if the token was not "
                "encrypted, encrypted with a different key, or has been tampered with."
            )

        # Test with a token encrypted by a different key
        another_valid_key = self.generate_valid_key()
        # Temporarily use another Fernet instance for encryption with a different key
        another_fernet = Fernet(another_valid_key.encode())
        encrypted_with_another_key = another_fernet.encrypt("some data".encode()).decode()

        # Decryption attempt with the original key loaded in encryption_utils._fernet_instance
        with patch.object(encryption_utils.logger, 'error') as mock_error:
            decrypted_wrong_key = encryption_utils.decrypt_token(encrypted_with_another_key)
            self.assertIsNone(decrypted_wrong_key)
            mock_error.assert_any_call(
                 "Failed to decrypt token: Invalid token. This can happen if the token was not "
                 "encrypted, encrypted with a different key, or has been tampered with."
            )

    @patch.dict(os.environ, {}, clear=True)
    def test_encrypt_empty_or_none(self):
        valid_key = self.generate_valid_key()
        os.environ["M365_TOKEN_ENCRYPTION_KEY"] = valid_key
        importlib.reload(encryption_utils)

        self.assertEqual(encryption_utils.encrypt_token(""), "")
        self.assertIsNone(encryption_utils.encrypt_token(None))

    @patch.dict(os.environ, {}, clear=True)
    def test_decrypt_empty_or_none(self):
        valid_key = self.generate_valid_key()
        os.environ["M365_TOKEN_ENCRYPTION_KEY"] = valid_key
        importlib.reload(encryption_utils)

        self.assertEqual(encryption_utils.decrypt_token(""), "")
        self.assertIsNone(encryption_utils.decrypt_token(None))

    @patch.dict(os.environ, {}, clear=True)
    def test_encrypt_internal_failure(self):
        valid_key = self.generate_valid_key()
        os.environ["M365_TOKEN_ENCRYPTION_KEY"] = valid_key
        importlib.reload(encryption_utils)

        with patch.object(encryption_utils._fernet_instance, 'encrypt', side_effect=Exception("Simulated encryption error")), \
             patch.object(encryption_utils.logger, 'error') as mock_logger_error:
            result = encryption_utils.encrypt_token("testtoken")
            self.assertIsNone(result)
            mock_logger_error.assert_called_once_with("Error encrypting token: Simulated encryption error", exc_info=True)

    @patch.dict(os.environ, {}, clear=True)
    def test_decrypt_internal_failure(self):
        valid_key = self.generate_valid_key()
        os.environ["M365_TOKEN_ENCRYPTION_KEY"] = valid_key
        importlib.reload(encryption_utils)

        # Need a valid encrypted token to pass the initial checks before mock is hit
        valid_encrypted_token = encryption_utils.encrypt_token("data_to_be_decrypted")
        self.assertIsNotNone(valid_encrypted_token)

        with patch.object(encryption_utils._fernet_instance, 'decrypt', side_effect=Exception("Simulated decryption error")), \
             patch.object(encryption_utils.logger, 'error') as mock_logger_error:
            result = encryption_utils.decrypt_token(valid_encrypted_token)
            self.assertIsNone(result)
            mock_logger_error.assert_called_once_with("Error decrypting token: Simulated decryption error", exc_info=True)

if __name__ == '__main__':
    unittest.main()
```
