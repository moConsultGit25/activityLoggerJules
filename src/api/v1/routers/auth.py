# src/api/v1/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm # For login form
from typing import Annotated # For Depends with OAuth2PasswordRequestForm in newer FastAPI/Python

from src.auth_context.application.auth_service import AuthService
from src.auth_context.infrastructure.user_repository import MongoUserRepository
from src.auth_context.application.security import create_access_token
# Import Pydantic schemas for request/response models
from ...v1.schemas.auth_schemas import UserCreate, UserResponse, Token

router = APIRouter()

# Dependency to get an instance of MongoUserRepository
# In a real app, a more sophisticated DI system might be used.
def get_user_repository():
    return MongoUserRepository()

# Dependency to get an instance of AuthService
def get_auth_service(user_repo: MongoUserRepository = Depends(get_user_repository)) -> AuthService:
    return AuthService(user_repository=user_repo)


@router.post("/register",
             response_model=UserResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Register a new user.")
async def register_new_user(
    user_in: UserCreate,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Registers a new user in the system.
    - Requires a unique username (email).
    - Password must be at least 8 characters.
    """
    try:
        created_user = auth_service.register_user(user_in)
        # Convert domain User object to UserResponse Pydantic model
        # FastAPI does this automatically if response_model is set and fields match,
        # or if User domain model has Config.from_attributes = True (or orm_mode)
        return UserResponse.model_validate(created_user) # Pydantic v2 way
    except HTTPException as e: # Re-raise HTTPExceptions from service (e.g., user already exists)
        raise e
    except Exception as e: # Catch any other unexpected errors
        print(f"Unexpected error during user registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during user registration."
        )

@router.post("/login",
             response_model=Token,
             summary="User login to obtain an access token.")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], # Username is in form_data.username
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Authenticates a user and returns a JWT access token.
    Uses OAuth2PasswordRequestForm, so client should send data as `application/x-www-form-urlencoded`.
    - `username`: User's email address.
    - `password`: User's plain text password.
    """
    user = auth_service.authenticate_user(
        username=form_data.username,
        password_to_verify=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}, # Part of OAuth2 spec
        )
    if not user.is_active: # Double check, though authenticate_user should also handle this
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, # Or 401, depending on policy
            detail="Inactive user. Please contact support.",
        )

    # Create JWT access token
    # The 'sub' (subject) of the token is typically the username or user ID.
    # Additional data can be added to the token if needed, but keep it minimal.
    access_token_data = {"sub": user.username, "user_id": user.id}
    # Expiration time is handled by create_access_token using default settings
    access_token = create_access_token(data=access_token_data)

    return Token(access_token=access_token, token_type="bearer")

# Example of a protected route (will be fully testable after get_current_user is integrated)
# from src.api.dependencies import get_current_active_user
# from src.auth_context.domain.user import User as DomainUser # For type hinting current_user

# @router.get("/users/me", response_model=UserResponse, summary="Get current authenticated user's details.")
# async def read_users_me(current_user: DomainUser = Depends(get_current_active_user)):
#     """
#     Fetches details for the currently authenticated user.
#     """
#     return UserResponse.model_validate(current_user)
