from typing import Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class Response(BaseModel, Generic[T]):
    """统一 API 响应格式 (参照 python_rz 规范)"""

    code: int = 0  # 业务状态码，0 代表成功
    message: str = "OK"  # 提示信息
    data: Optional[T] = None  # 实际数据，类型由 T 决定
