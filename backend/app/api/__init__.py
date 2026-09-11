from fastapi import APIRouter
from app.api.backup import router as backup_router
from app.api.health import router as health_router
from app.api.reports import router as reports_router
from app.api.tasks import router as tasks_router

# 主路由 (参照 python_rz 规范)
router = APIRouter(prefix="/api")

# 注册各个子模块路由
router.include_router(health_router)
router.include_router(reports_router)
router.include_router(tasks_router)
router.include_router(backup_router)

__all__ = ["router"]

