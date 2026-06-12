"""
MCP Server 实现
管理工具注册、参数校验、请求处理
"""
from typing import Dict, List, Any, Callable
from agent.mcp.protocol import (
    MCPRequest, MCPResponse, MCPErrorCode,
    MCPToolDefinition, MCPToolSchema,
    create_mcp_response, create_mcp_error, validate_mcp_params
)
from utils.logger_handler import logger


class MCPServer:
    """
    MCP Server
    
    职责：
    1. 工具注册与管理
    2. 请求路由与分发
    3. 参数校验
    4. 结果封装
    """
    
    def __init__(self):
        self._tools: Dict[str, MCPToolDefinition] = {}
        logger.info("MCP Server 初始化完成")
    
    def register_tool(
        self,
        name: str,
        description: str,
        handler: Callable,
        parameters: Dict[str, Any] = None,
        required: List[str] = None
    ) -> None:
        """
        注册工具
        
        Args:
            name: 工具名称
            description: 工具描述
            handler: 工具处理函数
            parameters: 参数Schema
            required: 必填参数列表
        """
        schema = MCPToolSchema(
            name=name,
            description=description,
            parameters=parameters or {"type": "object", "properties": {}},
            required=required or []
        )
        
        tool_def = MCPToolDefinition(
            name=name,
            description=description,
            schema=schema,
            handler=handler
        )
        
        self._tools[name] = tool_def
        logger.info(f"MCP 工具注册成功: {name}")
    
    def unregister_tool(self, name: str) -> bool:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"MCP 工具注销成功: {name}")
            return True
        return False
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具列表"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "schema": tool.schema.dict()
            }
            for tool in self._tools.values()
        ]
    
    def handle_request(self, request: MCPRequest) -> MCPResponse:
        """
        处理 MCP 请求
        
        完整流程：
        1. 校验请求格式
        2. 查找工具
        3. 校验参数
        4. 执行工具
        5. 封装响应
        """
        try:
            # 1. 校验请求
            if not request.method:
                return create_mcp_error(
                    MCPErrorCode.INVALID_REQUEST,
                    "缺少 method 字段",
                    request_id=request.id
                )
            
            # 2. 查找工具
            tool = self._tools.get(request.method)
            if not tool:
                return create_mcp_error(
                    MCPErrorCode.METHOD_NOT_FOUND,
                    f"工具不存在: {request.method}",
                    request_id=request.id
                )
            
            # 3. 校验参数
            error = validate_mcp_params(tool.schema, request.params)
            if error:
                return create_mcp_error(
                    MCPErrorCode.INVALID_PARAMS,
                    error,
                    request_id=request.id
                )
            
            # 4. 执行工具
            logger.info(f"MCP 执行工具: {request.method}, 参数: {request.params}")
            result = tool.handler(**request.params)
            
            # 5. 封装响应
            return create_mcp_response(result=result, request_id=request.id)
            
        except Exception as e:
            logger.error(f"MCP 工具执行失败: {request.method}, 错误: {e}")
            return create_mcp_error(
                MCPErrorCode.TOOL_EXECUTION_ERROR,
                str(e),
                request_id=request.id
            )
    
    def handle_raw_request(self, raw_request: Dict[str, Any]) -> Dict[str, Any]:
        """处理原始字典请求"""
        try:
            request = MCPRequest(**raw_request)
            response = self.handle_request(request)
            return response.dict()
        except Exception as e:
            logger.error(f"MCP 请求解析失败: {e}")
            return create_mcp_error(
                MCPErrorCode.INVALID_REQUEST,
                f"请求格式错误: {str(e)}"
            ).dict()


# 全局 MCP Server 实例
mcp_server = MCPServer()


def register_mcp_tool(
    name: str,
    description: str,
    parameters: Dict[str, Any] = None,
    required: List[str] = None
):
    """
    MCP 工具注册装饰器
    
    使用示例：
        @register_mcp_tool(
            name="get_weather",
            description="获取指定城市的天气",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"}
                }
            },
            required=["city"]
        )
        def get_weather(city: str) -> str:
            return f"{city}的天气是晴天"
    """
    def decorator(func: Callable):
        mcp_server.register_tool(
            name=name,
            description=description,
            handler=func,
            parameters=parameters,
            required=required
        )
        return func
    return decorator
