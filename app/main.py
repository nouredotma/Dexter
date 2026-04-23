from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes.auth import router as auth_router
from app.api.routes.admin import router as admin_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.users import router as users_router
from app.api.routes.ws import router as ws_router
from app.config import get_settings
from app.workers.broker import broker, shutdown_broker, startup_broker


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    try:
        await startup_broker()
    except Exception as exc:
        logger.warning("Broker startup failed (worker may still run separately): {}", exc)

    yield

    try:
        await shutdown_broker()
    except Exception as exc:
        logger.warning("Broker shutdown failed: {}", exc)


def create_app() -> FastAPI:
    settings = get_settings()

    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment)

    app = FastAPI(title="Svet", lifespan=lifespan)

    configured_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if settings.environment == "dev" and settings.cors_origins == "*":
        cors_origins = ["*"]
        cors_credentials = False
    else:
        cors_origins = configured_origins or ["https://example.com"]
        cors_credentials = True

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cors_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(tasks_router)
    app.include_router(admin_router)
    app.include_router(ws_router, prefix="/ws")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    return app


app = create_app()
