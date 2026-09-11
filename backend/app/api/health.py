from fastapi import APIRouter
from app.config import settings
from app.services.ai_service import ai_service

router = APIRouter(tags=["Health"])


@router.get("/health", summary="健康检查")
def health() -> dict:
    return {
        "status": "ok",
        "env": settings.APP_ENV,
        "model_loaded": ai_service.is_loaded,
        "model_path": str(settings.MODEL_PATH),
        "model_exists": settings.MODEL_PATH.exists(),
        "model_error": ai_service.load_error,
    }
