import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.mongodb import close_mongo_connection, connect_to_mongo
from app.routers import auth, health, resume, sessions, users
from app.services import asr


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    # Load Whisper in the background: it takes ~15s, and doing it here means the
    # first candidate to speak doesn't wait for it, while startup isn't blocked.
    warm_up_task = asyncio.create_task(asr.warm_up())
    yield
    warm_up_task.cancel()
    await close_mongo_connection()


app = FastAPI(title="ARIA API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(resume.router)
app.include_router(sessions.router)
