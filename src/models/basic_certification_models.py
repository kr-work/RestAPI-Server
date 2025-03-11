from pydantic import BaseModel
from uuid import UUID

class MatchCertificationModel(BaseModel):
    username: str
    password: str
    match_id: UUID