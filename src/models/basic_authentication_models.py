from pydantic import BaseModel
from uuid import UUID

class MatchAuthenticationModel(BaseModel):
    username: str
    hash_password: str
    match_id: UUID

class UserModel(BaseModel):
    username: str
    hash_password: str
    salt: str