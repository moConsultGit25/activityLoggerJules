# src/api/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# AuthContext components
from src.auth_context.application.security import decode_access_token
# Assuming TokenData schema is defined where security functions are, or import it
# from src.auth_context.application.security import TokenData # Not a schema, but type hint for payload
from src.api.v1.schemas.auth_schemas import TokenData # Use Pydantic schema for payload structure

from src.auth_context.domain.user import User as DomainUser # Domain model
from src.auth_context.infrastructure.user_repository import MongoUserRepository


# OAuth2 scheme definition
# tokenUrl should point to your login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Dependency to get an instance of MongoUserRepository
# This is a simple way; a more complex app might use a DI container.
def get_user_repository_dependency():
    return MongoUserRepository()

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_repo: MongoUserRepository = Depends(get_user_repository_dependency)
) -> DomainUser:
    """
    Decodes JWT token, retrieves user from repository, and returns the User domain object.
    This is a dependency that can be used in path operations to get the authenticated user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None: # Token is invalid, expired, or decoding failed
        raise credentials_exception

    # Validate payload structure using TokenData Pydantic model
    try:
        token_data = TokenData(**payload) # FastAPI automatically handles 'sub' to 'username' if needed by TokenData
        # If 'sub' is used directly and TokenData expects 'username', ensure 'sub' is mapped.
        # The current decode_access_token returns the raw payload which includes 'sub'.
        # If TokenData has 'username', and 'sub' is the username, this mapping is needed.
        # For now, let's assume payload directly contains 'username' or 'sub' is used.
        # The `create_access_token` uses `sub` for username.
        username_from_payload = payload.get("sub") # 'sub' is standard for subject (username)
        if username_from_payload is None: # Check if 'sub' (username) is in payload
             username_from_payload = token_data.username # Fallback if TokenData has username

    except Exception: # Pydantic ValidationError if payload doesn't match TokenData
        raise credentials_exception # Or a more specific error for bad token data

    if username_from_payload is None:
        print("Error: Username not found in token payload.")
        raise credentials_exception

    user = user_repo.get_by_username(username_from_payload)
    if user is None:
        print(f"Error: User '{username_from_payload}' from token not found in repository.")
        raise credentials_exception # User from token not found in DB

    return user


async def get_current_active_user(
    current_user: DomainUser = Depends(get_current_user)
) -> DomainUser:
    """
    Dependency that ensures the user fetched from token is active.
    Relies on get_current_user to first validate token and fetch user.
    """
    if not current_user.is_active:
        print(f"User '{current_user.username}' is inactive.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user


# Example of how to use these dependencies in a router:
# from fastapi import APIRouter
# router = APIRouter()
# @router.get("/users/me")
# async def read_users_me(current_active_user: DomainUser = Depends(get_current_active_user)):
#     return current_active_user
#
# @router.get("/items/")
# async def read_items(current_user_optional: Optional[DomainUser] = Depends(get_current_user_optional)):
#    # If you want an endpoint that can be accessed by anyone, but provides extra info for logged-in users
#    # you'd need a get_current_user_optional that doesn't raise HTTPException if token is missing/invalid
#    pass
