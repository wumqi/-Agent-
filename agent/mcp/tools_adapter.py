"""
MCP 工具适配器
将现有工具封装为 MCP 协议
"""
from agent.mcp.server import register_mcp_tool
from agent.tools.agent_tools import get_all_tools
from utils.logger_handler import logger


def adapt_all_tools_to_mcp():
    """
    将所有现有工具适配为 MCP 协议
    
    自动扫描现有工具并注册到 MCP Server
    """
    tools = get_all_tools()
    
    for tool in tools:
        try:
            # 提取工具信息
            tool_name = tool.name
            tool_description = tool.description
            
            # 构建参数 Schema
            parameters = {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "用户查询内容"
                    }
                },
                "required": ["query"]
            }
            
            # 创建适配函数
            def create_handler(t):
                def handler(query: str):
                    return t.run(query)
                return handler
            
            # 注册到 MCP
            register_mcp_tool(
                name=tool_name,
                description=tool_description,
                parameters=parameters,
                required=["query"]
            )(create_handler(tool))
            
            logger.info(f"工具已适配为 MCP: {tool_name}")
            
        except Exception as e:
            logger.error(f"工具 MCP 适配失败: {tool.name}, 错误: {e}")
    
    logger.info(f"MCP 工具适配完成，共 {len(tools)} 个工具")


def adapt_single_tool_to_mcp(tool, custom_name: str = None, custom_description: str = None):
    """
    将单个工具适配为 MCP 协议
    
    Args:
        tool: 原始工具
        custom_name: 自定义名称
        custom_description: 自定义描述
    """
    name = custom_name or tool.name
    description = custom_description or tool.description
    
    @register_mcp_tool(
        name=name,
        description=description,
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "用户查询内容"
                }
            },
            "required": ["query"]
        }
    )
    def adapted_handler(query: str):
        return tool.run(query)
    
    logger.info(f"单工具已适配为 MCP: {name}")
    return adapted_handler


# 启动时自动适配
if __name__ == "__main__":
    adapt_all_tools_to_mcp()
