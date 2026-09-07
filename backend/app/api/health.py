"""Health check endpoint."""

from fastapi import APIRouter
from app.config import get_settings
from app.services.granite import get_granite_service

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    granite = get_granite_service()
    return {
        "status": "ok",
        "app": settings.app_name,
        "granite_configured": granite.is_configured,
        "granite_model": settings.granite_model_id,
    }
