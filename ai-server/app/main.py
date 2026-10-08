from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.todo_router import todo
from app.api.routes.rag_router import rag_router
from app.api.routes.eval_router import  eval_router
from app.config import settings
from sqlalchemy import text
from contextlib import asynccontextmanager
from app.lib.db import create_pool, close_pool
from app.lib.alchemy_db import engine

# @asynccontextmanager
# async def lifespan(app:FastAPI):
#     print('lifespan started')

#     async with engine.connect() as conn:
#         await conn.execute(text('SELECT 1'))
#     print('db connected')

#     yield

#     await engine.dispose()
#     print("shutdown: engine disposed")




app = FastAPI(description="this is for ai applications",title=settings.APP_NAME, )

app.add_middleware(CORSMiddleware, allow_headers=["*"],allow_origins=["http://localhost:3000"],  allow_methods=["*"], expose_headers=["*"])

app.include_router(todo, prefix='/api',tags=["todo"] )
app.include_router(rag_router, prefix='/api/rag',tags=["rag"] )
app.include_router(eval_router, prefix='/api/eval',tags=["eval"] )

@app.get('/')
def hello():
    return "hello world"