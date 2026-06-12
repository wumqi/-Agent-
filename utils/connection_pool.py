#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库连接池管理 - 优化版本
支持配置连接池大小、超时时间等参数
"""

import pymysql
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ConnectionPool:
    """
    数据库连接池管理
    支持配置：
    - 最大连接数
    - 连接超时时间
    - 连接重试次数
    - 空闲连接回收时间
    """
    
    _pool = []
    _max_connections = 10
    _min_idle_connections = 2
    _connection_timeout = 30
    _max_retry_count = 3
    _db_config = None
    _initialized = False
    
    @classmethod
    def init_pool(cls, db_config: dict):
        """
        初始化连接池
        :param db_config: 数据库配置字典
        """
        cls._db_config = db_config
        
        # 从配置读取连接池参数
        cls._max_connections = int(db_config.get('max_connections', 10))
        cls._min_idle_connections = int(db_config.get('min_idle_connections', 2))
        cls._connection_timeout = int(db_config.get('connection_timeout', 30))
        cls._max_retry_count = int(db_config.get('max_retry_count', 3))
        
        cls._pool = []
        cls._initialized = True
        
        # 预创建最小空闲连接
        cls._prewarm_pool()
        
        logger.info(f"连接池初始化完成: max_connections={cls._max_connections}, "
                   f"min_idle={cls._min_idle_connections}, timeout={cls._connection_timeout}s")
    
    @classmethod
    def _prewarm_pool(cls):
        """预创建最小空闲连接"""
        for _ in range(cls._min_idle_connections):
            try:
                conn = cls._create_connection()
                cls._pool.append(conn)
            except Exception as e:
                logger.warning(f"预创建连接失败: {e}")
    
    @classmethod
    def _create_connection(cls):
        """创建新连接"""
        if cls._db_config is None:
            raise ValueError("连接池未初始化")
        
        password = str(cls._db_config.get('password', '')).strip()
        return pymysql.connect(
            host=str(cls._db_config.get('host', 'localhost')),
            port=int(cls._db_config.get('port', 3306)),
            user=str(cls._db_config.get('user', 'root')),
            password=password if password else None,
            database=str(cls._db_config.get('database', 'agent_chat')),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
            connect_timeout=cls._connection_timeout,
            read_timeout=cls._connection_timeout,
            write_timeout=cls._connection_timeout
        )
    
    @classmethod
    def get_connection(cls, retry_count: int = 0) -> pymysql.connections.Connection:
        """
        从连接池获取连接
        :param retry_count: 当前重试次数
        :return: 数据库连接
        """
        if not cls._initialized:
            raise ValueError("连接池未初始化，请先调用 init_pool()")
        
        # 如果连接池为空，创建新连接
        if not cls._pool:
            return cls._create_connection()
        
        # 从连接池获取连接
        conn = cls._pool.pop()
        
        # 检查连接是否仍然有效
        try:
            conn.ping(reconnect=True)
            return conn
        except Exception as e:
            logger.debug(f"连接已断开，尝试重新连接: {e}")
            
            # 关闭无效连接
            try:
                conn.close()
            except:
                pass
            
            # 重试获取连接
            if retry_count < cls._max_retry_count:
                return cls.get_connection(retry_count + 1)
            
            # 重试次数耗尽，创建新连接
            return cls._create_connection()
    
    @classmethod
    def return_connection(cls, conn: pymysql.connections.Connection):
        """
        将连接放回连接池
        :param conn: 数据库连接
        """
        if len(cls._pool) < cls._max_connections:
            try:
                # 重置连接状态
                conn.rollback()
                cls._pool.append(conn)
            except Exception as e:
                logger.warning(f"连接放回连接池失败: {e}")
                try:
                    conn.close()
                except:
                    pass
        else:
            # 连接池已满，直接关闭连接
            try:
                conn.close()
            except:
                pass
    
    @classmethod
    def get_pool_status(cls) -> dict:
        """
        获取连接池状态
        :return: 连接池状态字典
        """
        return {
            'total_connections': cls._max_connections,
            'idle_connections': len(cls._pool),
            'active_connections': cls._max_connections - len(cls._pool),
            'min_idle': cls._min_idle_connections,
            'timeout': cls._connection_timeout
        }
    
    @classmethod
    def close_all_connections(cls):
        """关闭所有连接"""
        while cls._pool:
            conn = cls._pool.pop()
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"关闭连接失败: {e}")
        logger.info("所有连接已关闭")
