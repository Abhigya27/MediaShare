import os
import secrets
import string
import uuid
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, exceptions
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.password import PasswordHelperProtocol
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher
from sqlalchemy import select

from backend.db import User, get_user_db

load_dotenv()

SECRET = os.getenv("SECRET_KEY")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "20"))


class BcryptPasswordHelper(PasswordHelperProtocol):

    def __init__(self) -> None:
        self.password_hash = PasswordHash((BcryptHasher(),))

    def verify_and_update(self, plain_password: str, hashed_password: str):
        return self.password_hash.verify_and_update(plain_password, hashed_password)

    def hash(self, password: str) -> str:
        return self.password_hash.hash(password)

    def generate(self) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(20))


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    def __init__(self, user_db: SQLAlchemyUserDatabase):
        super().__init__(user_db, password_helper=BcryptPasswordHelper())

    async def validate_password(self, password: str, user) -> None:
        if len(password) < 8:
            raise exceptions.InvalidPasswordException(
                reason="Password must be at least 8 characters long."
            )
        if len(password.encode("utf-8")) > 72:
            raise exceptions.InvalidPasswordException(
                reason="Password must be at most 72 bytes long."
            )

    async def get_by_username(self, username: str) -> User:
        session = self.user_db.session
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None:
            raise exceptions.UserNotExists()
        return user

    async def authenticate(self, credentials: OAuth2PasswordRequestForm) -> Optional[User]:
        try:
            user = await self.get_by_username(credentials.username)

        except exceptions.UserNotExists:
            self.password_helper.hash(credentials.password)
            return None

        verified, updated_password_hash = self.password_helper.verify_and_update(
            credentials.password, user.hashed_password
        )
        if not verified:
            return None
        if updated_password_hash is not None:
            await self.user_db.update(user, {"hashed_password": updated_password_hash})
        if not user.is_active:
            return None
        return user

    async def create(self, user_create, safe: bool = False, request: Optional[Request] = None) -> User:
        existing = await self.user_db.session.execute(
            select(User).where(User.username == user_create.username)
        )
        if existing.scalar_one_or_none() is not None:
            raise exceptions.UserAlreadyExists()
        return await super().create(user_create, safe, request)

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.username} ({user.id}) has registered.")

    async def on_after_forgot_password(self, user: User, token: str, request: Optional[Request] = None):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(self, user: User, token: str, request: Optional[Request] = None):
        print(f"Verification requested for user {user.id}. Verification token: {token}")


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy():
    return JWTStrategy(secret=SECRET, lifetime_seconds=ACCESS_TOKEN_EXPIRE_MINUTES * 60)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])
current_active_user = fastapi_users.current_user(active=True)