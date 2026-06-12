#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自我反思模块 - 负责评估Agent响应质量、检测错误并提供改进建议
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ReflectionAgent:
    """
    自我反思Agent - 在生成响应后进行质量评估和错误检测
    
    主要功能：
    1. 响应质量评估
    2. 错误检测和标记
    3. 改进建议生成
    4. 置信度评估
    5. 反思历史记录
    """
    
    def __init__(self, llm=None):
        self.llm = llm
        self._reflection_history: List[Dict] = []
        self._error_patterns: Dict[str, int] = {}
        self._confidence_threshold = 0.6
        
    def reflect(
        self,
        user_query: str,
        agent_response: str,
        tool_calls: List[Dict],
        context: Dict = None
    ) -> Dict[str, Any]:
        """
        对Agent响应进行自我反思
        
        Args:
            user_query: 用户问题
            agent_response: Agent生成的响应
            tool_calls: 调用的工具列表
            context: 额外上下文信息
            
        Returns:
            反思结果字典，包含：
            - quality_score: 质量评分 (0-1)
            - confidence: 置信度 (0-1)
            - errors: 错误列表
            - suggestions: 改进建议
            - needs_correction: 是否需要纠正
            - corrected_response: 纠正后的响应（如果有）
        """
        result = {
            "timestamp": datetime.now().isoformat(),
            "user_query": user_query,
            "original_response": agent_response,
            "quality_score": 1.0,
            "confidence": 1.0,
            "errors": [],
            "suggestions": [],
            "needs_correction": False,
            "corrected_response": None,
            "reflection_type": "initial"
        }
        
        # 1. 基础质量检查
        self._check_basic_quality(result)
        
        # 2. 工具调用错误检测
        self._check_tool_errors(result, tool_calls)
        
        # 3. 响应完整性检查
        self._check_completeness(result, user_query)
        
        # 4. 上下文一致性检查
        if context:
            self._check_context_consistency(result, context)
        
        # 5. 置信度评估
        self._evaluate_confidence(result)
        
        # 6. 生成改进建议
        if result["needs_correction"]:
            self._generate_suggestions(result)
            
        # 7. 如果需要纠正，生成纠正响应
        if result["needs_correction"] and self.llm:
            self._generate_correction(result, user_query, context)
        
        # 记录反思历史
        self._reflection_history.append(result)
        
        logger.info(f"反思完成: 质量={result['quality_score']:.2f}, "
                   f"置信度={result['confidence']:.2f}, "
                   f"需要纠正={result['needs_correction']}")
        
        return result
    
    def _check_basic_quality(self, result: Dict) -> None:
        """检查基础质量"""
        response = result["original_response"]
        errors = result["errors"]
        
        # 检查响应是否为空
        if not response or len(response.strip()) == 0:
            errors.append({
                "type": "empty_response",
                "severity": "high",
                "message": "响应内容为空"
            })
            result["quality_score"] *= 0.5
            result["needs_correction"] = True
        
        # 检查响应长度
        if len(response) < 10:
            errors.append({
                "type": "too_short",
                "severity": "medium",
                "message": "响应内容过短，可能不完整"
            })
            result["quality_score"] *= 0.8
        
        # 检查是否包含函数名残留
        import re
        function_patterns = [
            r'rag_search',
            r'get_weather',
            r'query_ticket',
            r'Action:\s*\w+',
            r'Tool:',
            r'调用工具:',
            r'function\s+\w+\s*\('
        ]
        
        for pattern in function_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                errors.append({
                    "type": "function_name_leak",
                    "severity": "medium",
                    "message": f"响应中包含函数名残留: {pattern}"
                })
                result["quality_score"] *= 0.85
                result["needs_correction"] = True
    
    def _check_tool_errors(self, result: Dict, tool_calls: List[Dict]) -> None:
        """检查工具调用错误"""
        errors = result["errors"]
        
        for tool_call in tool_calls:
            # 检查工具调用是否失败
            if tool_call.get("error"):
                errors.append({
                    "type": "tool_error",
                    "severity": "high",
                    "tool": tool_call.get("name", "unknown"),
                    "message": f"工具调用失败: {tool_call.get('error')}"
                })
                result["quality_score"] *= 0.6
                result["needs_correction"] = True
                self._record_error_pattern(tool_call.get("name", "unknown"))
            
            # 检查工具返回是否为空
            if tool_call.get("result") is None or tool_call.get("result") == "":
                if tool_call.get("name") != "rag_search":  # 搜索结果为空不一定是错误
                    errors.append({
                        "type": "empty_result",
                        "severity": "low",
                        "tool": tool_call.get("name", "unknown"),
                        "message": "工具返回结果为空"
                    })
    
    def _check_completeness(self, result: Dict, user_query: str) -> None:
        """检查响应完整性"""
        response = result["original_response"]
        query = user_query.lower()
        
        # 提取查询关键词
        question_indicators = ["什么", "如何", "怎么", "为什么", "哪里", "谁", "多少", "如何"]
        is_question = any(indicator in query for indicator in question_indicators)
        
        if is_question:
            # 问题类查询应该提供明确的答案
            if "不知道" in response or "无法" in response or "没有找到" in response:
                result["confidence"] *= 0.7
                
            # 检查是否回答了问题的关键点
            if len(response) < 50:
                result["confidence"] *= 0.8
                result["suggestions"].append("回答可能不够详细，建议提供更完整的解答")
    
    def _check_context_consistency(self, result: Dict, context: Dict) -> None:
        """检查上下文一致性"""
        response = result["original_response"]
        
        # 检查是否引用了不存在的信息
        if "根据" in response or "如前所述" in response or "上文提到" in response:
            if not context.get("has_previous_info"):
                result["errors"].append({
                    "type": "context_mismatch",
                    "severity": "medium",
                    "message": "响应引用了不存在的上下文信息"
                })
                result["quality_score"] *= 0.8
    
    def _evaluate_confidence(self, result: Dict) -> None:
        """评估置信度"""
        base_confidence = result["confidence"]
        quality = result["quality_score"]
        errors = result["errors"]
        
        # 基于错误数量降低置信度
        high_severity_errors = sum(1 for e in errors if e.get("severity") == "high")
        medium_severity_errors = sum(1 for e in errors if e.get("severity") == "medium")
        
        confidence = base_confidence * quality
        confidence -= high_severity_errors * 0.2
        confidence -= medium_severity_errors * 0.1
        
        result["confidence"] = max(0.0, min(1.0, confidence))
        
        # 如果置信度低于阈值，标记为需要纠正
        if result["confidence"] < self._confidence_threshold:
            result["needs_correction"] = True
    
    def _generate_suggestions(self, result: Dict) -> None:
        """生成改进建议"""
        errors = result["errors"]
        suggestions = result["suggestions"]
        
        error_type_to_suggestion = {
            "empty_response": "请提供有意义的响应内容，不要返回空响应",
            "too_short": "请提供更详细的回答，包含更多解释和背景信息",
            "function_name_leak": "请清除响应中的函数名和技术术语，使用用户友好的语言",
            "tool_error": "请检查工具调用参数，或换一种方式实现相同功能",
            "empty_result": "请明确告知用户未能找到相关信息，或建议其他查询方式",
            "context_mismatch": "请确保响应内容与对话上下文一致，不要引用不存在的信息",
            "low_confidence": "当前信息不足以生成高质量回答，建议获取更多上下文或明确告知用户限制"
        }
        
        for error in errors:
            error_type = error.get("type")
            if error_type in error_type_to_suggestion:
                suggestions.append(error_type_to_suggestion[error_type])
    
    def _generate_correction(
        self,
        result: Dict,
        user_query: str,
        context: Dict = None
    ) -> None:
        """生成纠正后的响应"""
        try:
            # 构建纠正提示
            correction_prompt = f"""你是一个智能客服助手。请根据用户的原始问题和我提供的反思意见，生成一个改进后的回答。

原始问题: {user_query}

原始回答: {result['original_response']}

需要改进的问题:
{chr(10).join(f"- {s}" for s in result['suggestions'])}

请生成一个改进后的回答，要求：
1. 解决上述所有问题
2. 保持回答的准确性和有用性
3. 使用友好、专业的语言风格
4. 不要包含任何函数名或技术术语
"""
            
            # 调用LLM生成纠正响应
            if self.llm:
                from langchain.schema import HumanMessage
                messages = [HumanMessage(content=correction_prompt)]
                corrected = self.llm.invoke(messages)
                result["corrected_response"] = corrected.content if hasattr(corrected, 'content') else str(corrected)
                result["reflection_type"] = "corrected"
                
        except Exception as e:
            logger.error(f"生成纠正响应失败: {e}")
            result["correction_error"] = str(e)
    
    def _record_error_pattern(self, tool_name: str) -> None:
        """记录错误模式"""
        if tool_name in self._error_patterns:
            self._error_patterns[tool_name] += 1
        else:
            self._error_patterns[tool_name] = 1
    
    def get_reflection_stats(self) -> Dict[str, Any]:
        """获取反思统计信息"""
        total = len(self._reflection_history)
        if total == 0:
            return {
                "total_reflections": 0,
                "avg_quality_score": 0,
                "avg_confidence": 0,
                "correction_rate": 0,
                "top_errors": []
            }
        
        avg_quality = sum(r["quality_score"] for r in self._reflection_history) / total
        avg_confidence = sum(r["confidence"] for r in self._reflection_history) / total
        corrections = sum(1 for r in self._reflection_history if r.get("needs_correction"))
        
        # 统计错误类型
        error_counts = {}
        for r in self._reflection_history:
            for error in r.get("errors", []):
                error_type = error.get("type", "unknown")
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        top_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "total_reflections": total,
            "avg_quality_score": avg_quality,
            "avg_confidence": avg_confidence,
            "correction_rate": corrections / total if total > 0 else 0,
            "error_patterns": self._error_patterns.copy(),
            "top_errors": top_errors
        }
    
    def should_retry(self, reflection_result: Dict) -> bool:
        """判断是否需要重试"""
        return (
            reflection_result.get("needs_correction", False) and
            reflection_result.get("confidence", 1.0) < 0.5 and
            reflection_result.get("corrected_response") is None
        )
    
    def clear_history(self) -> None:
        """清除反思历史"""
        self._reflection_history.clear()
        logger.info("反思历史已清除")
