from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from backend.db import Post, create_db_model, get_session, User
from backend.schemas import PostResponse
from backend.rate_limit import enforce_post_rate_limit
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy import select, func
from backend.imagekt import imagekit
from math import ceil
import uuid
import os
import shutil
import tempfile
from backend.users import fastapi_users, current_active_user, auth_backend
from backend.schemas import UserRead, UserCreate, UserUpdate


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_model()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"]
)
app.include_router(
    fastapi_users.get_reset_password_router(), prefix="/auth", tags=["auth"]
)
app.include_router(
    fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"]
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"]
)


@app.post("/post", response_model=PostResponse, status_code=201)
async def upload(file: UploadFile = File(...), title: str = Form(""),
                 session: AsyncSession = Depends(get_session),
                 user: User = Depends(enforce_post_rate_limit)):

    temp_file_path = None
    try:
        filename = file.filename or "upload"
        content_type = file.content_type or ""
        suffix = os.path.splitext(filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)

        def upload_to_imagekit():
            with open(temp_file_path, "rb") as upload_file:
                return imagekit.files.upload(
                    file=upload_file,
                    file_name=filename,
                    use_unique_file_name=True,
                    tags=["backend-upload"],
                )

        upload_result = await run_in_threadpool(upload_to_imagekit)

        post = Post(
            user_id=user.id,
            title=title,
            url=upload_result.url,
            file_type="video" if content_type.startswith(
                "video/") else "image",
            file_name=upload_result.name,
        )
        session.add(post)
        await session.commit()
        await session.refresh(post)
        return post

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        file.file.close()


@app.get("/feed")
async def get_feed(
    page: int = Query(1, ge=1, description="1-indexed page number"),
    page_size: int = Query(10, ge=1, le=50, description="Posts per page"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    offset = (page - 1) * page_size

    total_result = await session.execute(select(func.count()).select_from(Post))
    total_posts = total_result.scalar_one()

    result = await session.execute(
        select(Post).order_by(Post.created_at.desc()).offset(offset).limit(page_size)
    )
    posts = result.scalars().all()

    result = await session.execute(select(User))
    users = [row[0] for row in result.all()]
    user_dict = {u.id: u.username for u in users}

    posts_data = []
    for post in posts:
        posts_data.append(
            {
                "id": str(post.id),
                "user_id": str(post.user_id),
                "title": post.title,
                "url": post.url,
                "file_type": post.file_type,
                "file_name": post.file_name,
                "created_at": post.created_at.isoformat(),
                "is_owner": post.user_id == user.id,
                "username": user_dict.get(post.user_id, "Unknown"),
            }
        )

    total_pages = ceil(total_posts / page_size) if total_posts else 1

    return {
        "posts": posts_data,
        "page": page,
        "page_size": page_size,
        "total_posts": total_posts,
        "total_pages": total_pages,
    }


@app.delete("/posts/{post_id}")
async def delete_post(post_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(current_active_user)):
    try:
        post_uuid = uuid.UUID(post_id)
        result = await session.execute(select(Post).where(Post.id == post_uuid))
        post = result.scalars().first()

        if not post:
            raise HTTPException(status_code=404, detail="post not found")
        if post.user_id != user.id:
            raise HTTPException(
                status_code=403, detail="you don't have permission to delete this post")
        await session.delete(post)
        await session.commit()

        return {"message": "post deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))