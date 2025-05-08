from datetime import datetime
from pydantic import BaseModel
from uuid import UUID


class UserModel(BaseModel):
    username: str
    hash_password: str
    salt: str
