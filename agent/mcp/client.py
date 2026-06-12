"""
MCP Client 实现
用于调用 MCP Server 上的工具
"""
from typing import Dict, Any, Optional
from agent.mcp.protocol import MCPRequest, MCPResponse, MCPErrorCode
from agent.mcp.server import mcp_server
from utils.logger_handler import logger


class MCPClient:
    """
    MCP Client
    
    职责：
    1. 构建标准化请求
    2. 发送请求到 MCP Server
    3. 处理响应结果
    4. 错误处理与重试
    """
    
    def __init__(self, server=None):
        self.server = server or mcp_server
        logger.info("MCP Client 初始化完成")
    
    def call_tool(
        self,
        tool_name: str,
        params: Dict[str, Any] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            params: 参数
            request_id: 请求ID
            
        Returns:
            工具执行结果
        """
        # 构建请求
        request = MCPRequest(
            method=tool_name,
            params=params or {},
            id=request_id
        )
        
        # 发送请求
        logger.info(f"MCP Client 调用工具: {tool_name}")
        response = self.server.handle_request(request)
        
        # 处理响应
        if response.error:
            logger.error(f"MCP 工具调用失败: {response.error}")
            raise MCPClientError(
                code=response.error.get("code", "UNKNOWN"),
                message=response.error.get("message", "未知错误"),
                data=response.error.get("data")
            )
        
        return response.result
    
    def call_tool_safe(
        self,
        tool_name: str,
        params: Dict[str, Any] = None,
        default_value: Any = None
    ) -> Any:
        """
        安全调用工具（失败时返回默认值）
        """
        try:
            return self.call_tool(tool_name, params)
        except MCPClientError as e:
            logger.warning(f"MCP 工具调用失败，返回默认值: {tool_name}, 错误: {e}")
            return default_value
    
    def list_available_tools(self) -> list:
        """获取可用工具列表"""
        return self.server.list_tools()


class MCPClientError(Exception):
    """MCP Client 错误"""
    
    def __init__(self, code: str, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"[{code}] {message}")


# 全局 MCP Client 实例
mcp_client = MCPClient()
