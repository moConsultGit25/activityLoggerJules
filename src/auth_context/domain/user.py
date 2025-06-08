# src/auth_context/domain/user.py
import dataclasses
import uuid

@dataclasses.dataclass
class User:
    """
    Represents a user in the system.
    """
    id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    username: str  # Typically an email address
    hashed_password: str
    is_active: bool = True
    # Could add roles, permissions, timestamps, etc. later
    # e.g., roles: List[str] = dataclasses.field(default_factory=list)

    def __post_init__(self):
        # Basic validation
        if not self.username:
            raise ValueError("Username cannot be empty.")
        if not self.hashed_password: # In a real scenario, we might not store users without passwords even if hashed
            raise ValueError("Hashed password cannot be empty.")

# Example (not typically part of the domain model file itself):
if __name__ == '__main__':
    try:
        user1 = User(username="test@example.com", hashed_password="hashed_pw_example")
        print(f"User created: ID={user1.id}, Username={user1.username}, Active={user1.is_active}")

        user2_id = str(uuid.uuid4())
        user2 = User(id=user2_id, username="another@example.com", hashed_password="another_hash", is_active=False)
        print(f"User created: ID={user2.id}, Username={user2.username}, Active={user2.is_active}")

        # Example of invalid creation
        # invalid_user = User(username="", hashed_password="abc") # Should raise ValueError
    except ValueError as e:
        print(f"Error creating user: {e}")
