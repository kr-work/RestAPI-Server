from pydantic import BaseModel


class UserModel(BaseModel):
    """This class is used to create a user model for basic authentication."""
    username: str
    hash_password: str
    salt: str
