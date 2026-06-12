"""
聊天相关数据模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")
    session_id: Optional[str] = Field(default=None, description="会话ID")
    stream: bool = Field(default=True, description="是否流式输出")


class ChatResponse(BaseModel):
    """聊天响应"""
    message: str = Field(..., description="助手回答")
    session_id: str = Field(..., description="会话ID")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(default=None, description="工具调用记录")
    reflection: Optional[Dict[str, Any]] = Field(default=None, description="反思结果")


class StreamChunk(BaseModel):
    """SSE 流式数据块"""
    type: str = Field(..., description="数据类型：content/tool/reflection/done/error")
    data: Any = Field(..., description="数据内容")
    session_id: str = Field(..., description="会话ID")
