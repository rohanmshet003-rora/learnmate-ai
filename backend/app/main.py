"""LearnMate AI — FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.api import health, students, assessment, roadmap, progress, learn


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_db()
        yield

    app = FastAPI(
        title=settings.app_name,
        description="Agentic Personalised Learning Pathway powered by IBM Granite.",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health.router, prefix="/api")
    app.include_router(students.router, prefix="/api")
    app.include_router(assessment.router, prefix="/api")
    app.include_router(roadmap.router, prefix="/api")
    app.include_router(progress.router, prefix="/api")
    app.include_router(learn.router, prefix="/api")

    return app


app = create_app()
