"""
闲聊问答节点
"""
from typing import Dict, Any, AsyncGenerator
from agent.multi_agent.nodes.base_node import BaseNode
from model.factory import chat_model
from utils.logger_handler import logger


class ChatNode(BaseNode):
    """闲聊问答节点 - 直接调用大模型生成回答"""
    
    def __init__(self):
        self.model = chat_model
        logger.info("闲聊节点初始化完成")
    
    async def execute(self, user_message: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """执行闲聊问答"""
        try:
            # 构建简单 prompt
            messages = [
                {"role": "system", "content": "你是一个友好、专业的智能客服助手。请用简洁、自然的方式回答用户问题。"},
                {"role": "user", "content": user_message}
            ]
            
            response = self.model.invoke(messages)
            
            return {
                "response": response.content,
                "tool_calls": None
            }
        except Exception as e:
            logger.error(f"闲聊节点执行失败: {e}")
            return {
                "response": "抱歉，我暂时无法回答这个问题。",
                "tool_calls": None
            }
    
    async def execute_stream(self, user_message: str, session_id: str, user_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """流式执行闲聊问答"""
        try:
            messages = [
                {"role": "system", "content": "你是一个友好、专业的智能客服助手。"},
                {"role": "user", "content": user_message}
            ]
            
            # 流式输出
            for chunk in self.model.stream(messages):
                if chunk.content:
                    yield {"type": "content", "data": chunk.content}
                    
        except Exception as e:
            logger.error(f"闲聊节点流式执行失败: {e}")
            yield {"type": "error", "data": str(e)}
