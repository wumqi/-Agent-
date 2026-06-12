"""
自定义 Supervisor 多智能体架构
基于意图识别和路由分发的多智能体调度器
"""
import json
import logging
from typing import Dict, List, Any, AsyncGenerator
from enum import Enum

from model.factory import chat_model
from agent.multi_agent.nodes.rag_node import RagNode
from agent.multi_agent.nodes.chat_node import ChatNode
from agent.multi_agent.nodes.tool_node import ToolNode
from agent.multi_agent.nodes.fallback_node import FallbackNode
from agent.reflection_agent import ReflectionAgent
from utils.logger_handler import logger


class IntentType(Enum):
    """意图类型"""
    KNOWLEDGE_QUERY = "knowledge_query"      # 知识库查询
    TOOL_CALL = "tool_call"                  # 工具调用
    CHAT = "chat"                            # 闲聊问答
    FALLBACK = "fallback"                    # 异常兜底


class SupervisorAgent:
    """
    Supervisor 主控调度器
    
    核心职责：
    1. 意图识别：分析用户输入，判断属于哪类意图
    2. 路由分发：将请求分发到对应的分支节点处理
    3. 结果整合：汇总各节点结果，生成最终回答
    4. 反思评估：对回答进行质量评估和错误纠正
    """
    
    def __init__(self):
        # 初始化各分支节点
        self.rag_node = RagNode()
        self.chat_node = ChatNode()
        self.tool_node = ToolNode()
        self.fallback_node = FallbackNode()
        
        # 初始化反思模块
        self.reflection_agent = ReflectionAgent(llm=chat_model)
        
        # 意图路由映射
        self.intent_nodes = {
            IntentType.KNOWLEDGE_QUERY: self.rag_node,
            IntentType.TOOL_CALL: self.tool_node,
            IntentType.CHAT: self.chat_node,
            IntentType.FALLBACK: self.fallback_node,
        }
        
        logger.info("Supervisor 多智能体架构初始化完成")
    
    def _classify_intent(self, user_message: str) -> IntentType:
        """
        意图识别
        
        基于关键词和规则判断用户意图类型：
        - 知识库查询：包含"制度""流程""政策""规定"等专业词汇
        - 工具调用：包含"天气""时间""计算"等工具类词汇
        - 闲聊：其他日常对话
        """
        message = user_message.lower()
        
        # 知识库查询关键词
        knowledge_keywords = [
            "制度", "流程", "政策", "规定", "指南", "手册",
            "报销", "请假", "考勤", "入职", "离职",
            "怎么", "如何", "什么", "哪些", "介绍"
        ]
        
        # 工具调用关键词
        tool_keywords = [
            "天气", "温度", "时间", "日期", "计算",
            "查询", "搜索", "定位", "天气怎么样"
        ]
        
        # 判断意图
        knowledge_score = sum(1 for kw in knowledge_keywords if kw in message)
        tool_score = sum(1 for kw in tool_keywords if kw in message)
        
        if knowledge_score >= 1:
            return IntentType.KNOWLEDGE_QUERY
        elif tool_score >= 1:
            return IntentType.TOOL_CALL
        else:
            return IntentType.CHAT
    
    async def process(self, user_message: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        同步处理用户请求
        
        Args:
            user_message: 用户输入
            session_id: 会话ID
            user_id: 用户ID
            
        Returns:
            包含响应、工具调用记录、反思结果的字典
        """
        try:
            # 1. 意图识别
            intent = self._classify_intent(user_message)
            logger.info(f"意图识别结果: {intent.value}, 用户: {user_id}, 会话: {session_id}")
            
            # 2. 路由分发到对应节点
            node = self.intent_nodes.get(intent, self.fallback_node)
            result = await node.execute(user_message, session_id, user_id)
            
            # 3. 自我反思评估
            reflection_result = None
            if self.reflection_agent:
                reflection_result = self.reflection_agent.reflect(
                    user_query=user_message,
                    agent_response=result.get("response", ""),
                    tool_calls=result.get("tool_calls", []),
                    context={"session_id": session_id, "intent": intent.value}
                )
                
                # 如果需要纠正，使用纠正后的回答
                if reflection_result.get("needs_correction"):
                    result["response"] = reflection_result.get("corrected_response", result["response"])
            
            return {
                "response": result.get("response", ""),
                "tool_calls": result.get("tool_calls"),
                "reflection": reflection_result,
                "intent": intent.value,
            }
            
        except Exception as e:
            logger.error(f"Supervisor 处理失败: {e}")
            # 异常兜底
            fallback_result = await self.fallback_node.execute(user_message, session_id, user_id)
            return {
                "response": fallback_result.get("response", "抱歉，处理您的请求时出现问题，请稍后重试。"),
                "tool_calls": None,
                "reflection": None,
                "intent": IntentType.FALLBACK.value,
            }
    
    async def process_stream(self, user_message: str, session_id: str, user_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式处理用户请求（SSE）
        
        生成数据块格式：
        - type: content - 文本内容
        - type: tool - 工具调用信息
        - type: reflection - 反思结果
        - type: done - 结束标记
        """
        try:
            # 1. 意图识别
            intent = self._classify_intent(user_message)
            logger.info(f"流式处理 - 意图: {intent.value}, 会话: {session_id}")
            
            # 2. 路由分发
            node = self.intent_nodes.get(intent, self.fallback_node)
            
            # 3. 流式执行
            async for chunk in node.execute_stream(user_message, session_id, user_id):
                yield {
                    "type": chunk.get("type", "content"),
                    "data": chunk.get("data", ""),
                    "session_id": session_id,
                }
            
        except Exception as e:
            logger.error(f"流式处理失败: {e}")
            yield {
                "type": "error",
                "data": str(e),
                "session_id": session_id,
            }
