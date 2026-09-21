import uuid
from datetime import datetime
from typing import Optional

from fastapi_users import schemas

from pydantic import BaseModel, ConfigDict, Field


class PostCreate(BaseModel):
    title: str = ""


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    url: str
    file_type: str
    file_name: str
    created_at: datetime


class UserRead(schemas.BaseUser[uuid.UUID]):
    username: str


class UserCreate(schemas.BaseUserCreate):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")


class UserUpdate(schemas.BaseUserUpdate):
    username: Optional[str] = Field(
        default=None, min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$"
    )