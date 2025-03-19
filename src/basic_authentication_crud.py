import hashlib
import logging
import secrets
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from typing import Tuple
from uuid import UUID

from src.models.basic_authentication_shemas import MatchAuthentication, UserTable, Base
from src.models.basic_authentication_models import MatchAuthenticationModel, UserModel
from src.models.dc_models import MatchNameModel
from src.create_sqlite_engine import engine
from src.load_secrets import pepper_data

Session = async_sessionmaker(
    autocommit=False, class_=AsyncSession, bind=engine
)
session = Session()
logging.basicConfig(level=logging.INFO)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)


class CreateAuthentication:

    @staticmethod
    async def create_table() -> None:
        """Create table if not exists"""
        try:
            async with engine.begin() as conn:
                # テーブル作成 (既存テーブルがある場合はスキップされる)
                await conn.run_sync(Base.metadata.create_all)
        except IntegrityError as e:
            logging.warning(f"Table already exists or other integrity error: {e}")

    @staticmethod
    async def create_user_data(username: str, password: str):
        """Create user data to authenticate the user

        Args:
            user (UserModel): username and password which
        """
        await CreateAuthentication.create_table()
        salt = secrets.token_hex(8)
        password = hashlib.sha256((password + salt + pepper_data).encode()).hexdigest()
        async with session:
            try:
                new_user = UserTable(
                    username=username,
                    hash_password=password,
                    salt=salt
                )
                session.add(new_user)
                await session.commit()

            except Exception as e:
                logging.error(f"Error creating user data: {e}")

    @staticmethod
    async def create_match_authentication(match_id: UUID, user_data: UserModel, match_team_name: MatchNameModel) -> MatchNameModel | None:
        """Create Basic Authentication information required for the match

        Args:
            match_id (UUID): _description_
            basic_authentication (MatchauthenticationModel): _description_
            team_number (int): _description_
        """        
        async with session:
            try:
                new_basic_authentication = MatchAuthentication(
                    username=user_data.username,
                    hash_password=user_data.hash_password,
                    match_team_name=match_team_name,
                    match_id=match_id
                )
                session.add(new_basic_authentication)
                await session.commit()

                return match_team_name

            except Exception as e:
                logging.error(f"Error creating basic authentication: {e}")
                return None


class ReadAuthentication:
    @staticmethod
    async def read_user_data(username: str) -> UserModel:
        """Read user data to get salt and password hash

        Args:
            username (str): username of the user

        Returns:
            UserModel: username, password and salt
        """
        async with session:
            try:
                stmt = (select(UserTable)
                        .where(UserTable.username == username)
                )
                result = await session.execute(stmt)
                result = result.scalars().first()
                if result is None:
                    logging.error("User not found")
                    return None
                user = UserModel(
                    username=result.username,
                    hash_password=result.hash_password,
                    salt=result.salt
                )
                return user

            except Exception as e:
                logging.error(f"Error reading user data: {e}")
                return None

    @staticmethod
    async def read_match_team_name(match_id: UUID) -> Tuple[bool, bool]:
        """Read team number for the match

        Args:
            match_id (UUID): ID to identify this match

        Returns:
            Tuple[bool, bool]: True if match team name exists, False if it does not exist
        """
        logging.info(f"match_id: {match_id}")
        async with session:
            try:
                stmt = (select(MatchAuthentication)
                        .where(MatchAuthentication.match_id == match_id)
                )
                result = await session.execute(stmt)
                result = result.scalars().all()
                # logging.info(f"result[0]: {result[0]}")
                # logging.info(f"result[0].match_team_name: {result[0].match_team_name}")
                # logging.info(f"len(result): {len(result)}")
                if len(result) == 0:
                    return [False, False]
                elif len(result) == 1:
                    if result[0].match_team_name == "team0":
                        return [True, False]
                    elif result[0].match_team_name == "team1":
                        return [False, True]
                return [True, True]

            except Exception as e:
                logging.error(f"Error reading match team name: {e}")

    @staticmethod
    async def read_basic_authentication(match_authentication: MatchAuthenticationModel) -> MatchNameModel:
        """Read basic authentication information for the match

        Args:
            match_id (UUID): ID to identify this match
            match_authentication (MatchAuthenticationModel): username and password

        Returns:
            int: _description_
        """        
        async with session:
            try:
                stmt = (select(MatchAuthentication)
                        .where(MatchAuthentication.match_id == match_authentication.match_id,
                            MatchAuthentication.username == match_authentication.username,
                            MatchAuthentication.hash_password == match_authentication.hash_password
                    )
                )
                result = await session.execute(stmt)
                result = result.scalars().all()
                match_team_name = result[0].team_number
                match_team_name = MatchNameModel(match_team_name=match_team_name)
                return match_team_name

            except Exception as e:
                logging.error(f"Error reading basic authentication: {e}")
                return None
            
    @staticmethod
    async def read_match_id(match_id: UUID) -> bool|None:
        """Read match id to check if it exists

        Args:
            match_id (UUID): ID to identify this match

        Returns:
            bool|None: True if match id exists, False if it does not exist, None if there is an error
        """        
        async with session:
            try:
                stmt = (select(MatchAuthentication)
                        .where(MatchAuthentication.match_id == match_id)
                )
                result = await session.execute(stmt)
                result = result.scalars().all()
                if result is None:
                    return False
                return True
            
            except Exception as e:
                logging.error(f"Error reading match id: {e}")
                return None
            

            