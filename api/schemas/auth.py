"""
认证相关数据模型
"""
from pydantic import BaseModel, Field
from typing import Optional


class TokenRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class TokenResponse(BaseModel):
    """登录响应"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(default=3600, description="过期时间（秒）")


class UserInfo(BaseModel):
    """用户信息"""
    user_id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    role: str = Field(default="user", description="角色")
