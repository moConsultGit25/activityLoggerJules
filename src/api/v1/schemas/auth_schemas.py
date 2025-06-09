# src/api/v1/schemas/auth_schemas.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class UserBase(BaseModel):
    username: EmailStr # Treat username as email

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="User password, must be at least 8 characters.")

class UserResponse(UserBase):
    id: str
    is_active: bool

    class Config:
        from_attributes = True # For compatibility with User domain model (dataclass)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    # Could include other claims like scopes, user_id, etc.

# For password change requests (example, not implemented in this subtask)
# class PasswordChange(BaseModel):
#     current_password: str
#     new_password: str = Field(..., min_length=8)

class M365ConnectionStatus(BaseModel):
    is_connected: bool
    account_email: Optional[str] = None # Email of the connected M365 account
    error: Optional[str] = None # If there was an error checking status or token is invalid
