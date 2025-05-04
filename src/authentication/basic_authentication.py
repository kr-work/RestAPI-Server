from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
import secrets
import hashlib
import asyncio
import logging
from uuid import UUID
from typing import Tuple

from src.crud import ReadData, UpdateData
from src.models.basic_authentication_shemas import UserTable
from src.models.basic_authentication_models import UserModel
from src.authentication.basic_authentication_crud import (
    CreateAuthentication,
    ReadAuthentication,
)
from src.models.dc_models import MatchNameModel
from src.load_secrets import pepper_data

basic_authentication_router = APIRouter()
security = HTTPBasic()
create_auth = CreateAuthentication()
read_auth = ReadAuthentication()
read_data = ReadData()
update_data = UpdateData()


class BasicAuthentication:
    def __init__(self):
        pass

    async def check_user_data(self, credentials: HTTPBasicCredentials = Depends(security)) -> UserModel:
        """Check if the user data is valid. This function is called only once before the start of the match

        Args:
            credentials (HTTPBasicCredentials, optional): _description_. Defaults to Depends(security).

        Raises:
            HTTPException: The first time the user data is checked, the user data is not found in the database
            HTTPException: The password is incorrect

        Returns:
            bool: Basic authentication result
        """        
        # await create_auth.create_user_data("user", "password")

        user_data: UserModel = await read_auth.read_user_data(credentials.username)
        if user_data is None:
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail = "Invalid username",
                headers = {"WWW-Authenticate": "Basic"},
            )

        hashed_password = hashlib.sha256((credentials.password + user_data.salt + pepper_data).encode()).hexdigest()

        if not secrets.compare_digest(hashed_password, user_data.hash_password):
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail = "Invalid password",
                headers = {"WWW-Authenticate": "Basic"},
            )
        return user_data
    
    async def check_match_data(self, user_data: UserModel, match_id: UUID) -> str:
        """Check if the match data is valid. This function is called only once before the start of the match

        Args:
            user_data (UserModel): _description_
            match_id (UUID): _description_

        Raises:
            HTTPException: The first time the user data is checked, the user data is not found in the database
            HTTPException: The password is incorrect

        Returns:
            bool: Basic authentication result
        """        
        match_data = await read_auth.read_match_data(user_data, match_id)
        if match_data is None:
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail = "Invalid match data",
                headers = {"WWW-Authenticate": "Basic"},
            )
        return match_data.match_team_name
    # 
    async def store_user_data(self, user_name: str, password: str) -> None:
        await create_auth.create_user_data(user_name, password)

    # read all user data
    async def read_user_data(self) -> UserModel:
        return await read_auth.read_user_data(username="user")


async def main(user_name: str, password: str):
    basic_auth = BasicAuthentication()
    await basic_auth.store_user_data(user_name, password)
    user_data = await basic_auth.read_user_data()
    print(user_data.username, user_data.hash_password, user_data.salt)

    
if __name__ == "__main__":
    asyncio.run(main("user", "password"))