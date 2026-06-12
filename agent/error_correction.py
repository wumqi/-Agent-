#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
错误检测和纠正模块 - 提供错误恢复、重试机制和降级策略
"""

import logging
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorType(Enum):
    """错误类型"""
    TOOL_EXECUTION = "tool_execution"
    TOOL_NOT_FOUND = "tool_not_found"
    TOOL_TIMEOUT = "tool_timeout"
    LLM_ERROR = "llm_error"
    CONTEXT_OVERFLOW = "context_overflow"
    RATE_LIMIT = "rate_limit"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


class ErrorRecoveryStrategy(Enum):
    """错误恢复策略"""
    RETRY = "retry"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    FALLBACK_TOOLS = "fallback_tools"
    SIMPLIFY_QUERY = "simplify_query"
    REDUCE_CONTEXT = "reduce_context"
    ESCALATE = "escalate"
    FAIL_SAFE = "fail_safe"


class AgentError(Exception):
    """Agent错误基类"""
    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        recoverable: bool = True,
        details: Dict = None
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.severity = severity
        self.recoverable = recoverable
        self.details = details or {}
        self.timestamp = datetime.now()


class ErrorCorrector:
    """
    错误检测和纠正器
    
    功能：
    1. 错误分类和严重程度评估
    2. 自动重试机制
    3. 恢复策略选择
    4. 降级服务
    5. 错误日志记录
    """
    
    def __init__(self):
        # 重试配置
        self.max_retries = 3
        self.base_retry_delay = 1.0
        self.max_retry_delay = 30.0
        
        # 错误处理规则
        self._error_rules: Dict[ErrorType, Dict] = {
            ErrorType.TOOL_EXECUTION: {
                "severity": ErrorSeverity.MEDIUM,
                "recoverable": True,
                "default_strategy": ErrorRecoveryStrategy.RETRY_WITH_BACKOFF,
                "max_attempts": 3
            },
            ErrorType.TOOL_TIMEOUT: {
                "severity": ErrorSeverity.HIGH,
                "recoverable": True,
                "default_strategy": ErrorRecoveryStrategy.RETRY,
                "max_attempts": 2
            },
            ErrorType.TOOL_NOT_FOUND: {
                "severity": ErrorSeverity.CRITICAL,
                "recoverable": False,
                "default_strategy": ErrorRecoveryStrategy.FAIL_SAFE,
                "max_attempts": 0
            },
            ErrorType.LLM_ERROR: {
                "severity": ErrorSeverity.HIGH,
                "recoverable": True,
                "default_strategy": ErrorRecoveryStrategy.RETRY_WITH_BACKOFF,
                "max_attempts": 2
            },
            ErrorType.CONTEXT_OVERFLOW: {
                "severity": ErrorSeverity.HIGH,
                "recoverable": True,
                "default_strategy": ErrorRecoveryStrategy.REDUCE_CONTEXT,
                "max_attempts": 1
            },
            ErrorType.RATE_LIMIT: {
                "severity": ErrorSeverity.MEDIUM,
                "recoverable": True,
                "default_strategy": ErrorRecoveryStrategy.RETRY_WITH_BACKOFF,
                "max_attempts": 5
            },
            ErrorType.VALIDATION: {
                "severity": ErrorSeverity.LOW,
                "recoverable": True,
                "default_strategy": ErrorRecoveryStrategy.SIMPLIFY_QUERY,
                "max_attempts": 1
            }
        }
        
        # 错误统计
        self._error_stats: Dict[str, int] = {}
        self._total_errors = 0
        self._recovered_errors = 0
    
    def handle_error(
        self,
        error: Exception,
        context: Dict = None
    ) -> Dict[str, Any]:
        """
        处理错误并返回纠正结果
        
        Args:
            error: 发生的错误
            context: 错误上下文信息
            
        Returns:
            纠正结果，包含：
            - handled: 是否成功处理
            - strategy: 使用的策略
            - recovery_result: 恢复结果
            - should_retry: 是否应该重试
            - fallback_response: 降级响应
        """
        self._total_errors += 1
        context = context or {}
        
        # 错误分类
        error_info = self._classify_error(error)
        
        # 获取错误规则
        rule = self._error_rules.get(
            error_info["type"],
            self._error_rules[ErrorType.UNKNOWN]
        )
        
        logger.warning(
            f"检测到错误: 类型={error_info['type'].value}, "
            f"严重程度={error_info['severity'].value}, "
            f"可恢复={error_info['recoverable']}"
        )
        
        # 选择恢复策略
        strategy = self._select_strategy(error_info, rule, context)
        
        # 执行恢复
        recovery_result = self._execute_recovery(strategy, error_info, context)
        
        if recovery_result.get("recovered"):
            self._recovered_errors += 1
        
        return {
            "handled": recovery_result.get("recovered", False),
            "error_type": error_info["type"].value,
            "severity": error_info["severity"].value,
            "strategy_used": strategy.value,
            "recovery_result": recovery_result,
            "should_retry": (
                error_info["recoverable"] and
                recovery_result.get("retry_count", 0) < rule.get("max_attempts", 0)
            ),
            "fallback_response": recovery_result.get("fallback_response"),
            "error_details": error_info
        }
    
    def _classify_error(self, error: Exception) -> Dict[str, Any]:
        """分类错误"""
        error_msg = str(error).lower()
        error_type = ErrorType.UNKNOWN
        severity = ErrorSeverity.MEDIUM
        recoverable = True
        
        if "timeout" in error_msg or "timed out" in error_msg:
            error_type = ErrorType.TOOL_TIMEOUT
            severity = ErrorSeverity.HIGH
        elif "not found" in error_msg or "不存在" in error_msg:
            error_type = ErrorType.TOOL_NOT_FOUND
            severity = ErrorSeverity.CRITICAL
            recoverable = False
        elif "rate limit" in error_msg or "限流" in error_msg or "too many" in error_msg:
            error_type = ErrorType.RATE_LIMIT
            severity = ErrorSeverity.MEDIUM
        elif "context" in error_msg and ("overflow" in error_msg or "超出" in error_msg):
            error_type = ErrorType.CONTEXT_OVERFLOW
            severity = ErrorSeverity.HIGH
            recoverable = True
        elif "validation" in error_msg or "验证" in error_msg:
            error_type = ErrorType.VALIDATION
            severity = ErrorSeverity.LOW
        elif "llm" in error_msg or "model" in error_msg or "openai" in error_msg:
            error_type = ErrorType.LLM_ERROR
            severity = ErrorSeverity.HIGH
        elif "tool" in error_msg or "工具" in error_msg:
            error_type = ErrorType.TOOL_EXECUTION
            severity = ErrorSeverity.MEDIUM
        
        return {
            "type": error_type,
            "severity": severity,
            "recoverable": recoverable,
            "message": str(error)
        }
    
    def _select_strategy(
        self,
        error_info: Dict,
        rule: Dict,
        context: Dict
    ) -> ErrorRecoveryStrategy:
        """选择恢复策略"""
        error_type = error_info["type"]
        
        # 根据错误类型选择策略
        if error_type == ErrorType.CONTEXT_OVERFLOW:
            return ErrorRecoveryStrategy.REDUCE_CONTEXT
        elif error_type == ErrorType.TOOL_NOT_FOUND:
            return ErrorRecoveryStrategy.FALLBACK_TOOLS
        elif error_type == ErrorType.VALIDATION:
            return ErrorRecoveryStrategy.SIMPLIFY_QUERY
        elif error_type in [ErrorType.TOOL_EXECUTION, ErrorType.TOOL_TIMEOUT, ErrorType.LLM_ERROR]:
            return ErrorRecoveryStrategy.RETRY_WITH_BACKOFF
        elif error_type == ErrorType.RATE_LIMIT:
            return ErrorRecoveryStrategy.RETRY_WITH_BACKOFF
        
        return rule.get("default_strategy", ErrorRecoveryStrategy.FAIL_SAFE)
    
    def _execute_recovery(
        self,
        strategy: ErrorRecoveryStrategy,
        error_info: Dict,
        context: Dict
    ) -> Dict[str, Any]:
        """执行恢复策略"""
        result = {
            "recovered": False,
            "strategy": strategy.value,
            "retry_count": 0,
            "fallback_response": None
        }
        
        if strategy == ErrorRecoveryStrategy.RETRY:
            result = self._retry_strategy(error_info, context, result)
        elif strategy == ErrorRecoveryStrategy.RETRY_WITH_BACKOFF:
            result = self._retry_with_backoff_strategy(error_info, context, result)
        elif strategy == ErrorRecoveryStrategy.FALLBACK_TOOLS:
            result = self._fallback_tools_strategy(error_info, context, result)
        elif strategy == ErrorRecoveryStrategy.SIMPLIFY_QUERY:
            result = self._simplify_query_strategy(error_info, context, result)
        elif strategy == ErrorRecoveryStrategy.REDUCE_CONTEXT:
            result = self._reduce_context_strategy(error_info, context, result)
        elif strategy == ErrorRecoveryStrategy.FAIL_SAFE:
            result = self._fail_safe_strategy(error_info, context, result)
        
        return result
    
    def _retry_strategy(
        self,
        error_info: Dict,
        context: Dict,
        result: Dict
    ) -> Dict:
        """重试策略"""
        max_attempts = self._error_rules.get(
            error_info["type"],
            {}
        ).get("max_attempts", self.max_retries)
        
        for attempt in range(max_attempts):
            result["retry_count"] = attempt + 1
            logger.info(f"重试 attempt {attempt + 1}/{max_attempts}")
            
            # 模拟重试（实际使用时替换为真实重试逻辑）
            if self._can_recover(error_info):
                result["recovered"] = True
                logger.info(f"重试成功")
                return result
            
            time.sleep(0.5)
        
        result["fallback_response"] = self._generate_fallback_response(error_info)
        return result
    
    def _retry_with_backoff_strategy(
        self,
        error_info: Dict,
        context: Dict,
        result: Dict
    ) -> Dict:
        """带退避的重试策略"""
        max_attempts = self._error_rules.get(
            error_info["type"],
            {}
        ).get("max_attempts", self.max_retries)
        
        for attempt in range(max_attempts):
            result["retry_count"] = attempt + 1
            
            # 计算退避延迟
            delay = min(
                self.base_retry_delay * (2 ** attempt),
                self.max_retry_delay
            )
            
            logger.info(f"带退避重试: attempt {attempt + 1}/{max_attempts}, delay={delay}s")
            
            time.sleep(delay)
            
            if self._can_recover(error_info):
                result["recovered"] = True
                logger.info(f"带退避重试成功")
                return result
        
        result["fallback_response"] = self._generate_fallback_response(error_info)
        return result
    
    def _fallback_tools_strategy(
        self,
        error_info: Dict,
        context: Dict,
        result: Dict
    ) -> Dict:
        """工具降级策略"""
        original_tool = context.get("tool_name", "unknown")
        
        # 定义工具降级映射
        fallback_map = {
            "rag_search": "direct_search",
            "get_weather": "get_weather_simple",
            "query_ticket": "list_recent_tickets"
        }
        
        fallback_tool = fallback_map.get(original_tool)
        
        if fallback_tool:
            logger.info(f"使用降级工具: {fallback_tool}")
            result["fallback_tool"] = fallback_tool
            result["recovered"] = True
            return result
        
        result["fallback_response"] = (
            "抱歉，当前无法执行您请求的操作。"
            "请稍后再试，或联系技术支持获取帮助。"
        )
        return result
    
    def _simplify_query_strategy(
        self,
        error_info: Dict,
        context: Dict,
        result: Dict
    ) -> Dict:
        """简化查询策略"""
        original_query = context.get("query", "")
        
        # 简化查询逻辑
        simplified = original_query
        if len(original_query) > 100:
            simplified = original_query[:100] + "..."
        
        logger.info(f"简化查询: {original_query} -> {simplified}")
        result["simplified_query"] = simplified
        result["recovered"] = True
        return result
    
    def _reduce_context_strategy(
        self,
        error_info: Dict,
        context: Dict,
        result: Dict
    ) -> Dict:
        """减少上下文策略"""
        current_history = context.get("history", [])
        
        # 减少历史记录
        if len(current_history) > 10:
            reduced_history = current_history[-10:]
            logger.info(f"减少上下文: {len(current_history)} -> {len(reduced_history)}")
            result["reduced_history"] = reduced_history
            result["recovered"] = True
            return result
        
        result["fallback_response"] = (
            "当前对话上下文过长，无法继续处理。"
            "请开启新的对话，或减少问题复杂度。"
        )
        return result
    
    def _fail_safe_strategy(
        self,
        error_info: Dict,
        context: Dict,
        result: Dict
    ) -> Dict:
        """故障安全策略"""
        logger.error(f"不可恢复的错误: {error_info['message']}")
        
        result["recovered"] = False
        result["fallback_response"] = (
            "抱歉，系统遇到了一个无法自动恢复的问题。"
            "建议您：\n"
            "1. 稍后重试\n"
            "2. 简化您的问题\n"
            "3. 开启新的对话"
        )
        return result
    
    def _can_recover(self, error_info: Dict) -> bool:
        """判断是否可恢复"""
        return error_info.get("recoverable", False)
    
    def _generate_fallback_response(self, error_info: Dict) -> str:
        """生成降级响应"""
        error_type = error_info.get("type")
        
        fallback_responses = {
            ErrorType.TOOL_EXECUTION: "抱歉，服务暂时不可用，请稍后重试。",
            ErrorType.TOOL_TIMEOUT: "抱歉，请求超时，请检查网络后重试。",
            ErrorType.TOOL_NOT_FOUND: "抱歉，该功能暂时不可用。",
            ErrorType.LLM_ERROR: "抱歉，AI服务暂时繁忙，请稍后重试。",
            ErrorType.CONTEXT_OVERFLOW: "抱歉，对话太长无法处理，请开启新对话。",
            ErrorType.RATE_LIMIT: "抱歉，请求过于频繁，请稍后重试。",
            ErrorType.VALIDATION: "抱歉，输入验证失败，请检查后重试。",
            ErrorType.UNKNOWN: "抱歉，发生未知错误，请稍后重试。"
        }
        
        return fallback_responses.get(
            error_type,
            "抱歉，服务出现异常，请稍后重试。"
        )
    
    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计"""
        return {
            "total_errors": self._total_errors,
            "recovered_errors": self._recovered_errors,
            "recovery_rate": (
                self._recovered_errors / self._total_errors
                if self._total_errors > 0 else 0
            ),
            "error_breakdown": self._error_stats.copy()
        }
    
    def record_error(self, error_type: str) -> None:
        """记录错误类型"""
        self._error_stats[error_type] = self._error_stats.get(error_type, 0) + 1
