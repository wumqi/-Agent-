"""输入验证模块

提供输入验证和安全过滤功能，防止SQL注入、XSS攻击等安全威胁。
"""

import re
import html
from typing import Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)


class InputValidator:
    """输入验证器"""
    
    # 常见的SQL注入模式
    SQL_INJECTION_PATTERNS = [
        r"(?i)\b(SELECT|INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|EXEC|UNION)\b",
        r"(?i)\b(AND|OR)\s+(\d+)\s*=\s*(\d+)",
        r"(?i)\b(UNION\s+SELECT|UNION ALL\s+SELECT)\b",
        r"(?i)\b(EXEC|EXECUTE)\s+[\w]+\(",
        r"(?i)\b(DECLARE|CREATE|DROP|ALTER)\s+(TABLE|PROCEDURE|FUNCTION|VIEW)\b",
        r"(?i)--.*$",
        r"(?i)/\*.*\*/",
        r"(?i)\b(WAITFOR|SLEEP|BENCHMARK)\b",
        r"(?i)\b(XOR|NOT)\s+(\d+)\s*=\s*(\d+)",
    ]
    
    # XSS攻击模式
    XSS_PATTERNS = [
        r"(?i)<script[^>]*>.*?</script>",
        r"(?i)<iframe[^>]*>.*?</iframe>",
        r"(?i)<img[^>]*on\w+\s*=",
        r"(?i)<a[^>]*href\s*=\s*[\"']javascript:",
        r"(?i)javascript:\s*[^\"']*[\"']",
        r"(?i)on\w+\s*=\s*[\"'].*?[\"']",
        r"(?i)<embed[^>]*>.*?</embed>",
        r"(?i)<object[^>]*>.*?</object>",
        r"(?i)<body[^>]*on\w+\s*=",
        r"(?i)<svg[^>]*on\w+\s*=",
    ]
    
    # 敏感关键词
    SENSITIVE_KEYWORDS = [
        'admin', 'root', 'password', 'secret', 'token', 'api_key',
        'credit', 'card', 'ssn', 'passport', '身份证', '银行卡',
        '密码', '账号', '账户', '验证码', '密钥', '私钥',
    ]
    
    def validate_username(self, username: str) -> Tuple[bool, Optional[str]]:
        """验证用户名
        
        Args:
            username: 用户名
            
        Returns:
            (是否有效, 错误信息)
        """
        if not username:
            return False, "用户名不能为空"
        
        if len(username) < 3:
            return False, "用户名至少需要3个字符"
        
        if len(username) > 50:
            return False, "用户名不能超过50个字符"
        
        # 只允许字母、数字、下划线
        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            return False, "用户名只能包含字母、数字和下划线"
        
        return True, None
    
    def validate_password(self, password: str) -> Tuple[bool, Optional[str]]:
        """验证密码
        
        Args:
            password: 密码
            
        Returns:
            (是否有效, 错误信息)
        """
        if not password:
            return False, "密码不能为空"
        
        if len(password) < 6:
            return False, "密码至少需要6个字符"
        
        if len(password) > 128:
            return False, "密码不能超过128个字符"
        
        # 检查是否包含至少一个数字和一个字母
        if not re.search(r"[a-zA-Z]", password) or not re.search(r"[0-9]", password):
            return False, "密码需要包含至少一个字母和一个数字"
        
        return True, None
    
    def validate_email(self, email: str) -> Tuple[bool, Optional[str]]:
        """验证邮箱
        
        Args:
            email: 邮箱地址
            
        Returns:
            (是否有效, 错误信息)
        """
        if not email:
            return False, "邮箱不能为空"
        
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            return False, "邮箱格式不正确"
        
        return True, None
    
    def validate_session_id(self, session_id: str) -> Tuple[bool, Optional[str]]:
        """验证会话ID
        
        Args:
            session_id: 会话ID
            
        Returns:
            (是否有效, 错误信息)
        """
        if not session_id:
            return False, "会话ID不能为空"
        
        # 检查是否为UUID格式
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        if not re.match(uuid_pattern, session_id, re.IGNORECASE):
            return False, "会话ID格式不正确"
        
        return True, None
    
    def validate_user_input(self, input_text: str) -> Tuple[bool, Optional[str], str]:
        """验证用户输入文本
        
        Args:
            input_text: 用户输入的文本
            
        Returns:
            (是否有效, 错误信息, 清理后的文本)
        """
        if not input_text:
            return False, "输入不能为空", ""
        
        # 检查长度
        if len(input_text) > 5000:
            return False, "输入内容过长，最多允许5000个字符", ""
        
        # 检查SQL注入
        for pattern in self.SQL_INJECTION_PATTERNS:
            if re.search(pattern, input_text):
                logger.warning(f"检测到SQL注入尝试: {input_text[:50]}...")
                return False, "输入包含非法内容", ""
        
        # 检查XSS攻击
        for pattern in self.XSS_PATTERNS:
            if re.search(pattern, input_text):
                logger.warning(f"检测到XSS攻击尝试: {input_text[:50]}...")
                return False, "输入包含非法内容", ""
        
        # HTML转义，防止XSS
        cleaned_text = html.escape(input_text)
        
        # 检查是否包含敏感关键词（仅记录，不阻止）
        for keyword in self.SENSITIVE_KEYWORDS:
            if keyword.lower() in cleaned_text.lower():
                logger.info(f"检测到敏感关键词 '{keyword}' 在输入中")
        
        return True, None, cleaned_text
    
    def sanitize_filename(self, filename: str) -> str:
        """清理文件名，防止路径遍历攻击
        
        Args:
            filename: 原始文件名
            
        Returns:
            清理后的文件名
        """
        if not filename:
            return "unnamed"
        
        # 移除路径分隔符
        sanitized = re.sub(r"[\\/]", "_", filename)
        
        # 移除特殊字符
        sanitized = re.sub(r"[<>:\"]|[\x00-\x1f]", "", sanitized)
        
        # 限制长度
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        
        # 如果清理后为空，返回默认名称
        if not sanitized:
            sanitized = "unnamed"
        
        return sanitized
    
    def validate_file_size(self, file_size: int, max_size: int = 10 * 1024 * 1024) -> Tuple[bool, Optional[str]]:
        """验证文件大小
        
        Args:
            file_size: 文件大小（字节）
            max_size: 最大允许大小（字节），默认10MB
            
        Returns:
            (是否有效, 错误信息)
        """
        if file_size > max_size:
            return False, f"文件大小超过限制（最大{max_size//(1024*1024)}MB）"
        
        return True, None
    
    def validate_file_type(self, filename: str, allowed_extensions: list = None) -> Tuple[bool, Optional[str]]:
        """验证文件类型
        
        Args:
            filename: 文件名
            allowed_extensions: 允许的扩展名列表，默认['.txt', '.pdf', '.md']
            
        Returns:
            (是否有效, 错误信息)
        """
        if allowed_extensions is None:
            allowed_extensions = ['.txt', '.pdf', '.md']
        
        ext = filename.lower().strip()
        
        # 检查扩展名
        if not any(ext.endswith(allowed_ext) for allowed_ext in allowed_extensions):
            return False, f"不支持的文件类型，仅支持: {', '.join(allowed_extensions)}"
        
        return True, None


# 创建全局验证器实例
validator = InputValidator()