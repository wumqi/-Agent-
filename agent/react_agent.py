import warnings
from typing import List, Dict
import re

# 抑制LangChain弃用警告
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

from langchain.agents.initialize import initialize_agent
from langchain.agents.agent_types import AgentType

from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools.agent_tools import get_all_tools
from agent.reflection_agent import ReflectionAgent
from agent.error_correction import ErrorCorrector
from agent.tools.reflection_tools import ReflectionTools
from utils.logger_handler import logger


class ReactAgent:
    def __init__(
            self,
            max_history_length: int = 10,
            max_summary_length: int = 500,
            enable_reflection: bool = True
    ):
        """
        ReAct Agent 初始化
        
        Args:
            max_history_length: 最大历史长度
            max_summary_length: 最大摘要长度
            enable_reflection: 是否启用自我反思
        """

        # 工具列表
        self.tools = get_all_tools()

        # 是否启用自我反思
        self.enable_reflection = enable_reflection
        
        # 初始化自我反思模块
        if self.enable_reflection:
            self.reflection_agent = ReflectionAgent(llm=chat_model)
            self.error_corrector = ErrorCorrector()
            self.reflection_tools = ReflectionTools(
                reflection_agent=self.reflection_agent,
                error_corrector=self.error_corrector
            )
            # 添加反思工具到工具列表
            self.tools.extend(self.reflection_tools.get_tools())
        else:
            self.reflection_agent = None
            self.error_corrector = None
            self.reflection_tools = None

        # 系统提示词
        self.system_prompt = load_system_prompts()

        # 初始化 Agent（兼容 LangChain 0.3.x）
        self.agent = initialize_agent(
            tools=self.tools,
            llm=chat_model,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
            handle_parsing_errors=True,
        )

        # 对话历史
        self.conversation_history: List[Dict[str, str]] = []

        # 历史长度限制
        self.max_history_length = max_history_length

        # 摘要长度限制
        self.max_summary_length = max_summary_length

        # 对话摘要
        self.conversation_summary = ""

        # 上次摘要时间
        self.last_summary_time = 0

    def _is_tool_message(self, content: str) -> bool:
        """
        判断是否为工具调用中间消息
        """

        tool_patterns = [
            r'^Action:\s*\w+',
            r'^Tool:',
            r'^调用工具:',
            r'^思考:',
            r'^\[工具返回\]',
            r'^\[结束对话\]',
            r'^Agent Info:',
            r'^Observation:',
            r'^FunctionCall:',
            r'^\{.*function.*\}',
            r'^\s*function\s+\w+',
            r'^\s*def\s+\w+',
            r'^工具调用:',
            r'^使用工具:',
            r'^开始调用:',
            r'^返回结果:',
            r'^执行结果:',
        ]

        for pattern in tool_patterns:
            if re.match(pattern, content.strip(), re.IGNORECASE):
                return True

        return False

    def _clean_tool_messages(self, content: str) -> str:
        """
        清理工具调用相关消息和函数名，并生成友好的输出格式
        """
        
        # 定义工具函数名到友好名称的映射
        tool_name_map = {
            'get_document_content': '文档内容获取',
            'search_knowledge_base': '知识库检索', 
            'summarize_document': '文档摘要',
            'qa_search': '问答检索',
            'get_session_list': '会话列表',
            'create_session': '创建会话',
            'delete_session': '删除会话',
            'update_session_title': '更新会话标题',
            'get_messages': '获取消息',
            'add_message': '添加消息',
            'finish_task': '完成任务',
            'end_conversation': '结束对话',
            '总结任务': '总结任务',
            '结束对话': '结束对话',
            'rag_search': '信息检索',
            'get_weather': '天气查询',
            'get_user_location': '位置获取',
            'get_user_id': '用户ID获取',
            'get_current_month': '当前月份获取',
            'fetch_external_data': '外部数据获取',
            'fill_context_for_report': '报告上下文填充',
            'query_ticket': '工单查询',
            'get_system_stats': '系统统计',
        }
        
        # 移除JSON格式的函数调用
        content = re.sub(r'\{\s*["\']name["\']\s*:\s*["\'][^"\']+["\'][^}]*\}', '', content)
        content = re.sub(r'\{\s*["\']tool["\']\s*:\s*["\'][^"\']+["\'][^}]*\}', '', content)
        content = re.sub(r'\{\s*["\']function["\']\s*:\s*["\'][^"\']+["\'][^}]*\}', '', content)
        
        # 移除函数定义
        content = re.sub(r'\bfunction\s+\w+\s*\([^)]*\)\s*\{', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\bdef\s+\w+\s*\([^)]*\)\s*:', '', content, flags=re.IGNORECASE)
        
        # 将函数调用替换为友好名称（带括号的调用）
        for func_name, friendly_name in tool_name_map.items():
            content = re.sub(r'\b' + re.escape(func_name) + r'\s*\([^)]*\)', friendly_name, content)
        
        # 将单独的函数名替换为友好名称（不带括号）
        for func_name, friendly_name in tool_name_map.items():
            # 只替换独立出现的函数名，不替换已经是友好名称一部分的情况
            content = re.sub(r'(?<!\w)' + re.escape(func_name) + r'(?!\w)', friendly_name, content)
        
        # 移除工具调用标记和标签
        content = re.sub(r'<function[^>]*>', '', content)
        content = re.sub(r'</function>', '', content)
        content = re.sub(r'<tool[^>]*>', '', content)
        content = re.sub(r'</tool>', '', content)
        
        # 移除中文工具调用描述
        content = re.sub(r'调用\s*[\u4e00-\u9fa5]*工具\s*[:：]\s*\w+', '', content)
        content = re.sub(r'使用\s*[\u4e00-\u9fa5]*工具\s*[:：]\s*\w+', '', content)
        content = re.sub(r'执行\s*[\u4e00-\u9fa5]*函数\s*[:：]\s*\w+', '', content)
        content = re.sub(r'工具\s*[:：]\s*\w+', '', content)
        content = re.sub(r'函数\s*[:：]\s*\w+', '', content)
        
        # 移除思考过程标记
        content = re.sub(r'^思考\s*[:：]\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'^Thought\s*[:：]\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'^Action\s*[:：]\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'^Observation\s*[:：]\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'^工具返回\s*[:：]\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'^返回结果\s*[:：]\s*', '', content, flags=re.MULTILINE)
        
        # 按行处理，移除工具消息行
        lines = content.split('\n')
        cleaned_lines = []

        for line in lines:
            if not self._is_tool_message(line):
                cleaned_lines.append(line)

        result = '\n'.join(cleaned_lines).strip()
        
        # 移除多余的空行和空格
        result = re.sub(r'\n{3,}', '\n\n', result)
        result = re.sub(r'\s{3,}', ' ', result)
        
        # 格式化输出
        result = self._format_output(result)
        
        return result

    def _format_output(self, content: str) -> str:
        """
        格式化输出内容，使其更美观易读
        """
        if not content:
            return content
        
        lines = content.split('\n')
        formatted_lines = []
        
        for line in lines:
            # 移除行首行尾空格
            line = line.strip()
            
            # 跳过空行（会在后面统一处理）
            if not line:
                continue
            
            # 格式化列表项
            line = self._format_list_item(line)
            
            # 格式化标题
            line = self._format_heading(line)
            
            # 格式化加粗/强调
            line = self._format_bold(line)
            
            # 格式化代码
            line = self._format_code(line)
            
            formatted_lines.append(line)
        
        # 重新组合并添加适当的空行
        result = '\n\n'.join(formatted_lines)
        
        # 确保列表项之间有适当的间距
        result = re.sub(r'(\n- ){2,}', r'\n- ', result)
        result = re.sub(r'(\n\d+\. ){2,}', r'\n', result)
        
        # 确保标题后有适当的空行
        result = re.sub(r'(#{1,6} .+)\n([^#\n])', r'\1\n\n\2', result)
        
        # 确保代码块前后有适当的空行
        result = re.sub(r'```(\w+)?\n', '\n```\\1\n', result)
        result = re.sub(r'\n```', '\n\n```', result)
        
        # 移除首尾多余空行
        result = result.strip()
        
        return result
    
    def _format_list_item(self, line: str) -> str:
        """格式化列表项"""
        # 统一列表项格式
        # 处理 - item 格式
        line = re.sub(r'^[\*•·→>]\s+', '- ', line)
        # 处理数字列表格式
        line = re.sub(r'^(\d+)\s*[、.．]\s+', r'\1. ', line)
        return line
    
    def _format_heading(self, line: str) -> str:
        """格式化标题"""
        # 确保标题前后有空格
        line = re.sub(r'^(#+)([^#\s])', r'\1 \2', line)
        line = re.sub(r'^(#+\s+.+?)\s+#*$', r'\1', line)
        return line
    
    def _format_bold(self, line: str) -> str:
        """格式化加粗/强调"""
        # 统一加粗格式为 **text**
        line = re.sub(r'【([^】]+)】', r'**\1**', line)
        line = re.sub(r'「([^」]+)」', r'**\1**', line)
        line = re.sub(r'『([^』]+)』', r'**\1**', line)
        line = re.sub(r'<strong>([^<]+)</strong>', r'**\1**', line)
        line = re.sub(r'<b>([^<]+)</b>', r'**\1**', line)
        return line
    
    def _format_code(self, line: str) -> str:
        """格式化代码"""
        # 处理行内代码
        line = re.sub(r'`([^`]+)`', r'`\1`', line)
        # 处理尖括号代码
        line = re.sub(r'<code>([^<]+)</code>', r'`\1`', line)
        return line

    def _truncate_history(self):
        """
        截断历史记录
        """

        if len(self.conversation_history) > self.max_history_length:
            self.conversation_history = self.conversation_history[-self.max_history_length:]

    def _summarize_history(self) -> str:
        """
        对话摘要
        """

        if len(self.conversation_history) < 3:
            return ""

        try:

            history_text = "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in self.conversation_history[:-2]
            ])

            if len(history_text) <= self.max_summary_length:
                return history_text

            summary_prompt = f"""
请将以下对话历史总结成一段简洁摘要，
不要超过{self.max_summary_length}字：

{history_text}

摘要：
"""

            if hasattr(chat_model, 'invoke'):

                summary = chat_model.invoke(summary_prompt).content

            else:

                summary = str(
                    chat_model.generate(
                        [summary_prompt]
                    ).generations[0][0].text
                )

            return summary[:self.max_summary_length]

        except Exception as e:

            logger.error(f"生成对话摘要失败: {str(e)}")

            return ""

    def _generate_reply_suggestions(self, query: str) -> List[str]:
        """
        生成智能回复建议
        """

        try:

            suggestions_prompt = f"""
基于用户问题：

"{query}"

生成3个相关后续问题。

格式：

1. xxx
2. xxx
3. xxx
"""

            if hasattr(chat_model, 'invoke'):

                result = chat_model.invoke(
                    suggestions_prompt
                ).content

            else:

                result = str(
                    chat_model.generate(
                        [suggestions_prompt]
                    ).generations[0][0].text
                )

            suggestions = []

            for line in result.split('\n'):

                match = re.match(
                    r'^\d+\.\s*(.+)$',
                    line.strip()
                )

                if match:
                    suggestions.append(match.group(1))

            return suggestions[:3]

        except Exception as e:

            logger.error(f"生成回复建议失败: {str(e)}")

            return []

    def add_message(self, role: str, content: str):
        """
        添加消息
        """

        cleaned_content = self._clean_tool_messages(content)

        if cleaned_content:

            self.conversation_history.append({
                "role": role,
                "content": cleaned_content
            })

            self._truncate_history()

    def get_full_messages(self) -> List[Dict[str, str]]:
        """
        获取完整消息
        """

        messages = []

        if self.conversation_summary:

            messages.append({
                "role": "system",
                "content": f"对话历史摘要：{self.conversation_summary}\n\n当前对话："
            })

        messages.extend(self.conversation_history)

        return messages

    def execute_stream(self, query: str):
        """
        执行对话（兼容 LangChain 0.3.x）
        包含自我反思和错误纠正机制
        """

        self.add_message("user", query)

        try:

            # 拼接历史消息
            history_context = ""

            if self.conversation_summary:

                history_context += f"""
对话摘要：
{self.conversation_summary}

"""

            for msg in self.conversation_history:

                history_context += f"""
{msg['role']}:
{msg['content']}

"""

            final_query = f"""
{self.system_prompt}

{history_context}

用户问题：
{query}
"""

            # Agent 执行
            response = self.agent.run(final_query)

            # 清理工具消息
            cleaned_response = self._clean_tool_messages(response)

            # 自我反思评估
            if self.enable_reflection and self.reflection_agent:
                try:
                    reflection_result = self.reflection_agent.reflect(
                        user_query=query,
                        agent_response=cleaned_response,
                        tool_calls=[]  # 可以传入实际工具调用记录
                    )
                    
                    # 如果需要纠正且有纠正后的响应，使用纠正版本
                    if reflection_result.get("needs_correction"):
                        if reflection_result.get("corrected_response"):
                            cleaned_response = reflection_result["corrected_response"]
                            logger.info(f"使用纠正后的响应: 原始质量={reflection_result['quality_score']:.2f}")
                        elif reflection_result.get("confidence", 1.0) < 0.5:
                            # 置信度过低，添加提示
                            logger.warning(f"响应置信度过低: {reflection_result['confidence']:.2f}")
                except Exception as e:
                    logger.error(f"自我反思评估失败: {e}")

            if cleaned_response:

                self.add_message(
                    "assistant",
                    cleaned_response
                )

            yield cleaned_response

        except Exception as e:

            logger.error(f"Agent执行失败: {str(e)}")

            yield f"执行失败: {str(e)}"

        finally:

            self.conversation_summary = self._summarize_history()

    def get_conversation_summary(self) -> str:
        """
        获取对话摘要
        """

        return self.conversation_summary

    def generate_suggestions(self, query: str) -> List[str]:
        """
        生成回复建议
        """

        return self._generate_reply_suggestions(query)

    def clear_history(self):
        """
        清空对话历史（不清空反思历史，保留统计数据）
        """

        self.conversation_history = []
        self.conversation_summary = ""
        self.last_summary_time = 0
    
    def clear_reflection_history(self):
        """
        清空反思历史（仅在用户明确要求时调用）
        """
        if self.reflection_agent:
            self.reflection_agent.clear_history()
            logger.info("反思历史已由用户手动清空")
    
    def get_history_length(self) -> int:
        """
        获取历史长度
        """

        return len(self.conversation_history)
    
    def get_reflection_stats(self) -> Dict:
        """
        获取反思统计信息
        """
        if self.reflection_agent:
            return self.reflection_agent.get_reflection_stats()
        return {}
    
    def get_error_stats(self) -> Dict:
        """
        获取错误统计信息
        """
        if self.error_corrector:
            return self.error_corrector.get_error_stats()
        return {}

    def get_available_tools(self) -> List[str]:
        """
        获取工具列表
        """

        return [tool.name for tool in self.tools]


if __name__ == '__main__':

    agent = ReactAgent()

    print("可用工具:")
    print(agent.get_available_tools())

    print("\n用户：今天天气怎么样？")

    for chunk in agent.execute_stream(
            "今天天气怎么样？"
    ):
        print(chunk, end="", flush=True)

    print("\n\n对话摘要:")
    print(agent.get_conversation_summary())

    print("\n回复建议:")
    print(
        agent.generate_suggestions(
            "今天天气怎么样？"
        )
    )