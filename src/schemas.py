import uuid
from datetime import datetime
from fastapi import schemas

from pydantic import BaseModel, ConfigDict


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
    pass

class UserCreate(schemas.BaseUserCreate):
    pass

class UserUpdate(schemas.BaseUserUpdate):
    pass