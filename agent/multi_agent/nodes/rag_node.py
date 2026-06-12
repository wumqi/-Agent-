"""
RAG 知识库检索节点
"""
from typing import Dict, Any, AsyncGenerator
from agent.multi_agent.nodes.base_node import BaseNode
from rag.rag_service import RagSummarizeService
from utils.logger_handler import logger


class RagNode(BaseNode):
    """RAG 知识库检索节点"""
    
    def __init__(self):
        self.rag_service = RagSummarizeService()
        logger.info("RAG 节点初始化完成")
    
    async def execute(self, user_message: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """执行 RAG 检索并生成回答"""
        try:
            # 检索相关知识
            result = self.rag_service.query(user_message)
            
            return {
                "response": result.get("answer", ""),
                "tool_calls": [{
                    "tool": "knowledge_retrieval",
                    "input": user_message,
                    "output": result.get("sources", [])
                }],
                "sources": result.get("sources", [])
            }
        except Exception as e:
            logger.error(f"RAG 节点执行失败: {e}")
            return {
                "response": "抱歉，知识库检索出现问题，请稍后重试。",
                "tool_calls": None
            }
    
    async def execute_stream(self, user_message: str, session_id: str, user_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """流式执行 RAG 检索"""
        try:
            # 先发送检索中状态
            yield {"type": "status", "data": "正在检索知识库..."}
            
            # 执行检索
            result = self.rag_service.query(user_message)
            answer = result.get("answer", "")
            
            # 流式输出回答
            for i in range(0, len(answer), 10):
                chunk = answer[i:i+10]
                yield {"type": "content", "data": chunk}
            
            # 发送工具调用信息
            yield {
                "type": "tool",
                "data": {
                    "tool": "knowledge_retrieval",
                    "sources": result.get("sources", [])
                }
            }
            
        except Exception as e:
            logger.error(f"RAG 节点流式执行失败: {e}")
            yield {"type": "error", "data": str(e)}
