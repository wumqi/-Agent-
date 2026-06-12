"""
会话相关数据模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class SessionCreateRequest(BaseModel):
    """创建会话请求"""
    title: Optional[str] = Field(default="新会话", description="会话标题")


class SessionResponse(BaseModel):
    """会话响应"""
    id: str = Field(..., description="会话ID")
    title: str = Field(..., description="会话标题")
    user_id: Optional[str] = Field(default=None, description="用户ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class MessageResponse(BaseModel):
    """消息响应"""
    id: str = Field(..., description="消息ID")
    session_id: str = Field(..., description="会话ID")
    role: str = Field(..., description="角色：user/assistant")
    content: str = Field(..., description="消息内容")
    created_at: datetime = Field(..., description="创建时间")


class SessionListResponse(BaseModel):
    """会话列表响应"""
    sessions: List[SessionResponse] = Field(..., description="会话列表")
    total: int = Field(..., description="总数")
