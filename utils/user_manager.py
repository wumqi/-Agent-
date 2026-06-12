"""用户管理模块

提供用户注册、登录、权限管理等功能。
"""

import uuid
import hashlib
import pymysql
from datetime import datetime
from typing import Optional, Dict, Tuple, Any, List
from enum import Enum
import logging

from .validator import validator
from .cache_manager import cache_manager

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """用户角色"""
    ADMIN = "admin"       # 管理员
    USER = "user"         # 普通用户
    GUEST = "guest"       # 访客


class UserManager:
    """用户管理器"""
    
    def __init__(self, db_connection_pool):
        self._pool = db_connection_pool
    
    def _hash_password(self, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """哈希密码
        
        Args:
            password: 原始密码
            salt: 盐值，如果为None则生成新的盐值
            
        Returns:
            (哈希后的密码, 盐值)
        """
        if salt is None:
            salt = uuid.uuid4().hex[:16]
        
        # 使用SHA-256哈希，结合盐值
        hash_obj = hashlib.sha256()
        hash_obj.update((password + salt).encode('utf-8'))
        hashed_password = hash_obj.hexdigest()
        
        return hashed_password, salt
    
    def create_user(self, username: str, password: str, email: str = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """创建用户
        
        Args:
            username: 用户名
            password: 密码
            email: 邮箱（可选）
            
        Returns:
            (是否成功, 用户ID/错误信息, 错误信息)
        """
        # 验证输入
        valid, error = validator.validate_username(username)
        if not valid:
            return False, None, error
        
        valid, error = validator.validate_password(password)
        if not valid:
            return False, None, error
        
        if email:
            valid, error = validator.validate_email(email)
            if not valid:
                return False, None, error
        
        # 检查用户名是否已存在
        if self.get_user_by_username(username):
            return False, None, "用户名已存在"
        
        # 哈希密码
        hashed_password, salt = self._hash_password(password)
        
        # 创建用户ID
        user_id = str(uuid.uuid4())
        
        # 插入数据库
        try:
            conn = self._pool.get_connection()
            try:
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                
                # 创建用户表（如果不存在）
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id VARCHAR(36) PRIMARY KEY,
                        username VARCHAR(50) UNIQUE NOT NULL,
                        password VARCHAR(64) NOT NULL,
                        salt VARCHAR(16) NOT NULL,
                        email VARCHAR(100),
                        role VARCHAR(20) DEFAULT 'user',
                        status VARCHAR(20) DEFAULT 'active',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                
                # 插入用户数据
                cursor.execute("""
                    INSERT INTO users (id, username, password, salt, email, role)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (user_id, username, hashed_password, salt, email, UserRole.USER.value))
                
                conn.commit()
                
                # 更新缓存
                user_info = {
                    'id': user_id,
                    'username': username,
                    'email': email,
                    'role': UserRole.USER.value,
                    'status': 'active',
                    'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                cache_manager.set_user(user_id, user_info)
                
                logger.info(f"用户创建成功: {username} ({user_id})")
                return True, user_id, None
            
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"创建用户失败: {str(e)}")
            return False, None, f"创建用户失败: {str(e)}"
    
    def authenticate_user(self, username: str, password: str) -> Tuple[bool, Optional[Dict]]:
        """验证用户身份
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            (是否成功, 用户信息)
        """
        # 先从缓存获取
        user_info = cache_manager.get_user(username)
        if user_info:
            # 验证密码
            hashed_password, _ = self._hash_password(password, user_info.get('salt'))
            if hashed_password == user_info.get('password'):
                return True, user_info
        
        # 从数据库获取
        try:
            conn = self._pool.get_connection()
            try:
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                
                cursor.execute("""
                    SELECT id, username, password, salt, email, role, status, created_at, updated_at
                    FROM users WHERE username = %s AND status = 'active'
                """, (username,))
                
                result = cursor.fetchone()
                
                if result:
                    # 验证密码
                    hashed_password, _ = self._hash_password(password, result['salt'])
                    
                    if hashed_password == result['password']:
                        # 更新缓存
                        cache_manager.set_user(result['id'], result)
                        return True, result
                
                return False, None
            
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"用户认证失败: {str(e)}")
            return False, None
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """根据用户ID获取用户信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户信息，如果不存在返回None
        """
        # 先从缓存获取
        user_info = cache_manager.get_user(user_id)
        if user_info:
            return user_info
        
        # 从数据库获取
        try:
            conn = self._pool.get_connection()
            try:
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                
                cursor.execute("""
                    SELECT id, username, email, role, status, created_at, updated_at
                    FROM users WHERE id = %s
                """, (user_id,))
                
                result = cursor.fetchone()
                
                if result:
                    # 更新缓存
                    cache_manager.set_user(user_id, result)
                    return result
                
                return None
            
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}")
            return None
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """根据用户名获取用户信息
        
        Args:
            username: 用户名
            
        Returns:
            用户信息，如果不存在返回None
        """
        try:
            conn = self._pool.get_connection()
            try:
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                
                cursor.execute("""
                    SELECT id, username, email, role, status, created_at, updated_at
                    FROM users WHERE username = %s
                """, (username,))
                
                return cursor.fetchone()
            
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}")
            return None
    
    def update_user(self, user_id: str, **kwargs) -> Tuple[bool, Optional[str]]:
        """更新用户信息
        
        Args:
            user_id: 用户ID
            kwargs: 要更新的字段（email, password等）
            
        Returns:
            (是否成功, 错误信息)
        """
        update_fields = []
        update_values = []
        
        if 'email' in kwargs:
            valid, error = validator.validate_email(kwargs['email'])
            if not valid:
                return False, error
            update_fields.append("email = %s")
            update_values.append(kwargs['email'])
        
        if 'password' in kwargs:
            valid, error = validator.validate_password(kwargs['password'])
            if not valid:
                return False, error
            hashed_password, salt = self._hash_password(kwargs['password'])
            update_fields.append("password = %s")
            update_values.append(hashed_password)
            update_fields.append("salt = %s")
            update_values.append(salt)
        
        if 'role' in kwargs:
            if kwargs['role'] not in [r.value for r in UserRole]:
                return False, "无效的角色值"
            update_fields.append("role = %s")
            update_values.append(kwargs['role'])
        
        if 'status' in kwargs:
            update_fields.append("status = %s")
            update_values.append(kwargs['status'])
        
        if not update_fields:
            return False, "没有要更新的字段"
        
        update_values.append(user_id)
        
        try:
            conn = self._pool.get_connection()
            try:
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                
                sql = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
                cursor.execute(sql, tuple(update_values))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    # 使缓存失效
                    cache_manager.invalidate_user(user_id)
                    logger.info(f"用户信息更新成功: {user_id}")
                    return True, None
                else:
                    return False, "用户不存在"
            
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"更新用户信息失败: {str(e)}")
            return False, f"更新用户信息失败: {str(e)}"
    
    def delete_user(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """删除用户
        
        Args:
            user_id: 用户ID
            
        Returns:
            (是否成功, 错误信息)
        """
        try:
            conn = self._pool.get_connection()
            try:
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                
                # 先检查用户是否存在
                cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
                if not cursor.fetchone():
                    return False, "用户不存在"
                
                # 删除用户的会话和消息
                cursor.execute("DELETE FROM messages WHERE session_id IN (SELECT id FROM sessions WHERE user_id = %s)", (user_id,))
                cursor.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
                
                # 删除用户
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                
                conn.commit()
                
                # 使缓存失效
                cache_manager.invalidate_user(user_id)
                cache_manager.invalidate_session_list(user_id)
                
                logger.info(f"用户删除成功: {user_id}")
                return True, None
            
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"删除用户失败: {str(e)}")
            return False, f"删除用户失败: {str(e)}"
    
    def list_users(self, page: int = 1, page_size: int = 10) -> Tuple[List[Dict], int]:
        """获取用户列表
        
        Args:
            page: 页码
            page_size: 每页数量
            
        Returns:
            (用户列表, 总数量)
        """
        try:
            conn = self._pool.get_connection()
            try:
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                
                # 获取总数量
                cursor.execute("SELECT COUNT(*) as total FROM users")
                total = cursor.fetchone()['total']
                
                # 获取分页数据
                offset = (page - 1) * page_size
                cursor.execute("""
                    SELECT id, username, email, role, status, created_at, updated_at
                    FROM users ORDER BY created_at DESC LIMIT %s OFFSET %s
                """, (page_size, offset))
                
                users = cursor.fetchall()
                
                return users, total
            
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"获取用户列表失败: {str(e)}")
            return [], 0
    
    def is_admin(self, user_id: str) -> bool:
        """检查用户是否为管理员
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否为管理员
        """
        user_info = self.get_user_by_id(user_id)
        return user_info and user_info.get('role') == UserRole.ADMIN.value
    
    def create_admin_user(self, username: str, password: str, email: str = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """创建管理员用户
        
        Args:
            username: 用户名
            password: 密码
            email: 邮箱（可选）
            
        Returns:
            (是否成功, 用户ID/错误信息, 错误信息)
        """
        # 创建用户
        success, user_id, error = self.create_user(username, password, email)
        
        if success and user_id:
            # 更新为管理员角色
            self.update_user(user_id, role=UserRole.ADMIN.value)
        
        return success, user_id, error