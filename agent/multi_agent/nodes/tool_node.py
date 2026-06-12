"""
工具调用节点
"""
from typing import Dict, Any, AsyncGenerator
from agent.multi_agent.nodes.base_node import BaseNode
from agent.tools.agent_tools import get_all_tools
from model.factory import chat_model
from utils.logger_handler import logger


class ToolNode(BaseNode):
    """工具调用节点 - 调用外部工具完成特定任务"""
    
    def __init__(self):
        self.tools = get_all_tools()
        self.model = chat_model
        logger.info(f"工具节点初始化完成，共 {len(self.tools)} 个工具")
    
    def _select_tool(self, user_message: str):
        """根据用户消息选择合适的工具"""
        message = user_message.lower()
        
        # 工具选择逻辑
        if "天气" in message or "温度" in message:
            for tool in self.tools:
                if "weather" in tool.name.lower():
                    return tool
        
        elif "位置" in message or "城市" in message:
            for tool in self.tools:
                if "location" in tool.name.lower():
                    return tool
        
        elif "用户" in message or "id" in message:
            for tool in self.tools:
                if "user" in tool.name.lower():
                    return tool
        
        return None
    
    async def execute(self, user_message: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """执行工具调用"""
        try:
            # 选择工具
            tool = self._select_tool(user_message)
            
            if not tool:
                # 没有匹配的工具，降级为闲聊
                logger.warning(f"未找到匹配工具，降级处理: {user_message}")
                messages = [
                    {"role": "system", "content": "你是一个智能客服助手。"},
                    {"role": "user", "content": user_message}
                ]
                response = self.model.invoke(messages)
                return {
                    "response": response.content,
                    "tool_calls": None
                }
            
            # 执行工具
            logger.info(f"执行工具: {tool.name}")
            tool_result = tool.run(user_message)
            
            # 让大模型基于工具结果生成回答
            messages = [
                {"role": "system", "content": "你是一个智能客服助手。请基于工具返回的结果回答用户问题。"},
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": f"工具返回结果: {tool_result}"}
            ]
            response = self.model.invoke(messages)
            
            return {
                "response": response.content,
                "tool_calls": [{
                    "tool": tool.name,
                    "input": user_message,
                    "output": tool_result
                }]
            }
            
        except Exception as e:
            logger.error(f"工具节点执行失败: {e}")
            return {
                "response": "抱歉，工具调用失败，请稍后重试。",
                "tool_calls": None
            }
    
    async def execute_stream(self, user_message: str, session_id: str, user_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """流式执行工具调用"""
        try:
            yield {"type": "status", "data": "正在调用工具..."}
            
            tool = self._select_tool(user_message)
            if tool:
                tool_result = tool.run(user_message)
                yield {
                    "type": "tool",
                    "data": {
                        "tool": tool.name,
                        "result": tool_result
                    }
                }
                
                # 基于工具结果生成回答
                messages = [
                    {"role": "system", "content": "你是一个智能客服助手。"},
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": f"工具返回: {tool_result}"}
                ]
                
                for chunk in self.model.stream(messages):
                    if chunk.content:
                        yield {"type": "content", "data": chunk.content}
            else:
                messages = [
                    {"role": "system", "content": "你是一个智能客服助手。"},
                    {"role": "user", "content": user_message}
                ]
                for chunk in self.model.stream(messages):
                    if chunk.content:
                        yield {"type": "content", "data": chunk.content}
                        
        except Exception as e:
            logger.error(f"工具节点流式执行失败: {e}")
            yield {"type": "error", "data": str(e)}
