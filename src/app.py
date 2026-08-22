from fastapi import FastAPI, HTTPException, File, UploadFile, Depends, Form
from src.schemas import PostCreate
from src.db import Post, create_db_model, get_session
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy import select


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
    