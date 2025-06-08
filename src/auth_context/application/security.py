# src/auth_context/application/security.py
import os
import secrets # For generating default secret key
from datetime import datetime, timedelta, timezone # Added timezone for UTC consistency
from typing import Dict, Any, Optional

from passlib.context import CryptContext
from jose import JWTError, jwt # python-jose library

# --- Password Hashing ---
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hashes a plain text password using bcrypt."""
    return password_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against its hashed version."""
    return password_context.verify(plain_password, hashed_password)

# --- JWT Token Handling ---

# Configuration for JWT
# It's crucial to keep SECRET_KEY secure and not hardcoded in production.
# Load from environment variable, with a default for development (and a warning).
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if JWT_SECRET_KEY is None:
    print("WARNING: JWT_SECRET_KEY environment variable not set. Using a default development key.")
    print("         This is INSECURE for production. Set a strong secret key in your environment.")
    JWT_SECRET_KEY = secrets.token_urlsafe(32) # Generate a reasonably strong default for dev

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30")) # Default to 30 minutes

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a new JWT access token.

    Args:
        data (Dict[str, Any]): Data to encode into the token (typically user identifier).
        expires_delta (Optional[timedelta]): Custom expiration time. Defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        str: The encoded JWT access token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    # Add 'sub' (subject) claim, commonly used for user ID or username
    if "sub" not in to_encode and "username" in to_encode: # Assuming 'username' is the primary identifier for 'sub'
        to_encode["sub"] = to_encode["username"]

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes a JWT access token.

    Args:
        token (str): The JWT token string to decode.

    Returns:
        Optional[Dict[str, Any]]: The decoded payload if the token is valid and not expired,
                                   otherwise None.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        # 'exp' claim is automatically verified by jwt.decode
        # You might want to check for 'sub' or other essential claims here
        # username: str = payload.get("sub") # Example: get subject
        # if username is None:
        #     return None # Or raise custom error
        return payload
    except jwt.ExpiredSignatureError:
        print("Token decoding failed: Expired signature.")
        return None
    except JWTError as e: # Broad exception for other JWT issues (malformed, invalid signature, etc.)
        print(f"Token decoding failed: Invalid token. Error: {e}")
        return None
    except Exception as e: # Catch any other unexpected errors
        print(f"An unexpected error occurred during token decoding: {e}")
        return None

# Example Usage (for demonstration)
if __name__ == '__main__':
    print("--- Security Utilities Demonstration ---")

    # Password Hashing
    plain_pw = "supersecretpassword"
    hashed_pw = hash_password(plain_pw)
    print(f"\nPlain password: {plain_pw}")
    print(f"Hashed password: {hashed_pw}")
    print(f"Verification (correct): {verify_password(plain_pw, hashed_pw)}")
    print(f"Verification (incorrect): {verify_password('wrongpassword', hashed_pw)}")

    # JWT Token Creation and Decoding
    print(f"\nUsing JWT Secret Key (first 10 chars): {JWT_SECRET_KEY[:10]}...") # Print only a part for safety
    print(f"Access token expires in: {ACCESS_TOKEN_EXPIRE_MINUTES} minutes")

    user_data_for_token = {"username": "testuser@example.com", "user_id": "user123"}
    access_token = create_access_token(data=user_data_for_token)
    print(f"\nGenerated Access Token: {access_token}")

    decoded_payload = decode_access_token(access_token)
    if decoded_payload:
        print(f"Decoded Token Payload: {decoded_payload}")
        assert decoded_payload["sub"] == user_data_for_token["username"]
        assert decoded_payload["user_id"] == user_data_for_token["user_id"]
    else:
        print("Token decoding failed or token was invalid/expired.")

    # Test expired token
    expired_token_custom_delta = create_access_token(data=user_data_for_token, expires_delta=timedelta(seconds=-1))
    print(f"\nGenerated Expired Token (custom delta): {expired_token_custom_delta}")
    decoded_expired_payload = decode_access_token(expired_token_custom_delta)
    print(f"Decoding expired token (custom delta) result: {decoded_expired_payload is None} (expected True)")
    assert decoded_expired_payload is None

    # Test invalid token
    invalid_token_string = "this.is.not.a.valid.token"
    print(f"\nDecoding invalid token string: '{invalid_token_string}'")
    decoded_invalid_token = decode_access_token(invalid_token_string)
    print(f"Decoding invalid token result: {decoded_invalid_token is None} (expected True)")
    assert decoded_invalid_token is None

    print("\n--- End of Security Utilities Demonstration ---")
