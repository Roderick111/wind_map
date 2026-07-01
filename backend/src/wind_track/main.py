"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from wind_track.api.routes import router
from wind_track.config.settings import settings
from wind_track.db.migrate import ensure_database


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await ensure_database()
    yield


app = FastAPI(
    title="Wind Track API",
    version=settings.pipeline_version,
    description="Urban wind exposure screening for Lyon",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

settings.tiles_dir.mkdir(parents=True, exist_ok=True)
app.mount("/tiles", StaticFiles(directory=settings.tiles_dir), name="tiles")