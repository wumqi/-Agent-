"""
Redis缓存处理模块
"""
import hashlib
import json
from typing import Optional, Any

import redis
from utils.config_handler import rag_conf
from utils.logger_handler import logger

class RedisCache:
    def __init__(self):
        self.host = rag_conf.get("redis_host", "localhost")
        self.port = rag_conf.get("redis_port", 6379)
        self.db = rag_conf.get("redis_db", 0)
        self.password = rag_conf.get("redis_password", None)
        self.expire_seconds = rag_conf.get("cache_expire_seconds", 3600)
        self.client = None
        self._connect()
    
    def _connect(self):
        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            self.client.ping()
            logger.info("Redis连接成功")
        except Exception as e:
            logger.warning(f"Redis连接失败: {str(e)}，将使用内存缓存作为备用")
            self.client = None
    
    def _generate_key(self, prefix: str, query: str) -> str:
        """生成缓存键,使用MD5哈希"""
        query_hash = hashlib.md5(query.encode('utf-8')).hexdigest()
        return f"{prefix}:{query_hash}"
    
    def get(self, prefix: str, query: str) -> Optional[Any]:
        """获取缓存数据"""
        if not self.client:
            return None
        
        try:
            key = self._generate_key(prefix, query)
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"获取缓存失败: {str(e)}")
            return None
    
    def set(self, prefix: str, query: str, data: Any, expire_seconds: Optional[int] = None) -> bool:
        """设置缓存数据"""
        if not self.client:
            return False
        
        try:
            key = self._generate_key(prefix, query)
            expire = expire_seconds if expire_seconds else self.expire_seconds
            self.client.setex(key, expire, json.dumps(data, ensure_ascii=False))
            return True
        except Exception as e:
            logger.error(f"设置缓存失败: {str(e)}")
            return False
    
    def delete(self, prefix: str, query: str) -> bool:
        """删除缓存数据"""
        if not self.client:
            return False
        
        try:
            key = self._generate_key(prefix, query)
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"删除缓存失败: {str(e)}")
            return False
    
    def clear_prefix(self, prefix: str) -> int:
        """删除指定前缀的所有缓存"""
        if not self.client:
            return 0
        
        try:
            keys = self.client.keys(f"{prefix}:*")
            if keys:
                return self.client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"清除前缀缓存失败: {str(e)}")
            return 0

redis_cache = RedisCache()

if __name__ == '__main__':
    cache = RedisCache()
    cache.set("test", "hello", {"value": "world"})
    result = cache.get("test", "hello")
    print(result)