"""安全审计模块

提供操作日志和访问日志记录功能，用于安全审计和问题追踪。
"""

import logging
import time
import json
from datetime import datetime
from typing import Dict, Optional, Any
from enum import Enum
from .session_manager import SessionManager


class AuditAction(Enum):
    """审计操作类型"""
    # 用户操作
    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
    USER_REGISTER = "USER_REGISTER"
    USER_UPDATE = "USER_UPDATE"
    USER_DELETE = "USER_DELETE"
    
    # 会话操作
    SESSION_CREATE = "SESSION_CREATE"
    SESSION_DELETE = "SESSION_DELETE"
    SESSION_SWITCH = "SESSION_SWITCH"
    
    # 消息操作
    MESSAGE_SEND = "MESSAGE_SEND"
    MESSAGE_DELETE = "MESSAGE_DELETE"
    
    # 文件操作
    FILE_UPLOAD = "FILE_UPLOAD"
    FILE_DELETE = "FILE_DELETE"
    
    # 知识库操作
    KB_ADD = "KB_ADD"
    KB_UPDATE = "KB_UPDATE"
    KB_DELETE = "KB_DELETE"
    
    # 系统操作
    SYSTEM_START = "SYSTEM_START"
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"
    SYSTEM_CONFIG_UPDATE = "SYSTEM_CONFIG_UPDATE"


class AuditLogger:
    """审计日志记录器"""
    
    def __init__(self):
        self._logger = logging.getLogger("audit")
        self._logger.setLevel(logging.INFO)
        
        # 添加文件处理器
        handler = logging.FileHandler("audit.log", encoding="utf-8")
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)
        
        self._session_manager = None
    
    def set_session_manager(self, session_manager):
        """设置会话管理器，用于持久化日志"""
        self._session_manager = session_manager
    
    def log(self, action: AuditAction, user_id: Optional[str] = None, 
            session_id: Optional[str] = None, ip_address: Optional[str] = None,
            details: Optional[Dict[str, Any]] = None, success: bool = True,
            error_message: Optional[str] = None):
        """记录审计日志
        
        Args:
            action: 操作类型
            user_id: 用户ID
            session_id: 会话ID
            ip_address: IP地址
            details: 详细信息
            success: 是否成功
            error_message: 错误信息
        """
        log_entry = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'action': action.value,
            'user_id': user_id,
            'session_id': session_id,
            'ip_address': ip_address,
            'success': success,
            'error_message': error_message,
            'details': details if details else {}
        }
        
        # 写入日志文件
        log_message = json.dumps(log_entry, ensure_ascii=False)
        self._logger.info(log_message)
        
        # 如果有会话管理器，也写入数据库
        if self._session_manager:
            try:
                self._session_manager.save_audit_log(log_entry)
            except Exception as e:
                self._logger.error(f"写入审计日志到数据库失败: {str(e)}")
    
    def log_user_login(self, user_id: str, ip_address: str = None, success: bool = True, 
                       error_message: str = None):
        """记录用户登录"""
        self.log(
            AuditAction.USER_LOGIN,
            user_id=user_id,
            ip_address=ip_address,
            success=success,
            error_message=error_message
        )
    
    def log_user_logout(self, user_id: str, ip_address: str = None):
        """记录用户登出"""
        self.log(
            AuditAction.USER_LOGOUT,
            user_id=user_id,
            ip_address=ip_address,
            success=True
        )
    
    def log_user_register(self, user_id: str, ip_address: str = None, success: bool = True,
                          error_message: str = None):
        """记录用户注册"""
        self.log(
            AuditAction.USER_REGISTER,
            user_id=user_id,
            ip_address=ip_address,
            success=success,
            error_message=error_message
        )
    
    def log_session_create(self, user_id: str, session_id: str, ip_address: str = None):
        """记录会话创建"""
        self.log(
            AuditAction.SESSION_CREATE,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            success=True
        )
    
    def log_session_delete(self, user_id: str, session_id: str, ip_address: str = None):
        """记录会话删除"""
        self.log(
            AuditAction.SESSION_DELETE,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            success=True
        )
    
    def log_message_send(self, user_id: str, session_id: str, content: str, 
                         ip_address: str = None, success: bool = True, 
                         error_message: str = None):
        """记录消息发送"""
        self.log(
            AuditAction.MESSAGE_SEND,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            details={'content_length': len(content)},
            success=success,
            error_message=error_message
        )
    
    def log_file_upload(self, user_id: str, filename: str, file_size: int, 
                        ip_address: str = None, success: bool = True,
                        error_message: str = None):
        """记录文件上传"""
        self.log(
            AuditAction.FILE_UPLOAD,
            user_id=user_id,
            ip_address=ip_address,
            details={'filename': filename, 'file_size': file_size},
            success=success,
            error_message=error_message
        )
    
    def log_kb_add(self, user_id: str, document_name: str, ip_address: str = None,
                   success: bool = True, error_message: str = None):
        """记录知识库添加"""
        self.log(
            AuditAction.KB_ADD,
            user_id=user_id,
            ip_address=ip_address,
            details={'document_name': document_name},
            success=success,
            error_message=error_message
        )
    
    def log_system_start(self):
        """记录系统启动"""
        self.log(
            AuditAction.SYSTEM_START,
            success=True,
            details={'timestamp': datetime.now().isoformat()}
        )
    
    def log_system_shutdown(self):
        """记录系统关闭"""
        self.log(
            AuditAction.SYSTEM_SHUTDOWN,
            success=True,
            details={'timestamp': datetime.now().isoformat()}
        )


# 创建全局审计日志器实例
audit_logger = AuditLogger()