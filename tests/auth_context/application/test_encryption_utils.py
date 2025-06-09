# tests/auth_context/application/test_encryption_utils.py
import unittest
from unittest.mock import patch
import os
from cryptography.fernet import Fernet, InvalidToken

# Import functions to test
# Need to be careful if _fernet_instance is already initialized at import time based on env var
# We might need to reload the module or patch os.environ *before* module import for some tests.
# For simplicity, we'll patch os.environ and assume functions will re-check or use the patched value.
# A better way for testing is to make _fernet_instance injectable or part of a class.

# Forcing a reload for testing different ENCRYPTION_KEY states:
import importlib
from src.auth_context.application import encryption_utils

class TestEncryptionUtils(unittest.TestCase):

    def setUp(self):
        # Ensure each test can set its own environment for ENCRYPTION_KEY
        self.original_env_var = os.environ.get("M365_TOKEN_ENCRYPTION_KEY")

    def tearDown(self):
        # Restore original environment variable state
        if self.original_env_var is None:
            if "M365_TOKEN_ENCRYPTION_KEY" in os.environ:
                del os.environ["M365_TOKEN_ENCRYPTION_KEY"]
        else:
            os.environ["M365_TOKEN_ENCRYPTION_KEY"] = self.original_env_var
        importlib.reload(encryption_utils) # Important to reload to re-evaluate _fernet_instance

    @patch.dict(os.environ, {"M365_TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode()})
    def test_encrypt_decrypt_success(self):
        importlib.reload(encryption_utils) # Reload to pick up patched env var
        original_token = "my_very_secret_token_data_!@#$%^&*()"
        encrypted = encryption_utils.encrypt_token(original_token)
        self.assertIsNotNone(encrypted)
        self.assertNotEqual(encrypted, original_token)

        decrypted = encryption_utils.decrypt_token(encrypted)
        self.assertEqual(decrypted, original_token)

    @patch.dict(os.environ, {"M365_TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode()})
    def test_decrypt_invalid_token_returns_none(self):
        importlib.reload(encryption_utils)
        invalid_encrypted_token = "gAAAAAB_this_is_not_a_valid_fernet_token_for_sure"
        decrypted = encryption_utils.decrypt_token(invalid_encrypted_token)
        self.assertIsNone(decrypted, "Decrypting an invalid token should return None or raise InvalidToken (handled as None here)")

    @patch.dict(os.environ, {}, clear=True) # Ensure M365_TOKEN_ENCRYPTION_KEY is not set
    def test_encrypt_no_key_returns_plaintext(self):
        # Must remove the key from environ if it was set by a previous test or system wide
        if "M365_TOKEN_ENCRYPTION_KEY" in os.environ:
            del os.environ["M365_TOKEN_ENCRYPTION_KEY"]
        importlib.reload(encryption_utils) # Reload to ensure _fernet_instance is None

        original_token = "plaintext_token_due_to_no_key"
        with self.assertLogs(encryption_utils.logger, level='WARNING') as log_watcher:
            encrypted = encryption_utils.encrypt_token(original_token)
            self.assertIn("Encryption key not available or invalid; returning token in plaintext (INSECURE).", log_watcher.output[0])

        self.assertEqual(encrypted, original_token, "Token should be plaintext if key is missing")


    @patch.dict(os.environ, {}, clear=True) # Ensure M365_TOKEN_ENCRYPTION_KEY is not set
    def test_decrypt_no_key_returns_plaintext(self):
        if "M365_TOKEN_ENCRYPTION_KEY" in os.environ:
            del os.environ["M365_TOKEN_ENCRYPTION_KEY"]
        importlib.reload(encryption_utils)

        encrypted_looking_token = "this_looks_encrypted_but_will_be_treated_as_plaintext"
        with self.assertLogs(encryption_utils.logger, level='WARNING') as log_watcher:
            decrypted = encryption_utils.decrypt_token(encrypted_looking_token)
            self.assertIn("Encryption key not available or invalid; assuming token is plaintext (INSECURE).", log_watcher.output[0])

        self.assertEqual(decrypted, encrypted_looking_token, "Token should be returned as is if key is missing")

    @patch.dict(os.environ, {"M365_TOKEN_ENCRYPTION_KEY": "this_is_not_a_valid_fernet_key"})
    def test_init_with_invalid_key_format(self):
        # This test checks the behavior at module load time (or reload)
        with self.assertLogs(encryption_utils.logger, level='ERROR') as log_watcher:
            importlib.reload(encryption_utils) # Attempt to reload with the bad key
            # _fernet_instance should be None after this
            self.assertIn("Invalid M365_TOKEN_ENCRYPTION_KEY", log_watcher.output[0])

        self.assertIsNone(encryption_utils._fernet_instance, "_fernet should be None if key is invalid")
        # Subsequent calls should behave as if no key is set
        original_token = "test"
        self.assertEqual(encryption_utils.encrypt_token(original_token), original_token)
        self.assertEqual(encryption_utils.decrypt_token(original_token), original_token)


    @patch.dict(os.environ, {"M365_TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode()})
    def test_encrypt_empty_or_none(self):
        importlib.reload(encryption_utils)
        self.assertEqual(encryption_utils.encrypt_token(""), "")
        self.assertIsNone(encryption_utils.encrypt_token(None))

    @patch.dict(os.environ, {"M365_TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode()})
    def test_decrypt_empty_or_none(self):
        importlib.reload(encryption_utils)
        self.assertEqual(encryption_utils.decrypt_token(""), "")
        self.assertIsNone(encryption_utils.decrypt_token(None))

if __name__ == '__main__':
    # Basic logging setup for test output visibility, if needed
    # logging.basicConfig(level=logging.DEBUG)
    unittest.main()
```
