from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from src.db import Post, create_db_model, get_session
from src.schemas import PostResponse
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy import select
from src.imagekt import imagekit
import uuid
import os
import shutil
import tempfile


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_model()
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/post", response_model=PostResponse, status_code=201)
async def upload(file: UploadFile = File(...), title: str = Form(""),
                 session: AsyncSession = Depends(get_session)):

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
async def get_feed(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Post).order_by(Post.created_at.desc()))
    posts = result.scalars().all()

    posts_data = []
    for post in posts:
        posts_data.append(
            {
                "id": str(post.id),
                "title": post.title,
                "url": post.url,
                "file_type": post.file_type,
                "file_name": post.file_name,
                "created_at": post.created_at.isoformat()
            }
        )
    return {"posts": posts_data}


@app.delete("/posts/{post_id}")
async def delete_post(post_id: str, session: AsyncSession = Depends(get_session)):
    try:
        post_uuid = uuid.UUID(post_id)
        result = await session.execute(select(Post).where(Post.id == post_uuid))
        post = result.scalars().first()

        if not post:
            raise HTTPException(status_code=404, detail="post not found")
        await session.delete(post)
        await session.commit()

        return {"message" : "post deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))