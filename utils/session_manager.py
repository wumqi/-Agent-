"""会话管理器 - 负责会话的持久化存储和管理"""

import pymysql
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from utils.config_handler import load_db_config
from utils.redis_manager import redis_manager
from utils.connection_pool import ConnectionPool
import logging
import traceback
import json as json_lib

logger = logging.getLogger(__name__)


class SessionManager:
    """会话管理器 - 处理会话的CRUD操作"""
    
    def __init__(self):
        self.db_config = load_db_config()
        ConnectionPool.init_pool(self.db_config)
        self._init_database()
    
    def _init_database(self):
        """初始化数据库和表"""
        password = str(self.db_config.get('password', '')).strip()
        conn = None
        
        try:
            # 先连接到MySQL服务器（不指定数据库）
            conn = pymysql.connect(
                host=str(self.db_config.get('host', 'localhost')),
                port=int(self.db_config.get('port', 3306)),
                user=str(self.db_config.get('user', 'root')),
                password=password if password else None,
                charset='utf8mb4'
            )
            
            with conn.cursor() as cursor:
                cursor.execute("CREATE DATABASE IF NOT EXISTS agent_chat CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            
            conn.commit()
            logger.info("数据库初始化成功")
            
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
        finally:
            if conn:
                conn.close()
        
        # 创建表
        conn = None
        try:
            conn = ConnectionPool.get_connection()
            
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 创建会话表（添加user_id字段）
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id VARCHAR(36) PRIMARY KEY,
                        user_id VARCHAR(36),
                        title VARCHAR(255) DEFAULT '新会话',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_user_id (user_id),
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 创建消息表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        session_id VARCHAR(36),
                        role VARCHAR(20) NOT NULL,
                        content TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_session_id (session_id),
                        INDEX idx_created_at (created_at),
                        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 创建审计日志表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        action VARCHAR(50) NOT NULL,
                        user_id VARCHAR(36),
                        session_id VARCHAR(36),
                        ip_address VARCHAR(45),
                        success BOOLEAN DEFAULT TRUE,
                        error_message TEXT,
                        details JSON,
                        INDEX idx_action (action),
                        INDEX idx_user_id (user_id),
                        INDEX idx_timestamp (timestamp)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
            
            conn.commit()
            logger.info("数据表初始化成功")
            
            # 创建数据库索引
            self._create_indexes()
            
        except Exception as e:
            logger.error(f"数据表初始化失败: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                ConnectionPool.return_connection(conn)
    
    def _create_indexes(self):
        """创建数据库索引以优化查询性能"""
        conn = None
        try:
            conn = ConnectionPool.get_connection()
            
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 用户表索引
                try:
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_username ON users(username)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_email ON users(email)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_role ON users(role)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON users(status)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at_user ON users(created_at)")
                except Exception as e:
                    logger.debug(f"用户表索引创建或已存在: {e}")
                
                # 会话表索引（复合索引）
                try:
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_updated ON sessions(user_id, updated_at DESC)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_created ON sessions(user_id, created_at DESC)")
                except Exception as e:
                    logger.debug(f"会话表索引创建或已存在: {e}")
                
                # 消息表索引（复合索引）
                try:
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_created ON messages(session_id, created_at ASC)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_role ON messages(role)")
                except Exception as e:
                    logger.debug(f"消息表索引创建或已存在: {e}")
                
                # 审计日志表复合索引
                try:
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_action ON audit_logs(user_id, action)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_timestamp ON audit_logs(user_id, timestamp DESC)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_action_timestamp ON audit_logs(action, timestamp DESC)")
                except Exception as e:
                    logger.debug(f"审计日志表索引创建或已存在: {e}")
            
            conn.commit()
            logger.info("数据库索引优化完成")
            
        except Exception as e:
            logger.error(f"数据库索引创建失败: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                ConnectionPool.return_connection(conn)
    
    def create_session(self, session_id: str, title: str = "新会话", user_id: str = None) -> bool:
        """创建新会话
        
        Args:
            session_id: 会话ID
            title: 会话标题
            user_id: 用户ID（可选）
            
        Returns:
            是否成功
        """
        conn = None
        try:
            conn = ConnectionPool.get_connection()
            
            with conn.cursor() as cursor:
                # 兼容旧表结构
                try:
                    cursor.execute(
                        "INSERT INTO sessions (id, title, user_id) VALUES (%s, %s, %s)",
                        (session_id, title, user_id)
                    )
                except pymysql.Error:
                    # 如果 user_id 列不存在，使用兼容模式
                    cursor.execute(
                        "INSERT INTO sessions (id, title) VALUES (%s, %s)",
                        (session_id, title)
                    )
            
            conn.commit()
            
            # 使缓存失效
            redis_manager.delete_session_list(user_id)
            
            logger.info(f"会话创建成功: {session_id} (用户: {user_id})")
            return True
            
        except Exception as e:
            logger.error(f"创建会话失败 {session_id}: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if conn:
                ConnectionPool.return_connection(conn)
    
    def get_all_sessions(self, user_id: str = None, use_cache: bool = True) -> List[Dict]:
        """获取所有会话列表

        Args:
            user_id: 用户ID（可选），如果提供则只返回该用户的会话
            use_cache: 是否使用缓存，默认True

        Returns:
            会话列表
        """
        # 先尝试从缓存获取（如果启用缓存）
        if use_cache:
            cached_sessions = redis_manager.get_session_list(user_id)
            if cached_sessions is not None:
                return cached_sessions
        
        conn = None
        try:
            conn = ConnectionPool.get_connection()
            
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 兼容旧表结构（没有 user_id 列）
                try:
                    if user_id:
                        cursor.execute(
                            "SELECT id, title, user_id, created_at, updated_at FROM sessions WHERE user_id = %s ORDER BY updated_at DESC",
                            (user_id,)
                        )
                    else:
                        cursor.execute(
                            "SELECT id, title, user_id, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
                        )
                except pymysql.Error:
                    # 如果 user_id 列不存在，使用兼容模式
                    if user_id:
                        cursor.execute(
                            "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
                        )
                    else:
                        cursor.execute(
                            "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
                        )
                result = cursor.fetchall()
                
                # 确保结果中包含 user_id 字段
                for row in result:
                    if 'user_id' not in row:
                        row['user_id'] = None
            
            # 更新缓存
            redis_manager.set_session_list(user_id, result)
            
            logger.debug(f"获取会话列表成功，共 {len(result)} 个会话")
            return result
            
        except Exception as e:
            logger.error(f"获取会话列表失败: {e}")
            return []
            
        finally:
            if conn:
                ConnectionPool.return_connection(conn)
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """获取单个会话信息"""
        conn = None
        try:
            conn = ConnectionPool.get_connection()
            
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 兼容旧表结构
                try:
                    cursor.execute(
                        "SELECT id, title, user_id, created_at, updated_at FROM sessions WHERE id = %s",
                        (session_id,)
                    )
                except pymysql.Error:
                    cursor.execute(
                        "SELECT id, title, created_at, updated_at FROM sessions WHERE id = %s",
                        (session_id,)
                    )
                result = cursor.fetchone()
                
                # 确保结果中包含 user_id 字段
                if result and 'user_id' not in result:
                    result['user_id'] = None
            
            logger.debug(f"获取会话信息: {session_id}")
            return result
            
        except Exception as e:
            logger.error(f"获取会话信息失败 {session_id}: {e}")
            return None
            
        finally:
            if conn:
                ConnectionPool.return_connection(conn)
    
    def update_session_title(self, session_id: str, title: str) -> bool:
        """更新会话标题"""
        conn = None
        try:
            conn = ConnectionPool.get_connection()
            
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE sessions SET title = %s, updated_at = NOW() WHERE id = %s",
                    (title, session_id)
                )
            
            conn.commit()
            
            # 获取会话的user_id并使缓存失效
            session_info = self.get_session(session_id)
            if session_info:
                user_id = session_info.get('user_id')
                # 清除Redis缓存
                redis_manager.delete_session_list(user_id)
            
            logger.info(f"会话标题更新成功: {session_id} -> {title}")
            return True
            
        except Exception as e:
            logger.error(f"更新会话标题失败 {session_id}: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if conn:
                ConnectionPool.return_connection(conn)
    
    def delete_session(self, session_id: str, current_user_id: str = None) -> bool:
        """删除会话（级联删除消息）"""
        conn = None
        try:
            # 先获取会话信息用于缓存失效
            session_info = self.get_session(session_id)
            user_id = session_info.get('user_id') if session_info else None
            
            # 如果会话的user_id为空但提供了当前用户ID，使用当前用户ID清除缓存
            if user_id is None and current_user_id:
                user_id = current_user_id
            
            conn = ConnectionPool.get_connection()
            
            with conn.cursor() as cursor:
                # 先删除消息
                cursor.execute("DELETE FROM messages WHERE session_id = %s", (session_id,))
                messages_deleted = cursor.rowcount
                logger.info(f"删除消息数量: {messages_deleted}")
                
                # 再删除会话
                cursor.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
                session_deleted = cursor.rowcount
                logger.info(f"删除会话数量: {session_deleted}")
                
                if session_deleted == 0:
                    logger.warning(f"会话不存在或已被删除: {session_id}")
            
            conn.commit()
            logger.info(f"事务提交成功: {session_id}")
            
            # 使缓存失效
            redis_manager.invalidate_cache(session_id=session_id, user_id=user_id)
            if current_user_id and current_user_id != user_id:
                redis_manager.delete_session_list(current_user_id)
            logger.info(f"缓存失效完成: {session_id}")
            
            logger.info(f"会话删除成功: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除会话失败 {session_id}: {e}")
            logger.error(traceback.format_exc())
            if conn:
                conn.rollback()
            return False
            
        finally:
            if conn:
                ConnectionPool.return_connection(conn)
    
    def add_message(self, session_id: str, role: str, content: str) -> bool:
        """添加消息到会话"""
        conn = None
        try:
            conn = ConnectionPool.get_connection()
            
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 先检查会话是否存在
                cursor.execute("SELECT id FROM sessions WHERE id = %s", (session_id,))
                if cursor.fetchone() is None:
                    # 如果会话不存在，创建会话（兼容旧表结构）
                    try:
                        cursor.execute(
                            "INSERT INTO sessions (id, title, user_id) VALUES (%s, %s, %s)",
                            (session_id, "新会话", None)
                        )
                    except pymysql.Error as e:
                        # 如果 user_id 列不存在，使用兼容模式
                        cursor.execute(
                            "INSERT INTO sessions (id, title) VALUES (%s, %s)",
                            (session_id, "新会话")
                        )
                    logger.info(f"会话不存在，已自动创建: {session_id}")
                
                cursor.execute(
                    "INSERT INTO messages (session_id, role, content) VALUES (%s, %s, %s)",
                    (session_id, role, content)
                )
                cursor.execute(
                    "UPDATE sessions SET updated_at = NOW() WHERE id = %s",
                    (session_id,)
                )
            
            conn.commit()
            
            # 使缓存失效
            session_info = self.get_session(session_id)
            if session_info:
                redis_manager.delete_session_list(session_info.get('user_id'))
            redis_manager.delete_session_messages(session_id)
            
            logger.debug(f"消息添加成功: {session_id}, {role}")
            return True
            
        except Exception as e:
            logger.error(f"添加消息失败 {session_id}: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if conn:
                ConnectionPool.return_connection(conn)
    
    def get_messages(self, session_id: str) -> List[Dict]:
        """获取会话的所有消息"""
        # 先尝试从缓存获取
        cached_messages = redis_manager.get_session_messages(session_id)
        if cached_messages is not None:
            return cached_messages
        
        conn = None
        try:
            conn = ConnectionPool.get_connection()
            
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(
                    "SELECT role, content, created_at FROM messages WHERE session_id = %s ORDER BY created_at ASC",
                    (session_id,)
                )
                result = cursor.fetchall()
            
            # 更新缓存
            redis_manager.set_session_messages(session_id, result)
            
            logger.debug(f"获取消息成功: {session_id}, 共 {len(result)} 条")
            return result
            
        except Exception as e:
            logger.error(f"获取消息失败 {session_id}: {e}")
            return []
            
        finally:
            if conn:
                ConnectionPool.return_connection(conn)
    
    def clear_session_messages(self, session_id: str) -> bool:
        """清空会话的所有消息"""
        conn = None
        try:
            conn = ConnectionPool.get_connection()
            
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM messages WHERE session_id = %s", (session_id,))
                cursor.execute("UPDATE sessions SET updated_at = NOW() WHERE id = %s", (session_id,))
            
            conn.commit()
            
            # 使缓存失效
            session_info = self.get_session(session_id)
            if session_info:
                redis_manager.delete_session_list(session_info.get('user_id'))
            redis_manager.delete_session_messages(session_id)
            
            logger.info(f"会话消息清空成功: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"清空消息失败 {session_id}: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if conn:
                ConnectionPool.return_connection(conn)
    
    def save_audit_log(self, log_entry: Dict) -> bool:
        """保存审计日志到数据库
        
        Args:
            log_entry: 日志条目
            
        Returns:
            是否成功
        """
        conn = None
        try:
            conn = ConnectionPool.get_connection()
            
            with conn.cursor() as cursor:
                # 将 details 转换为 JSON 字符串
                details_json = json_lib.dumps(log_entry.get('details', {}), ensure_ascii=False) if log_entry.get('details') else '{}'
                
                cursor.execute("""
                    INSERT INTO audit_logs (action, user_id, session_id, ip_address, 
                                           success, error_message, details)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    log_entry.get('action'),
                    log_entry.get('user_id'),
                    log_entry.get('session_id'),
                    log_entry.get('ip_address'),
                    log_entry.get('success', True),
                    log_entry.get('error_message'),
                    details_json
                ))
            
            conn.commit()
            logger.debug(f"审计日志保存成功: {log_entry.get('action')}")
            return True
            
        except Exception as e:
            logger.error(f"保存审计日志失败: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if conn:
                ConnectionPool.return_connection(conn)
    
    def get_audit_logs(self, user_id: str = None, action: str = None, 
                       start_time: datetime = None, end_time: datetime = None,
                       page: int = 1, page_size: int = 20) -> Tuple[List[Dict], int]:
        """获取审计日志列表
        
        Args:
            user_id: 用户ID筛选（可选）
            action: 操作类型筛选（可选）
            start_time: 开始时间（可选）
            end_time: 结束时间（可选）
            page: 页码
            page_size: 每页数量
            
        Returns:
            (日志列表, 总数量)
        """
        conn = None
        try:
            conn = ConnectionPool.get_connection()
            
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 构建查询条件
                conditions = []
                params = []
                
                if user_id:
                    conditions.append("user_id = %s")
                    params.append(user_id)
                
                if action:
                    conditions.append("action = %s")
                    params.append(action)
                
                if start_time:
                    conditions.append("timestamp >= %s")
                    params.append(start_time)
                
                if end_time:
                    conditions.append("timestamp <= %s")
                    params.append(end_time)
                
                # 获取总数量
                count_sql = "SELECT COUNT(*) as total FROM audit_logs"
                if conditions:
                    count_sql += " WHERE " + " AND ".join(conditions)
                
                cursor.execute(count_sql, tuple(params))
                total = cursor.fetchone()['total']
                
                # 获取分页数据
                offset = (page - 1) * page_size
                sql = "SELECT * FROM audit_logs"
                if conditions:
                    sql += " WHERE " + " AND ".join(conditions)
                sql += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
                
                params.extend([page_size, offset])
                cursor.execute(sql, tuple(params))
                result = cursor.fetchall()
            
            return result, total
            
        except Exception as e:
            logger.error(f"获取审计日志失败: {e}")
            return [], 0
            
        finally:
            if conn:
                ConnectionPool.return_connection(conn)