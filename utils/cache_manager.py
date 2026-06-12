"""缓存管理器模块

提供会话缓存和消息缓存功能，减少数据库查询次数，提升响应速度。
"""

import time
import hashlib
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta


class CacheItem:
    """缓存项"""
    
    def __init__(self, value: Any, ttl: int = 300):
        """
        Args:
            value: 缓存值
            ttl: 过期时间（秒），默认5分钟
        """
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() - self.created_at > self.ttl


class CacheManager:
    """缓存管理器"""
    
    def __init__(self):
        self._session_cache: Dict[str, CacheItem] = {}  # 会话列表缓存
        self._message_cache: Dict[str, CacheItem] = {}  # 消息缓存
        self._user_cache: Dict[str, CacheItem] = {}    # 用户信息缓存
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
    
    def _generate_message_cache_key(self, session_id: str) -> str:
        """生成消息缓存键"""
        return f"messages_{session_id}"
    
    def get_session_list(self, user_id: str = None) -> Optional[List[Dict]]:
        """获取会话列表缓存
        
        Args:
            user_id: 用户ID，可选
            
        Returns:
            会话列表，如果缓存不存在或过期返回None
        """
        key = f"sessions_{user_id or 'all'}"
        item = self._session_cache.get(key)
        
        if item and not item.is_expired():
            self._cache_stats['hits'] += 1
            return item.value
        else:
            self._cache_stats['misses'] += 1
            return None
    
    def set_session_list(self, sessions: List[Dict], user_id: str = None, ttl: int = 120):
        """设置会话列表缓存
        
        Args:
            sessions: 会话列表
            user_id: 用户ID，可选
            ttl: 过期时间（秒），默认2分钟
        """
        key = f"sessions_{user_id or 'all'}"
        self._session_cache[key] = CacheItem(sessions, ttl)
    
    def get_messages(self, session_id: str) -> Optional[List[Dict]]:
        """获取消息缓存
        
        Args:
            session_id: 会话ID
            
        Returns:
            消息列表，如果缓存不存在或过期返回None
        """
        key = self._generate_message_cache_key(session_id)
        item = self._message_cache.get(key)
        
        if item and not item.is_expired():
            self._cache_stats['hits'] += 1
            return item.value
        else:
            self._cache_stats['misses'] += 1
            return None
    
    def set_messages(self, session_id: str, messages: List[Dict], ttl: int = 300):
        """设置消息缓存
        
        Args:
            session_id: 会话ID
            messages: 消息列表
            ttl: 过期时间（秒），默认5分钟
        """
        key = self._generate_message_cache_key(session_id)
        self._message_cache[key] = CacheItem(messages, ttl)
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        """获取用户信息缓存
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户信息，如果缓存不存在或过期返回None
        """
        item = self._user_cache.get(user_id)
        
        if item and not item.is_expired():
            self._cache_stats['hits'] += 1
            return item.value
        else:
            self._cache_stats['misses'] += 1
            return None
    
    def set_user(self, user_id: str, user_info: Dict, ttl: int = 1800):
        """设置用户信息缓存
        
        Args:
            user_id: 用户ID
            user_info: 用户信息
            ttl: 过期时间（秒），默认30分钟
        """
        self._user_cache[user_id] = CacheItem(user_info, ttl)
    
    def invalidate_session_list(self, user_id: str = None):
        """使会话列表缓存失效
        
        Args:
            user_id: 用户ID，可选
        """
        key = f"sessions_{user_id or 'all'}"
        if key in self._session_cache:
            del self._session_cache[key]
    
    def invalidate_messages(self, session_id: str):
        """使消息缓存失效
        
        Args:
            session_id: 会话ID
        """
        key = self._generate_message_cache_key(session_id)
        if key in self._message_cache:
            del self._message_cache[key]
    
    def invalidate_user(self, user_id: str):
        """使用户信息缓存失效
        
        Args:
            user_id: 用户ID
        """
        if user_id in self._user_cache:
            del self._user_cache[user_id]
    
    def clear_all(self):
        """清空所有缓存"""
        self._session_cache.clear()
        self._message_cache.clear()
        self._user_cache.clear()
        self._cache_stats['evictions'] += 1
    
    def get_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        total = self._cache_stats['hits'] + self._cache_stats['misses']
        hit_rate = round(self._cache_stats['hits'] / total * 100, 2) if total > 0 else 0
        return {
            'hits': self._cache_stats['hits'],
            'misses': self._cache_stats['misses'],
            'hit_rate': hit_rate,
            'evictions': self._cache_stats['evictions'],
            'session_cache_size': len(self._session_cache),
            'message_cache_size': len(self._message_cache),
            'user_cache_size': len(self._user_cache)
        }
    
    def cleanup(self):
        """清理过期缓存"""
        now = time.time()
        
        # 清理会话缓存
        expired_keys = [key for key, item in self._session_cache.items() 
                        if now - item.created_at > item.ttl]
        for key in expired_keys:
            del self._session_cache[key]
            self._cache_stats['evictions'] += 1
        
        # 清理消息缓存
        expired_keys = [key for key, item in self._message_cache.items() 
                        if now - item.created_at > item.ttl]
        for key in expired_keys:
            del self._message_cache[key]
            self._cache_stats['evictions'] += 1
        
        # 清理用户缓存
        expired_keys = [key for key, item in self._user_cache.items() 
                        if now - item.created_at > item.ttl]
        for key in expired_keys:
            del self._user_cache[key]
            self._cache_stats['evictions'] += 1


# 创建全局缓存管理器实例
cache_manager = CacheManager()