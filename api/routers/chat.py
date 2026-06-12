"""
聊天路由 - SSE 流式问答
"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from api.schemas.chat import ChatRequest
from api.middleware.auth import get_current_active_user
from api.middleware.exception import BusinessException
from agent.multi_agent.supervisor import SupervisorAgent
from utils.session_manager import SessionManager
import json
import asyncio

router = APIRouter(prefix="/chat", tags=["聊天"])

# 初始化 Supervisor
supervisor = SupervisorAgent()
session_manager = SessionManager()


async def stream_chat_response(user_message: str, session_id: str, user_id: str):
    """流式生成聊天响应"""
    try:
        # 发送用户消息到会话
        session_manager.add_message(session_id, "user", user_message)
        
        # 通过 Supervisor 处理请求
        async for chunk in supervisor.process_stream(user_message, session_id, user_id):
            yield f"data: {json.dumps(chunk)}\n\n"
            await asyncio.sleep(0.01)
        
        # 发送结束标记
        yield f"data: {json.dumps({'type': 'done', 'data': '', 'session_id': session_id})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'data': str(e), 'session_id': session_id})}\n\n"


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """SSE 流式问答接口"""
    user_id = current_user["user_id"]
    session_id = request.session_id
    
    # 如果没有 session_id，创建新会话
    if not session_id:
        session = session_manager.create_session(user_id)
        session_id = session["id"]
    else:
        # 验证会话是否存在
        session = session_manager.get_session(session_id)
        if not session:
            raise BusinessException(4001, detail=f"会话不存在: {session_id}")
    
    return StreamingResponse(
        stream_chat_response(request.message, session_id, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-Id": session_id,
        }
    )


@router.post("/send")
async def chat_send(
    request: ChatRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """非流式问答接口"""
    user_id = current_user["user_id"]
    session_id = request.session_id
    
    if not session_id:
        session = session_manager.create_session(user_id)
        session_id = session["id"]
    
    try:
        # 添加用户消息
        session_manager.add_message(session_id, "user", request.message)
        
        # 通过 Supervisor 处理
        result = await supervisor.process(request.message, session_id, user_id)
        
        return {
            "code": 200,
            "message": "success",
            "data": {
                "message": result["response"],
                "session_id": session_id,
                "tool_calls": result.get("tool_calls"),
                "reflection": result.get("reflection"),
            }
        }
    except Exception as e:
        raise BusinessException(4003, detail=str(e))
