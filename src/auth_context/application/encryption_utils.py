# src/auth_context/application/encryption_utils.py
import os
from cryptography.fernet import Fernet, InvalidToken
import logging

logger = logging.getLogger(__name__)

# Load encryption key from environment variable
# This key MUST be kept secret and be a URL-safe base64-encoded 32-byte key.
# To generate a suitable key, run this in a Python interpreter:
# from cryptography.fernet import Fernet
# key = Fernet.generate_key()
# print(key.decode()) # Use this output as your M365_TOKEN_ENCRYPTION_KEY
M365_TOKEN_ENCRYPTION_KEY_STR = os.environ.get("M365_TOKEN_ENCRYPTION_KEY")

_fernet_instance: Optional[Fernet] = None

if M365_TOKEN_ENCRYPTION_KEY_STR:
    try:
        key_bytes = M365_TOKEN_ENCRYPTION_KEY_STR.encode() # Fernet key must be bytes
        _fernet_instance = Fernet(key_bytes)
        logger.info("M365 token encryption utility initialized successfully with provided key.")
    except Exception as e:
        logger.error(
            f"Invalid M365_TOKEN_ENCRYPTION_KEY: {e}. It must be a URL-safe base64-encoded 32-byte key. "
            "Refresh token encryption/decryption will not work. Please generate a valid key."
        )
        # _fernet_instance remains None, functions will not encrypt/decrypt.
else:
    logger.warning(
        "M365_TOKEN_ENCRYPTION_KEY environment variable is not set. "
        "Refresh tokens will be stored in plaintext if processed. "
        "This is INSECURE for production. Please generate and set a key."
    )
    # _fernet_instance remains None.

def encrypt_token(token: str) -> Optional[str]:
    """Encrypts a token string. Returns the original token if encryption is not configured."""
    if not _fernet_instance:
        logger.warning("Encryption key not available or invalid; returning token in plaintext (INSECURE).")
        return token # Storing raw for dev/testing if key is missing - NOT FOR PRODUCTION
    if not token: # Handles empty string or None
        return token
    try:
        return _fernet_instance.encrypt(token.encode()).decode()
    except Exception as e:
        logger.error(f"Error encrypting token: {e}", exc_info=True)
        # Depending on policy, you might want to raise an error here or return None.
        # Returning None indicates failure to encrypt.
        return None

def decrypt_token(encrypted_token_str: str) -> Optional[str]:
    """Decrypts an encrypted token string. Returns the original string if encryption is not configured."""
    if not _fernet_instance:
        logger.warning("Encryption key not available or invalid; assuming token is plaintext (INSECURE).")
        return encrypted_token_str # Returning raw for dev/testing if key is missing
    if not encrypted_token_str: # Handles empty string or None
        return encrypted_token_str
    try:
        return _fernet_instance.decrypt(encrypted_token_str.encode()).decode()
    except InvalidToken:
        logger.error(
            "Failed to decrypt token: Invalid token. This can happen if the token was not "
            "encrypted, encrypted with a different key, or has been tampered with."
        )
        return None # Or raise a specific error
    except Exception as e:
        logger.error(f"Error decrypting token: {e}", exc_info=True)
        return None # Or raise

if __name__ == '__main__':
    print("--- Encryption Utilities Demonstration ---")
    if not M365_TOKEN_ENCRYPTION_KEY_STR:
        print("WARNING: M365_TOKEN_ENCRYPTION_KEY is not set in the environment.")
        print("This demo will show plaintext 'encryption' and 'decryption'.")
        print("For real encryption, set the environment variable. Generate a key with:")
        print("  from cryptography.fernet import Fernet")
        print("  key = Fernet.generate_key().decode()")
        print("  print(key)")
    else:
        print(f"Using M365_TOKEN_ENCRYPTION_KEY (first 5 chars): {M365_TOKEN_ENCRYPTION_KEY_STR[:5]}...")


    sample_token = "my_secret_refresh_token_12345_example"
    print(f"\nOriginal token: {sample_token}")

    encrypted = encrypt_token(sample_token)
    if encrypted:
        print(f"Encrypted: {encrypted}")
        if encrypted == sample_token:
            print("NOTE: Token was not actually encrypted because key is missing/invalid.")

        decrypted = decrypt_token(encrypted)
        print(f"Decrypted: {decrypted}")
        assert decrypted == sample_token, "Decryption did not match original!"
    else:
        print("Encryption failed.")

    print("\nTesting with empty token:")
    empty_encrypted = encrypt_token("")
    print(f"Encrypted empty: '{empty_encrypted}' (should be empty or None)")
    assert empty_encrypted == "" # or check for None if encrypt_token behavior changes for empty
    empty_decrypted = decrypt_token(empty_encrypted if empty_encrypted is not None else "")
    print(f"Decrypted empty: '{empty_decrypted}'")
    assert empty_decrypted == ""

    if _fernet_instance: # Only test invalid token if encryption is active
        print("\nTesting decryption of an invalid/tampered token:")
        invalid_encrypted_token = "gAAAAABf..." # Example of a fernet token, likely invalid
        decrypted_invalid = decrypt_token(invalid_encrypted_token)
        print(f"Decryption of invalid token result: {decrypted_invalid} (expected None or error)")
        assert decrypted_invalid is None

    print("\n--- End of Encryption Utilities Demonstration ---")
