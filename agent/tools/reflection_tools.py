#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
反思工具 - Agent可以调用的自我反思工具
"""

import logging
from typing import Dict, List, Any, Optional
from langchain.tools import BaseTool, Tool
from langchain.schema import HumanMessage

logger = logging.getLogger(__name__)


class ReflectionTools:
    """反思工具类 - 提供Agent可调用的反思相关工具"""

    def __init__(self, reflection_agent=None, error_corrector=None):
        self.reflection_agent = reflection_agent
        self.error_corrector = error_corrector
        self._last_reflection_result = None

    def get_tools(self) -> List[BaseTool]:
        """获取反思工具列表"""
        return [
            Tool(
                name="evaluate_response_quality",
                description="评估响应质量工具。输入：用户问题、Agent回答、工具调用列表。输出：质量评分和改进建议。使用场景：当你不确定回答质量时，使用此工具进行评估",
                func=self._evaluate_response_quality_wrapper
            ),
            Tool(
                name="check_answer_confidence",
                description="检查答案置信度工具。输入：用户问题、当前回答。输出：置信度评估和不确定领域说明。使用场景：当你不确定自己的回答是否正确时使用",
                func=self._check_answer_confidence_wrapper
            ),
            Tool(
                name="request_human_review",
                description="请求人工审核工具。输入：问题、回答、需要审核的具体点。输出：审核请求状态。使用场景：当Agent认为需要人工介入时使用",
                func=self._request_human_review_wrapper
            ),
            Tool(
                name="correct_response",
                description="纠正回答工具。输入：原始回答、问题描述、需要纠正的内容。输出：纠正后的新回答。使用场景：当发现回答有错误或不完整时使用",
                func=self._correct_response_wrapper
            ),
            Tool(
                name="get_error_recovery_suggestion",
                description="获取错误恢复建议工具。输入：错误信息。输出：恢复建议和可采取的行动。使用场景：当遇到错误不知如何处理时使用",
                func=self._get_error_recovery_suggestion_wrapper
            )
        ]

    def _evaluate_response_quality_wrapper(self, input_str: str) -> str:
        """评估响应质量的包装函数"""
        try:
            import json
            data = json.loads(input_str) if input_str else {}
            user_query = data.get("user_query", "")
            agent_response = data.get("agent_response", "")
            tool_calls = data.get("tool_calls", [])

            if self.reflection_agent:
                result = self.reflection_agent.reflect(
                    user_query=user_query,
                    agent_response=agent_response,
                    tool_calls=tool_calls
                )
                self._last_reflection_result = result

                quality_score = result.get("quality_score", 0)
                confidence = result.get("confidence", 0)
                suggestions = result.get("suggestions", [])
                errors = result.get("errors", [])

                quality_grade = "优秀" if quality_score >= 0.9 else \
                               "良好" if quality_score >= 0.7 else \
                               "一般" if quality_score >= 0.5 else "较差"

                response = f"质量评估结果:\n"
                response += f"- 质量评分: {quality_score:.2f} ({quality_grade})\n"
                response += f"- 置信度: {confidence:.2f}\n"

                if errors:
                    response += f"- 发现问题: {len(errors)}个\n"
                    for error in errors[:3]:
                        response += f"  - [{error.get('severity', 'unknown')}] {error.get('message', '')}\n"

                if suggestions:
                    response += f"- 改进建议:\n"
                    for suggestion in suggestions:
                        response += f"  - {suggestion}\n"

                return response
            else:
                return "反思系统未初始化，无法评估响应质量"

        except Exception as e:
            logger.error(f"评估响应质量失败: {e}")
            return f"评估失败: {str(e)}"

    def _check_answer_confidence_wrapper(self, input_str: str) -> str:
        """检查答案置信度的包装函数"""
        try:
            import json
            data = json.loads(input_str) if input_str else {}
            user_query = data.get("user_query", "")
            current_answer = data.get("current_answer", "")

            confidence_factors = []
            uncertainty_indicators = []

            if len(current_answer) < 50:
                confidence_factors.append("回答较短")
                uncertainty_indicators.append("回答可能不够详细")

            uncertain_words = ["可能", "也许", "大概", "不确定", "我不确定", "我不清楚"]
            found_uncertain = [w for w in uncertain_words if w in current_answer]
            if found_uncertain:
                uncertainty_indicators.append(f"包含不确定词汇: {', '.join(found_uncertain)}")

            if "根据" in current_answer or "资料显示" in current_answer:
                confidence_factors.append("包含信息来源引用")

            base_confidence = 0.8
            if len(current_answer) < 50:
                base_confidence -= 0.1
            if uncertainty_indicators:
                base_confidence -= 0.1 * len(uncertainty_indicators)
            if confidence_factors:
                base_confidence += 0.05 * len(confidence_factors)

            final_confidence = max(0.0, min(1.0, base_confidence))

            confidence_level = "高" if final_confidence >= 0.8 else \
                              "中" if final_confidence >= 0.6 else "低"

            response = f"置信度评估:\n"
            response += f"- 置信度等级: {confidence_level} ({final_confidence:.2f})\n"

            if confidence_factors:
                response += f"- 增强信心的因素:\n"
                for factor in confidence_factors:
                    response += f"  + {factor}\n"

            if uncertainty_indicators:
                response += f"- 不确定领域:\n"
                for indicator in uncertainty_indicators:
                    response += f"  - {indicator}\n"

            if final_confidence < 0.6:
                response += "\n建议: 置信度较低，建议获取更多上下文信息或明确告知用户限制"

            return response

        except Exception as e:
            logger.error(f"检查置信度失败: {e}")
            return f"置信度检查失败: {str(e)}"

    def _request_human_review_wrapper(self, input_str: str) -> str:
        """请求人工审核的包装函数"""
        try:
            import json
            data = json.loads(input_str) if input_str else {}
            user_query = data.get("user_query", "")
            current_answer = data.get("current_answer", "")
            concerns = data.get("concerns", "")

            review_request = {
                "timestamp": "2026-05-18",
                "user_query": user_query,
                "current_answer": current_answer,
                "concerns": concerns,
                "status": "pending"
            }

            logger.info(f"人工审核请求: {review_request}")

            response = "人工审核请求已提交:\n"
            response += f"- 问题: {user_query}\n"
            response += f"- 关注点: {concerns}\n"
            response += "- 状态: 等待人工审核\n"
            response += "- 临时回复: 很抱歉，我需要就这个问题咨询人工客服，请稍等片刻。"

            return response

        except Exception as e:
            logger.error(f"请求人工审核失败: {e}")
            return f"请求审核失败: {str(e)}"

    def _correct_response_wrapper(self, input_str: str) -> str:
        """纠正回答的包装函数"""
        try:
            import json
            data = json.loads(input_str) if input_str else {}
            original_response = data.get("original_response", "")
            problem_description = data.get("problem_description", "")
            user_query = data.get("user_query", "")

            if not self.reflection_agent or not self.reflection_agent.llm:
                return "纠正系统未初始化，无法生成纠正回答"

            correction_prompt = f"""请根据以下信息生成一个纠正后的回答。

原始问题: {user_query}

原始回答: {original_response}

需要纠正的问题: {problem_description}

请生成一个纠正后的回答，要求：
1. 解决上述问题
2. 保持回答的准确性和完整性
3. 使用友好、专业的语言风格
4. 不要包含任何函数名或技术术语
"""

            messages = [HumanMessage(content=correction_prompt)]
            corrected = self.reflection_agent.llm.invoke(messages)

            corrected_text = corrected.content if hasattr(corrected, 'content') else str(corrected)

            logger.info(f"回答已纠正")

            return f"纠正后的回答:\n\n{corrected_text}"

        except Exception as e:
            logger.error(f"纠正回答失败: {e}")
            return f"纠正失败: {str(e)}"

    def _get_error_recovery_suggestion_wrapper(self, input_str: str) -> str:
        """获取错误恢复建议的包装函数"""
        try:
            import json
            data = json.loads(input_str) if input_str else {}
            error_message = data.get("error_message", "")

            if not self.error_corrector:
                return "错误恢复系统未初始化"

            from agent.error_correction import AgentError, ErrorType
            error = AgentError(message=error_message)

            recovery_result = self.error_corrector.handle_error(error)

            response = f"错误分析:\n"
            response += f"- 错误类型: {recovery_result.get('error_type', 'unknown')}\n"
            response += f"- 严重程度: {recovery_result.get('severity', 'unknown')}\n"
            response += f"- 建议策略: {recovery_result.get('strategy_used', 'unknown')}\n"

            if recovery_result.get('should_retry'):
                response += "\n建议行动:\n"
                response += "- 系统将自动重试\n"
                response += "- 如果重试失败，请稍后手动重试\n"
            else:
                response += "\n建议行动:\n"
                response += "- 请开启新的对话尝试\n"
                response += "- 如果问题持续存在，请联系技术支持\n"

            if recovery_result.get('fallback_response'):
                response += f"\n备选回复: {recovery_result.get('fallback_response')}"

            return response

        except Exception as e:
            logger.error(f"获取错误恢复建议失败: {e}")
            return f"获取建议失败: {str(e)}"
