from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.core.config import settings
from api.routers.auth_router import router as auth_router
from api.routers.game_router import router as game_router
from api.routers.match_router import router as match_router
from api.routers.ranking_router import router as ranking_router
from api.routers.user_router import router as user_router
from api.routers.friendship_router import router as friendship_router
from api.routers.library_router import router as library_router
from api.routers.wishlist_router import router as wishlist_router
from api.routers.collection_router import router as collection_router
from api.routers.scoring_template_router import router as scoring_template_router
from api.routers.achievement_router import router as achievement_router
from api.routers.price_router import router as price_router
from api.routers.notification_router import router as notification_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(user_router, prefix="/api/v1")
app.include_router(game_router, prefix="/api/v1")
app.include_router(match_router, prefix="/api/v1")
app.include_router(ranking_router, prefix="/api/v1")
app.include_router(friendship_router, prefix="/api/v1")
app.include_router(library_router, prefix="/api/v1")
app.include_router(wishlist_router, prefix="/api/v1")
app.include_router(collection_router, prefix="/api/v1")
app.include_router(scoring_template_router, prefix="/api/v1")
app.include_router(achievement_router, prefix="/api/v1")
app.include_router(price_router, prefix="/api/v1")
app.include_router(notification_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
