from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.services.store import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await init_db()
        yield


def create_app() -> FastAPI:
        app = FastAPI(
                    title="AI Workflow MVP",
                    version="0.2.0",
                    description="AI-powered workflow automation API.",
                    lifespan=lifespan,
        )
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        app.include_router(router)
        return app


app = create_app()
