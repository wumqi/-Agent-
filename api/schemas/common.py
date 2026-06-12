"""
通用数据模型
"""
from pydantic import BaseModel, Field
from typing import Any, Optional


class ApiResponse(BaseModel):
    """标准 API 响应"""
    code: int = Field(default=200, description="状态码")
    message: str = Field(default="success", description="消息")
    data: Optional[Any] = Field(default=None, description="数据")


class ErrorResponse(BaseModel):
    """错误响应"""
    code: int = Field(..., description="错误码")
    message: str = Field(..., description="错误消息")
    detail: Optional[str] = Field(default=None, description="详细错误信息")
