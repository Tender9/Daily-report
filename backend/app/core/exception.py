from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class BusinessException(Exception):
    """自定义业务异常 (参照 python_rz 规范)"""

    def __init__(self, code: int = 4001, message: str = "业务异常"):
        self.code = code
        self.message = message
        super().__init__(message)


def register_exceptions(app: FastAPI) -> None:
    """注册全局异常处理器"""

    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        return JSONResponse(
            status_code=200,
            content={"code": exc.code, "message": exc.message, "data": None},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"code": 5000, "message": f"系统内部错误: {str(exc)}", "data": None},
        )
