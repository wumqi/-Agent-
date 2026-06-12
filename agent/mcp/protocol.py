"""
MCP (Model Context Protocol) 协议数据模型
标准化工具调用协议
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Literal
from enum import Enum


class MCPErrorCode(Enum):
    """MCP 错误码"""
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_PARAMS = "INVALID_PARAMS"
    METHOD_NOT_FOUND = "METHOD_NOT_FOUND"
    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    TIMEOUT = "TIMEOUT"


class MCPRequest(BaseModel):
    """MCP 请求模型"""
    jsonrpc: Literal["2.0"] = Field(default="2.0", description="JSON-RPC 版本")
    method: str = Field(..., description="方法名（工具名）")
    params: Dict[str, Any] = Field(default={}, description="参数")
    id: Optional[str] = Field(default=None, description="请求ID")


class MCPResponse(BaseModel):
    """MCP 响应模型"""
    jsonrpc: Literal["2.0"] = Field(default="2.0")
    result: Optional[Any] = Field(default=None, description="执行结果")
    error: Optional[Dict[str, Any]] = Field(default=None, description="错误信息")
    id: Optional[str] = Field(default=None, description="请求ID")


class MCPError(BaseModel):
    """MCP 错误模型"""
    code: str = Field(..., description="错误码")
    message: str = Field(..., description="错误消息")
    data: Optional[Any] = Field(default=None, description="附加数据")


class MCPToolSchema(BaseModel):
    """MCP 工具 Schema"""
    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    parameters: Dict[str, Any] = Field(default={}, description="参数Schema（JSON Schema格式）")
    required: List[str] = Field(default=[], description="必填参数列表")


class MCPToolDefinition(BaseModel):
    """MCP 工具定义"""
    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    schema: MCPToolSchema = Field(..., description="工具Schema")
    handler: Any = Field(default=None, description="工具处理函数", exclude=True)


def create_mcp_request(method: str, params: Dict[str, Any] = None, request_id: str = None) -> MCPRequest:
    """创建 MCP 请求"""
    return MCPRequest(
        method=method,
        params=params or {},
        id=request_id
    )


def create_mcp_response(result: Any = None, request_id: str = None) -> MCPResponse:
    """创建 MCP 成功响应"""
    return MCPResponse(
        result=result,
        id=request_id
    )


def create_mcp_error(code: MCPErrorCode, message: str, data: Any = None, request_id: str = None) -> MCPResponse:
    """创建 MCP 错误响应"""
    return MCPResponse(
        error={
            "code": code.value,
            "message": message,
            "data": data
        },
        id=request_id
    )


def validate_mcp_params(schema: MCPToolSchema, params: Dict[str, Any]) -> Optional[str]:
    """
    校验 MCP 参数
    
    Returns:
        错误信息，如果校验通过返回 None
    """
    # 检查必填参数
    for required_param in schema.required:
        if required_param not in params:
            return f"缺少必填参数: {required_param}"
    
    # 检查参数类型（简化版，实际可使用 jsonschema 库）
    properties = schema.parameters.get("properties", {})
    for param_name, param_value in params.items():
        if param_name in properties:
            expected_type = properties[param_name].get("type")
            if expected_type:
                type_map = {
                    "string": str,
                    "integer": int,
                    "number": (int, float),
                    "boolean": bool,
                    "array": list,
                    "object": dict,
                }
                expected = type_map.get(expected_type)
                if expected and not isinstance(param_value, expected):
                    return f"参数 {param_name} 类型错误，期望 {expected_type}"
    
    return None
