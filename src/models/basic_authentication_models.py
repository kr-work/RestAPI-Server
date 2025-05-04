from datetime import datetime
from pydantic import BaseModel
from uuid import UUID


class MatchAuthenticationModel(BaseModel):
    username: str
    hash_password: str
    match_team_name: str  # "team0" or "team1"
    match_id: UUID
    created_at: datetime
    expired_at: datetime


class UserModel(BaseModel):
    username: str
    hash_password: str
    salt: str