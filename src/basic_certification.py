from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
import secrets
from uuid import UUID
import logging

from src.models.basic_certification_shemas import MatchCertification, UserTable
from src.models.basic_certification_models import MatchCertificationModel
from src.load_secrets import pepper_data

basic_certification_router = APIRouter()
security = HTTPBasic()
engine = create_async_engine('sqlite:///Lunch_Menu.sqlite', echo=False)
session = async_sessionmaker(
    autocommit=False, class_=AsyncSession, bind=engine
)

class BasicCertification:
    def __init__(self):
        pass

    def get_current_user(self, credentials: HTTPBasicCredentials = Depends(security)):
        username = secrets.compare_digest(credentials.username, "user")
        password = secrets.compare_digest(credentials.password, "password")
        if not (username and password):
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail = "Invalid username or password",
                headers = {"WWW-Authenticate": "Basic"},
            )
        return credentials.username
    
    def check_basic_certification(self, username: str = Depends(get_current_user)):
        return {"username": username}
    
class BasicCertificationCRUD:
    @staticmethod
    async def create_match_certification(match_id: UUID, basic_certification: MatchCertificationModel, team_number: int):
        async with session:
            try:
                new_basic_certification = MatchCertification(
                    username=basic_certification.username,
                    password=basic_certification.password,
                    team_number=team_number,
                    match_id=match_id
                )
                session.add(new_basic_certification)
                await session.commit()

            except Exception as e:
                logging.error(f"Error creating basic certification: {e}")

    @staticmethod
    async def read_basic_certification(match_id: UUID, match_certification: MatchCertificationModel) -> int:
        async with session:
            try:
                stmt = (select(MatchCertification)
                        .where(MatchCertification.match_id == match_id,
                            MatchCertification.username == match_certification.username,
                            MatchCertification.password == match_certification.password
                    )
                )
                result = await session.execute(stmt)
                result = result.scalars().all()
                team_number = result[0].team_number
                return team_number

            except Exception as e:
                logging.error(f"Error reading basic certification: {e}")
                return None
            
    




                