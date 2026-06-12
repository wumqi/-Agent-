"""
多智能体节点基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncGenerator


class BaseNode(ABC):
    """Agent 节点基类"""
    
    @abstractmethod
    async def execute(self, user_message: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """同步执行节点"""
        pass
    
    @abstractmethod
    async def execute_stream(self, user_message: str, session_id: str, user_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """流式执行节点"""
        pass
