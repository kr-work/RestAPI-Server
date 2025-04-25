from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.schema import Column
from sqlalchemy.types import Integer, String, Uuid, Float, DateTime, TEXT
from uuid import UUID
from typing import Optional, Dict, List

class Base(DeclarativeBase):
    pass

class UserTable(Base):
    __tablename__ = "users"
    username = Column(String, primary_key=True, index=True)
    hash_password = Column(String)
    salt = Column(String)

