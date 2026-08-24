from fastapi import FastAPI, HTTPException, File, UploadFile, Depends, Form
from src.schemas import PostCreate
from src.db import Post, create_db_model, get_session
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy import select
from src.imagekt import imagekit 
from imagekitio.types import FileUploadParams 
import os 
import shutil
import uuid
import tempfile



@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_model()
    yield


app=FastAPI(lifespan=lifespan)

@app.post("/post")
async def uplaod(file:UploadFile = File(...), title:str= Form(""),
                session: AsyncSession = Depends(get_session)):

    
    post = Post(title = title, url = "sample url", file_type="photo", 
                file_name = "sample name")
    session.add(post)
    await session.commit()
    await session.refresh(post)
    return post

@app.get("/feed")
async def get_feed(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Post).order_by(Post.created_at.desc()))
    posts = [row[0] for row in result.all()]

    posts_data = []
    for post in posts:
        posts_data.append(
            {
                "id" : str(post.id),
                "title" : post.title,
                "url" : post.url,
                "file_type" : post.file_type,
                "file_name" : post.file_name,
                "created_at" : post.created_at.isoformat()
            }
        )
    return {"posts" : posts_data}
