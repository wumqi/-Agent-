"""
上下文管理器 - 支持增强的对话上下文理解
支持长对话历史管理和自动摘要
"""

import json
import logging
import os
import time
from typing import Optional, Dict, Any, List
from utils.redis_manager import redis_manager

logger = logging.getLogger(__name__)


class ContextManager:
    """上下文管理器"""
    
    def __init__(self):
        # 从环境变量获取配置
        self._max_history = int(os.getenv("CONTEXT_MAX_HISTORY", "50"))
        self._summarize_threshold = int(os.getenv("CONTEXT_SUMMARIZE_THRESHOLD", "10"))
        self._compress_enabled = os.getenv("CONTEXT_COMPRESS_ENABLED", "true").lower() == "true"
        self._compress_tokens = int(os.getenv("CONTEXT_COMPRESS_TOKENS", "4096"))
    
    def get_context(self, session_id: str) -> Dict[str, Any]:
        """获取对话上下文"""
        # 尝试从Redis获取
        context = redis_manager.get_context(session_id)
        if context:
            return context
        
        # 如果Redis不可用或缓存不存在，返回默认上下文
        return {
            "history": [],
            "summary": "",
            "topics": [],
            "entities": {},
            "turn_count": 0
        }
    
    def update_context(self, session_id: str, user_message: str, assistant_response: str) -> Dict[str, Any]:
        """更新对话上下文"""
        context = self.get_context(session_id)
        
        # 添加新消息到历史
        context["history"].append({
            "role": "user",
            "content": user_message,
            "timestamp": time.time()
        })
        context["history"].append({
            "role": "assistant",
            "content": assistant_response,
            "timestamp": time.time()
        })
        
        # 更新对话轮数
        context["turn_count"] = len(context["history"]) // 2
        
        # 检查是否需要总结
        if self._compress_enabled and context["turn_count"] >= self._summarize_threshold:
            context = self._compress_context(session_id, context)
        
        # 限制历史长度
        if len(context["history"]) > self._max_history * 2:
            context["history"] = context["history"][-self._max_history * 2:]
        
        # 保存到Redis
        redis_manager.set_context(session_id, context)
        
        return context
    
    def _compress_context(self, session_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """压缩上下文 - 生成摘要并保留最近的消息"""
        try:
            # 生成摘要（模拟，实际应调用LLM）
            new_summary = self._generate_summary(context)
            
            # 如果已有摘要，合并新摘要
            if context.get("summary"):
                context["summary"] = f"{context['summary']}\n\n---\n\n{new_summary}"
            else:
                context["summary"] = new_summary
            
            # 保留最近的消息（保留阈值的一半）
            keep_count = max(self._summarize_threshold // 2, 3) * 2
            context["history"] = context["history"][-keep_count:]
            
            # 保存摘要到Redis
            redis_manager.set_summary(session_id, context["summary"])
            
            logger.info(f"会话 {session_id} 上下文已压缩，当前摘要长度: {len(context['summary'])}")
            
        except Exception as e:
            logger.error(f"压缩上下文失败: {e}")
        
        return context
    
    def _generate_summary(self, context: Dict[str, Any]) -> str:
        """生成对话摘要（模拟实现）
        
        实际实现应调用LLM来生成更准确的摘要
        """
        history = context["history"]
        
        # 获取对话主题
        topics = []
        for msg in history[-10:]:  # 只看最近的10条消息
            content = msg["content"]
            # 简单提取关键词作为主题（实际应使用NLP）
            if len(content) > 100:
                topics.append(content[:50] + "...")
            else:
                topics.append(content)
        
        # 生成摘要文本
        summary_parts = []
        
        if context.get("summary"):
            summary_parts.append("【之前对话摘要】")
            summary_parts.append(context["summary"][:200] if len(context["summary"]) > 200 else context["summary"])
        
        summary_parts.append("\n【最新对话】")
        for i, msg in enumerate(history[-4:], 1):  # 最近4条消息
            role = "用户" if msg["role"] == "user" else "助手"
            content = msg["content"][:80] if len(msg["content"]) > 80 else msg["content"]
            summary_parts.append(f"{role}: {content}")
        
        return "\n".join(summary_parts)
    
    def get_conversation_history(self, session_id: str, limit: int = 20) -> List[Dict]:
        """获取对话历史"""
        context = self.get_context(session_id)
        history = context.get("history", [])
        
        # 按时间排序（应该已经是按时间排序的）
        history.sort(key=lambda x: x.get("timestamp", 0))
        
        # 返回最近的消息
        return history[-limit:]
    
    def get_context_for_llm(self, session_id: str) -> List[Dict]:
        """获取用于LLM的上下文格式"""
        context = self.get_context(session_id)
        history = context.get("history", [])
        
        # 如果有摘要，将摘要作为system消息的一部分
        messages = []
        
        if context.get("summary"):
            summary_msg = {
                "role": "system",
                "content": f"对话摘要（用于理解上下文）：\n{context['summary']}"
            }
            messages.append(summary_msg)
        
        # 添加历史消息（转换为LLM格式）
        for msg in history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        return messages
    
    def get_summary(self, session_id: str) -> str:
        """获取对话摘要"""
        # 先尝试从缓存获取
        summary = redis_manager.get_summary(session_id)
        if summary:
            return summary
        
        # 从上下文获取
        context = self.get_context(session_id)
        return context.get("summary", "")
    
    def clear_context(self, session_id: str) -> bool:
        """清除对话上下文"""
        return redis_manager.delete_context(session_id)
    
    def analyze_topics(self, session_id: str) -> List[str]:
        """分析对话主题（简单实现）"""
        context = self.get_context(session_id)
        history = context.get("history", [])
        
        topics = []
        for msg in history:
            content = msg["content"]
            # 简单提取主题（实际应使用NLP）
            if len(content) > 0:
                # 取前几个词作为主题标记
                words = content.split()[:3]
                topic = " ".join(words)
                if topic not in topics:
                    topics.append(topic[:30])
        
        return topics[:5]


# 全局实例
context_manager = ContextManager()

if __name__ == '__main__':
    # 测试上下文管理器
    test_session_id = "test_context_session"
    
    # 模拟多轮对话
    messages = [
        ("用户询问如何使用系统", "好的，我来帮您介绍..."),
        ("介绍一下功能", "本系统支持..."),
        ("如何上传文档", "在侧边栏点击上传按钮..."),
        ("能搜索吗", "是的，支持全文搜索..."),
        ("还有其他功能吗", "还支持会话管理..."),
    ]
    
    for user_msg, assistant_msg in messages:
        context = context_manager.update_context(test_session_id, user_msg, assistant_msg)
        print(f"对话轮数: {context['turn_count']}")
        print(f"历史消息数: {len(context['history'])}")
    
    # 获取摘要
    summary = context_manager.get_summary(test_session_id)
    print(f"\n对话摘要:\n{summary}")
    
    # 获取LLM格式的上下文
    llm_context = context_manager.get_context_for_llm(test_session_id)
    print(f"\nLLM上下文格式: {len(llm_context)} 条消息")
    
    # 分析主题
    topics = context_manager.analyze_topics(test_session_id)
    print(f"\n分析主题: {topics}")
    
    # 清理测试数据
    context_manager.clear_context(test_session_id)
    print("\n测试完成")
