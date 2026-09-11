from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.config import settings
from app.core.exception import register_exceptions

app = FastAPI(title="群聊日报 API", version="0.2.0")

# 注册全局 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册全局异常处理器 (参照 python_rz 规范)
register_exceptions(app)

# 挂载统一 API 路由 (参照 python_rz 规范)
app.include_router(api_router)
