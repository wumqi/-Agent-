"""
异常兜底节点
"""
from typing import Dict, Any, AsyncGenerator
from agent.multi_agent.nodes.base_node import BaseNode
from model.factory import chat_model
from utils.logger_handler import logger


class FallbackNode(BaseNode):
    """
    异常兜底节点
    
    当其他节点执行失败或无法处理时，提供友好的兜底响应。
    """
    
    def __init__(self):
        self.model = chat_model
        logger.info("异常兜底节点初始化完成")
    
    # 兜底响应模板
    FALLBACK_RESPONSES = [
        "抱歉，我暂时无法理解您的问题。您可以尝试：\n1. 用更简洁的语言描述\n2. 询问公司的相关制度或流程\n3. 联系人工客服获取帮助",
        "抱歉，处理您的请求时出现问题。建议您：\n1. 刷新页面后重试\n2. 重新描述您的问题\n3. 如果问题持续，请联系技术支持",
        "您好，我遇到了一些技术问题。您可以：\n1. 稍后再试\n2. 换个方式提问\n3. 联系管理员协助处理",
    ]
    
    async def execute(self, user_message: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """执行兜底响应"""
        try:
            # 尝试让模型生成友好的兜底回答
            messages = [
                {"role": "system", "content": "你是一个智能客服助手。当无法回答用户问题时，请礼貌地说明，并提供有用的建议。"},
                {"role": "user", "content": user_message}
            ]
            
            response = self.model.invoke(messages)
            
            return {
                "response": response.content,
                "tool_calls": None
            }
            
        except Exception:
            # 如果模型调用也失败，使用预设模板
            import random
            return {
                "response": random.choice(self.FALLBACK_RESPONSES),
                "tool_calls": None
            }
    
    async def execute_stream(self, user_message: str, session_id: str, user_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """流式执行兜底响应"""
        try:
            messages = [
                {"role": "system", "content": "你是一个智能客服助手。当无法回答用户问题时，请礼貌地说明。"},
                {"role": "user", "content": user_message}
            ]
            
            for chunk in self.model.stream(messages):
                if chunk.content:
                    yield {"type": "content", "data": chunk.content}
                    
        except Exception:
            import random
            response = random.choice(self.FALLBACK_RESPONSES)
            yield {"type": "content", "data": response}
