from collections.abc import AsyncGenerator
from datetime import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, DateTime, String, Text, ForeignKey, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv
from sqlalchemy.orm import DeclarativeBase, relationship
from fastapi_users.db import SQLAlchemyUserDatabase, SQLAlchemyBaseUserTableUUID
from fastapi import Depends

import os
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(DATABASE_URL)

session_maker = async_sessionmaker(bind=engine)
Base = declarative_base()


class User(SQLAlchemyBaseUserTableUUID, Base):
    posts = relationship("Post", back_populates="user")


class Post(Base):
    __tablename__ = "posts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    title = Column(Text)
    url = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    file_type = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    user = relationship("User", back_populates="posts")


async def create_db_model():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_posts_table)


def _migrate_posts_table(connection):
    """Bring the original posts table up to date without deleting uploads."""
    inspector = inspect(connection)
    if "posts" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("posts")}
    if "user_id" in columns:
        return

    connection.execute(
        text('ALTER TABLE posts ADD COLUMN user_id CHAR(36) REFERENCES "user" (id)')
    )
    first_user = connection.execute(
        text('SELECT id FROM "user" ORDER BY rowid LIMIT 1')
    ).scalar_one_or_none()
    if first_user is not None:
        connection.execute(
            text("UPDATE posts SET user_id = :user_id WHERE user_id IS NULL"),
            {"user_id": first_user},
        )


async def get_session():
    async with session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_session)):
    yield SQLAlchemyUserDatabase(session, User)
