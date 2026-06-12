"""
Redis缓存管理器 - 只使用Redis缓存
支持会话缓存、消息缓存、用户缓存和上下文缓存
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# 需要导入的模块（放在前面避免循环导入问题）
import os


class CustomJSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理datetime对象"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        return super().default(obj)


class RedisManager:
    """Redis缓存管理器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        # 加载Redis配置
        self._host = os.getenv("REDIS_HOST", "localhost")
        self._port = int(os.getenv("REDIS_PORT", "6379"))
        self._db = int(os.getenv("REDIS_DB", "0"))
        self._password = os.getenv("REDIS_PASSWORD", "")
        self._timeout = int(os.getenv("REDIS_TIMEOUT", "10"))
        self._max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", "10"))
        
        # 缓存键前缀
        self._prefix = {
            "session_list": "chat:session:list:",    # 用户会话列表
            "session_messages": "chat:session:msgs:", # 会话消息
            "user_info": "chat:user:",               # 用户信息
            "context": "chat:context:",              # 对话上下文
            "summary": "chat:summary:",              # 对话摘要
            "response": "chat:response:",            # Agent响应缓存
            "query": "chat:query:",                  # 查询缓存（RAG检索结果）
            "knowledge": "chat:knowledge:",          # 知识库缓存
            "tag": "chat:tag:"                       # 缓存标签（用于批量失效）
        }
        
        # 缓存统计
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
        
        # Redis客户端
        self._client = None
        
        # 初始化连接
        self._init_connection()
    
    def _init_connection(self):
        """初始化Redis连接"""
        try:
            import redis
            
            pool = redis.ConnectionPool(
                host=self._host,
                port=self._port,
                db=self._db,
                password=self._password if self._password else None,
                socket_timeout=self._timeout,
                max_connections=self._max_connections
            )
            self._client = redis.Redis(connection_pool=pool)
            
            # 测试连接
            self._client.ping()
            logger.info(f"Redis连接成功: {self._host}:{self._port}/{self._db}")
        except ImportError:
            logger.error("Redis模块未安装，请安装redis模块: pip install redis")
            raise ImportError("Redis模块未安装")
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            raise ConnectionError(f"Redis连接失败: {e}")
    
    @property
    def client(self):
        """获取Redis客户端"""
        return self._client
    
    def _get_key(self, prefix: str, key: str) -> str:
        """生成完整的缓存键"""
        return f"{prefix}{key}"
    
    def get_session_list(self, user_id: str) -> Optional[List[Dict]]:
        """获取用户会话列表"""
        key = self._get_key(self._prefix["session_list"], user_id)
        try:
            data = self._client.get(key)
            if data:
                self._stats['hits'] += 1
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                return json.loads(data)
            self._stats['misses'] += 1
            return None
        except Exception as e:
            logger.error(f"获取会话列表失败: {e}")
            return None
    
    def set_session_list(self, user_id: str, sessions: List[Dict], ttl: int = 3600) -> bool:
        """设置用户会话列表"""
        key = self._get_key(self._prefix["session_list"], user_id)
        try:
            self._client.set(key, json.dumps(sessions, cls=CustomJSONEncoder), ex=ttl)
            self._stats['sets'] += 1
            return True
        except Exception as e:
            logger.error(f"设置会话列表失败: {e}")
            return False
    
    def _delete_by_pattern(self, pattern: str) -> int:
        """根据模式删除多个键"""
        try:
            deleted = 0
            keys = self._client.keys(pattern)
            if keys:
                deleted = self._client.delete(*keys)
                self._stats['deletes'] += deleted
            return deleted
        except Exception as e:
            logger.error(f"根据模式删除键失败 {pattern}: {e}")
            return 0
    
    def delete_session_list(self, user_id: str) -> bool:
        """删除用户会话列表"""
        key = self._get_key(self._prefix["session_list"], user_id)
        try:
            self._client.delete(key)
            self._stats['deletes'] += 1
            return True
        except Exception as e:
            logger.error(f"删除会话列表失败: {e}")
            return False
    
    def get_session_messages(self, session_id: str) -> Optional[List[Dict]]:
        """获取会话消息"""
        key = self._get_key(self._prefix["session_messages"], session_id)
        try:
            data = self._client.get(key)
            if data:
                self._stats['hits'] += 1
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                return json.loads(data)
            self._stats['misses'] += 1
            return None
        except Exception as e:
            logger.error(f"获取会话消息失败: {e}")
            return None
    
    def set_session_messages(self, session_id: str, messages: List[Dict], ttl: int = 7200) -> bool:
        """设置会话消息"""
        key = self._get_key(self._prefix["session_messages"], session_id)
        try:
            self._client.set(key, json.dumps(messages, cls=CustomJSONEncoder), ex=ttl)
            self._stats['sets'] += 1
            return True
        except Exception as e:
            logger.error(f"设置会话消息失败: {e}")
            return False
    
    def delete_session_messages(self, session_id: str) -> bool:
        """删除会话消息"""
        key = self._get_key(self._prefix["session_messages"], session_id)
        try:
            self._client.delete(key)
            self._stats['deletes'] += 1
            return True
        except Exception as e:
            logger.error(f"删除会话消息失败: {e}")
            return False
    
    def get_user_info(self, user_id: str) -> Optional[Dict]:
        """获取用户信息"""
        key = self._get_key(self._prefix["user_info"], user_id)
        try:
            data = self._client.get(key)
            if data:
                self._stats['hits'] += 1
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                return json.loads(data)
            self._stats['misses'] += 1
            return None
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            return None
    
    def set_user_info(self, user_id: str, user_info: Dict, ttl: int = 86400) -> bool:
        """设置用户信息"""
        key = self._get_key(self._prefix["user_info"], user_id)
        try:
            self._client.set(key, json.dumps(user_info, cls=CustomJSONEncoder), ex=ttl)
            self._stats['sets'] += 1
            return True
        except Exception as e:
            logger.error(f"设置用户信息失败: {e}")
            return False
    
    def delete_user_info(self, user_id: str) -> bool:
        """删除用户信息"""
        key = self._get_key(self._prefix["user_info"], user_id)
        try:
            self._client.delete(key)
            self._stats['deletes'] += 1
            return True
        except Exception as e:
            logger.error(f"删除用户信息失败: {e}")
            return False
    
    def get_context(self, session_id: str) -> Optional[Dict]:
        """获取对话上下文"""
        key = self._get_key(self._prefix["context"], session_id)
        try:
            data = self._client.get(key)
            if data:
                self._stats['hits'] += 1
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                return json.loads(data)
            self._stats['misses'] += 1
            return None
        except Exception as e:
            logger.error(f"获取上下文失败: {e}")
            return None
    
    def set_context(self, session_id: str, context: Dict, ttl: int = 3600) -> bool:
        """设置对话上下文"""
        key = self._get_key(self._prefix["context"], session_id)
        try:
            self._client.set(key, json.dumps(context, cls=CustomJSONEncoder), ex=ttl)
            self._stats['sets'] += 1
            return True
        except Exception as e:
            logger.error(f"设置上下文失败: {e}")
            return False
    
    def delete_context(self, session_id: str) -> bool:
        """删除对话上下文"""
        key = self._get_key(self._prefix["context"], session_id)
        try:
            self._client.delete(key)
            self._stats['deletes'] += 1
            return True
        except Exception as e:
            logger.error(f"删除上下文失败: {e}")
            return False
    
    def get_summary(self, session_id: str) -> Optional[str]:
        """获取对话摘要"""
        key = self._get_key(self._prefix["summary"], session_id)
        try:
            data = self._client.get(key)
            if data:
                self._stats['hits'] += 1
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                return data
            self._stats['misses'] += 1
            return None
        except Exception as e:
            logger.error(f"获取摘要失败: {e}")
            return None
    
    def set_summary(self, session_id: str, summary: str, ttl: int = 7200) -> bool:
        """设置对话摘要"""
        key = self._get_key(self._prefix["summary"], session_id)
        try:
            self._client.set(key, summary, ex=ttl)
            self._stats['sets'] += 1
            return True
        except Exception as e:
            logger.error(f"设置摘要失败: {e}")
            return False
    
    def get_response(self, session_id: str, query_hash: str) -> Optional[str]:
        """获取缓存的Agent响应"""
        key = self._get_key(self._prefix["response"], f"{session_id}:{query_hash}")
        try:
            data = self._client.get(key)
            if data:
                self._stats['hits'] += 1
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                return data
            self._stats['misses'] += 1
            return None
        except Exception as e:
            logger.error(f"获取响应缓存失败: {e}")
            return None
    
    def set_response(self, session_id: str, query_hash: str, response: str, ttl: int = 1800) -> bool:
        """缓存Agent响应"""
        key = self._get_key(self._prefix["response"], f"{session_id}:{query_hash}")
        try:
            self._client.set(key, response, ex=ttl)
            self._stats['sets'] += 1
            return True
        except Exception as e:
            logger.error(f"设置响应缓存失败: {e}")
            return False
    
    def get_query_cache(self, query: str) -> Optional[Any]:
        """获取查询缓存（RAG检索结果）"""
        import hashlib
        query_hash = hashlib.md5(query.encode('utf-8')).hexdigest()
        key = self._get_key(self._prefix["query"], query_hash)
        try:
            data = self._client.get(key)
            if data:
                self._stats['hits'] += 1
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                return json.loads(data)
            self._stats['misses'] += 1
            return None
        except Exception as e:
            logger.error(f"获取查询缓存失败: {e}")
            return None
    
    def set_query_cache(self, query: str, result: Any, ttl: int = 300) -> bool:
        """设置查询缓存"""
        import hashlib
        query_hash = hashlib.md5(query.encode('utf-8')).hexdigest()
        key = self._get_key(self._prefix["query"], query_hash)
        try:
            self._client.set(key, json.dumps(result, cls=CustomJSONEncoder), ex=ttl)
            self._stats['sets'] += 1
            return True
        except Exception as e:
            logger.error(f"设置查询缓存失败: {e}")
            return False
    
    def get_knowledge_cache(self, key: str) -> Optional[Any]:
        """获取知识库缓存"""
        cache_key = self._get_key(self._prefix["knowledge"], key)
        try:
            data = self._client.get(cache_key)
            if data:
                self._stats['hits'] += 1
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                return json.loads(data)
            self._stats['misses'] += 1
            return None
        except Exception as e:
            logger.error(f"获取知识库缓存失败: {e}")
            return None
    
    def set_knowledge_cache(self, key: str, value: Any, ttl: int = 86400) -> bool:
        """设置知识库缓存"""
        cache_key = self._get_key(self._prefix["knowledge"], key)
        try:
            self._client.set(cache_key, json.dumps(value, cls=CustomJSONEncoder), ex=ttl)
            self._stats['sets'] += 1
            return True
        except Exception as e:
            logger.error(f"设置知识库缓存失败: {e}")
            return False
    
    def invalidate_cache(self, session_id: str = None, user_id: str = None) -> bool:
        """
        使缓存失效
        
        Args:
            session_id: 会话ID（可选）
            user_id: 用户ID（可选）
        """
        try:
            # 删除指定会话的消息缓存
            if session_id:
                self.delete_session_messages(session_id)
                
                # 删除上下文缓存
                self.delete_context(session_id)
                
                # 删除摘要缓存
                summary_key = self._get_key(self._prefix["summary"], session_id)
                self._delete_key(summary_key)
                
                # 删除响应缓存
                response_pattern = f"{self._prefix['response']}{session_id}:*"
                self._delete_by_pattern(response_pattern)
            
            # 删除用户会话列表缓存
            if user_id:
                self.delete_session_list(user_id)
            
            return True
        except Exception as e:
            logger.error(f"使缓存失效失败: {e}")
            return False
    
    def _delete_key(self, key: str) -> bool:
        """删除单个键"""
        try:
            self._client.delete(key)
            self._stats['deletes'] += 1
            return True
        except Exception as e:
            logger.error(f"删除键失败 {key}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        return self._stats.copy()


# 创建单例实例
redis_manager = RedisManager()


if __name__ == "__main__":
    # 测试代码
    test_user_id = "test_user_123"
    test_session_id = "test_session_456"
    
    # 设置会话列表
    sessions = [{"id": "s1", "title": "测试会话", "updated_at": "2024-01-01"}]
    result = redis_manager.set_session_list(test_user_id, sessions)
    print(f"设置会话列表: {result}")
    
    # 获取会话列表
    result = redis_manager.get_session_list(test_user_id)
    print(f"获取会话列表: {result}")
    
    # 设置会话消息
    messages = [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "您好！"}]
    result = redis_manager.set_session_messages(test_session_id, messages)
    print(f"设置会话消息: {result}")
    
    # 获取会话消息
    result = redis_manager.get_session_messages(test_session_id)
    print(f"获取会话消息: {result}")
    
    # 测试缓存失效
    result = redis_manager.invalidate_cache(session_id=test_session_id, user_id=test_user_id)
    print(f"使缓存失效: {result}")
    
    # 获取缓存统计
    stats = redis_manager.get_stats()
    print(f"缓存统计: {stats}")
    
    print("Redis缓存管理器测试完成！")