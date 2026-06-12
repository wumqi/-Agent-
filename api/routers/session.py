"""
会话管理路由
"""
from fastapi import APIRouter, Depends
from api.schemas.session import SessionCreateRequest, SessionResponse, SessionListResponse
from api.middleware.auth import get_current_active_user
from api.middleware.exception import BusinessException
from utils.session_manager import SessionManager
from typing import List

router = APIRouter(prefix="/sessions", tags=["会话"])
session_manager = SessionManager()


@router.post("", response_model=SessionResponse)
async def create_session(
    request: SessionCreateRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """创建新会话"""
    user_id = current_user["user_id"]
    session = session_manager.create_session(user_id)
    return SessionResponse(**session)


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    current_user: dict = Depends(get_current_active_user)
):
    """获取会话列表"""
    user_id = current_user["user_id"]
    sessions = session_manager.get_all_sessions(user_id)
    return SessionListResponse(
        sessions=[SessionResponse(**s) for s in sessions],
        total=len(sessions)
    )


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """获取会话详情"""
    session = session_manager.get_session(session_id)
    if not session:
        raise BusinessException(4001, detail=f"会话不存在: {session_id}")
    return {"code": 200, "data": session}


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """删除会话"""
    success = session_manager.delete_session(session_id)
    if not success:
        raise BusinessException(4001, detail=f"删除会话失败: {session_id}")
    return {"code": 200, "message": "删除成功"}


@router.get("/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """获取会话消息列表"""
    messages = session_manager.get_messages(session_id)
    return {"code": 200, "data": messages}
