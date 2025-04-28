from pydantic import BaseModel
from uuid import UUID


class MatchAuthenticationModel(BaseModel):
    id: int
    username: str
    hash_password: str
    match_team_name: str  # 0 or 1, so we can use it as "team0" or "team1"
    match_id: UUID


class UserModel(BaseModel):
    username: str
    hash_password: str
    salt: str