"""
全局异常捕获与标准化错误码
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import traceback
import logging

logger = logging.getLogger(__name__)

# 标准化错误码定义
ERROR_CODES = {
    # 系统级错误 (1000-1999)
    1000: {"message": "系统内部错误", "status_code": 500},
    1001: {"message": "服务暂时不可用", "status_code": 503},
    1002: {"message": "请求超时", "status_code": 504},
    
    # 认证授权错误 (2000-2999)
    2000: {"message": "未授权访问", "status_code": 401},
    2001: {"message": "令牌已过期", "status_code": 401},
    2002: {"message": "令牌无效", "status_code": 401},
    2003: {"message": "权限不足", "status_code": 403},
    
    # 请求参数错误 (3000-3999)
    3000: {"message": "请求参数错误", "status_code": 400},
    3001: {"message": "请求体格式错误", "status_code": 400},
    3002: {"message": "缺少必要参数", "status_code": 400},
    3003: {"message": "参数类型错误", "status_code": 400},
    
    # 业务逻辑错误 (4000-4999)
    4000: {"message": "资源不存在", "status_code": 404},
    4001: {"message": "会话不存在", "status_code": 404},
    4002: {"message": "消息发送失败", "status_code": 500},
    4003: {"message": "Agent 执行失败", "status_code": 500},
    4004: {"message": "知识库检索失败", "status_code": 500},
    
    # 限流错误 (5000-5999)
    5000: {"message": "请求过于频繁", "status_code": 429},
}


class BusinessException(Exception):
    """业务异常基类"""
    def __init__(self, code: int, message: str = None, detail: str = None):
        self.code = code
        self.message = message or ERROR_CODES.get(code, {}).get("message", "未知错误")
        self.detail = detail
        super().__init__(self.message)


def get_error_response(code: int, detail: str = None) -> dict:
    """获取标准化错误响应"""
    error_info = ERROR_CODES.get(code, ERROR_CODES[1000])
    return {
        "code": code,
        "message": error_info["message"],
        "detail": detail,
    }


async def business_exception_handler(request: Request, exc: BusinessException):
    """业务异常处理器"""
    error_info = ERROR_CODES.get(exc.code, ERROR_CODES[1000])
    logger.warning(f"业务异常: code={exc.code}, message={exc.message}, detail={exc.detail}")
    return JSONResponse(
        status_code=error_info["status_code"],
        content=get_error_response(exc.code, exc.detail),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """参数校验异常处理器"""
    errors = exc.errors()
    detail = "; ".join([f"{e['loc'][-1]}: {e['msg']}" for e in errors])
    logger.warning(f"参数校验失败: {detail}")
    return JSONResponse(
        status_code=400,
        content=get_error_response(3000, detail),
    )


async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    error_trace = traceback.format_exc()
    logger.error(f"全局异常: {str(exc)}\n{error_trace}")
    return JSONResponse(
        status_code=500,
        content=get_error_response(1000, str(exc)),
    )


def register_exception_handlers(app):
    """注册异常处理器"""
    app.add_exception_handler(BusinessException, business_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
