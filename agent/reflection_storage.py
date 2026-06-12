#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
反思结果存储模块 - 将反思结果持久化到数据库，支持学习和分析
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ReflectionStorage:
    """
    反思结果存储器
    
    将反思结果存储到MySQL数据库，支持：
    1. 存储反思历史
    2. 存储错误模式
    3. 学习改进建议
    4. 统计分析
    """
    
    _instance = None
    
    def __new__(cls, connection_pool=None):
        if cls._instance is None:
            cls._instance = super(ReflectionStorage, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, connection_pool=None):
        if self._initialized:
            return
        self._initialized = True
        self._connection_pool = connection_pool
        self._reflection_history: List[Dict] = []
        
    def set_connection_pool(self, connection_pool):
        """设置连接池"""
        self._connection_pool = connection_pool
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """确保反思存储表存在"""
        if not self._connection_pool:
            return
            
        conn = None
        try:
            conn = self._connection_pool.get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS reflection_history (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        session_id VARCHAR(36),
                        user_query TEXT,
                        original_response TEXT,
                        corrected_response TEXT,
                        quality_score FLOAT,
                        confidence FLOAT,
                        errors TEXT,
                        suggestions TEXT,
                        reflection_type VARCHAR(50),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_session_id (session_id),
                        INDEX idx_quality_score (quality_score),
                        INDEX idx_created_at (created_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS error_patterns (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        error_type VARCHAR(100),
                        error_count INT DEFAULT 1,
                        last_occurrence TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        suggested_fix TEXT,
                        success_rate FLOAT,
                        INDEX idx_error_type (error_type)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS learning_insights (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        insight_type VARCHAR(50),
                        content TEXT,
                        frequency INT DEFAULT 1,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_insight_type (insight_type)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
            conn.commit()
            logger.info("反思存储表初始化完成")
            
        except Exception as e:
            logger.error(f"初始化反思存储表失败: {e}")
        finally:
            if conn:
                self._connection_pool.return_connection(conn)
    
    def save_reflection(
        self,
        session_id: str,
        user_query: str,
        original_response: str,
        reflection_result: Dict
    ) -> bool:
        """
        保存反思结果
        
        Args:
            session_id: 会话ID
            user_query: 用户问题
            original_response: 原始响应
            reflection_result: 反思结果
            
        Returns:
            是否保存成功
        """
        conn = None
        try:
            if not self._connection_pool:
                # 仅保存到内存
                self._reflection_history.append({
                    "session_id": session_id,
                    "user_query": user_query,
                    "original_response": original_response,
                    "reflection_result": reflection_result,
                    "timestamp": datetime.now().isoformat()
                })
                return True
            
            conn = self._connection_pool.get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO reflection_history 
                    (session_id, user_query, original_response, corrected_response,
                     quality_score, confidence, errors, suggestions, reflection_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    session_id,
                    user_query,
                    original_response,
                    reflection_result.get("corrected_response"),
                    reflection_result.get("quality_score"),
                    reflection_result.get("confidence"),
                    json.dumps(reflection_result.get("errors", []), ensure_ascii=False),
                    json.dumps(reflection_result.get("suggestions", []), ensure_ascii=False),
                    reflection_result.get("reflection_type", "initial")
                ))
            
            conn.commit()
            logger.debug(f"反思结果已保存: session_id={session_id}")
            return True
            
        except Exception as e:
            logger.error(f"保存反思结果失败: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                self._connection_pool.return_connection(conn)
    
    def record_error_pattern(
        self,
        error_type: str,
        suggested_fix: str = None
    ) -> bool:
        """
        记录错误模式
        
        Args:
            error_type: 错误类型
            suggested_fix: 建议修复方式
            
        Returns:
            是否记录成功
        """
        conn = None
        try:
            if not self._connection_pool:
                return False
                
            conn = self._connection_pool.get_connection()
            with conn.cursor() as cursor:
                # 检查是否已存在
                cursor.execute(
                    "SELECT id, error_count FROM error_patterns WHERE error_type = %s",
                    (error_type,)
                )
                result = cursor.fetchone()
                
                if result:
                    # 更新现有记录
                    cursor.execute("""
                        UPDATE error_patterns 
                        SET error_count = error_count + 1,
                            last_occurrence = CURRENT_TIMESTAMP
                        WHERE error_type = %s
                    """, (error_type,))
                else:
                    # 插入新记录
                    cursor.execute("""
                        INSERT INTO error_patterns (error_type, suggested_fix)
                        VALUES (%s, %s)
                    """, (error_type, suggested_fix))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"记录错误模式失败: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                self._connection_pool.return_connection(conn)
    
    def get_reflection_stats(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        获取反思统计信息
        
        Args:
            days: 统计最近几天的数据
            
        Returns:
            统计信息字典
        """
        if not self._connection_pool:
            return self._get_memory_stats()
        
        conn = None
        try:
            conn = self._connection_pool.get_connection()
            with conn.cursor() as cursor:
                # 总反思次数
                cursor.execute("""
                    SELECT COUNT(*) as total,
                           AVG(quality_score) as avg_quality,
                           AVG(confidence) as avg_confidence,
                           SUM(CASE WHEN corrected_response IS NOT NULL THEN 1 ELSE 0 END) as corrections
                    FROM reflection_history
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                """, (days,))
                overall = cursor.fetchone()
                
                # 错误类型分布
                cursor.execute("""
                    SELECT error_type, error_count, suggested_fix
                    FROM error_patterns
                    ORDER BY error_count DESC
                    LIMIT 10
                """)
                top_errors = cursor.fetchall()
                
                # 每日统计
                cursor.execute("""
                    SELECT DATE(created_at) as date,
                           COUNT(*) as count,
                           AVG(quality_score) as avg_quality
                    FROM reflection_history
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                    GROUP BY DATE(created_at)
                    ORDER BY date
                """, (days,))
                daily_stats = cursor.fetchall()
            
            return {
                "period_days": days,
                "total_reflections": overall[0] or 0,
                "avg_quality_score": round(overall[1] or 0, 3),
                "avg_confidence": round(overall[2] or 0, 3),
                "corrections_count": overall[3] or 0,
                "correction_rate": round((overall[3] or 0) / max(overall[0] or 1, 1), 3),
                "top_error_patterns": top_errors or [],
                "daily_stats": daily_stats or []
            }
            
        except Exception as e:
            logger.error(f"获取反思统计失败: {e}")
            return {}
        finally:
            if conn:
                self._connection_pool.return_connection(conn)
    
    def _get_memory_stats(self) -> Dict[str, Any]:
        """获取内存统计（无数据库时）"""
        if not self._reflection_history:
            return {
                "total_reflections": 0,
                "avg_quality_score": 0,
                "avg_confidence": 0,
                "corrections_count": 0
            }
        
        total = len(self._reflection_history)
        avg_quality = sum(
            r["reflection_result"].get("quality_score", 0)
            for r in self._reflection_history
        ) / total
        avg_confidence = sum(
            r["reflection_result"].get("confidence", 0)
            for r in self._reflection_history
        ) / total
        corrections = sum(
            1 for r in self._reflection_history
            if r["reflection_result"].get("corrected_response")
        )
        
        return {
            "total_reflections": total,
            "avg_quality_score": round(avg_quality, 3),
            "avg_confidence": round(avg_confidence, 3),
            "corrections_count": corrections,
            "correction_rate": round(corrections / max(total, 1), 3),
            "source": "memory"
        }
    
    def get_common_errors(self, limit: int = 5) -> List[Dict]:
        """获取常见错误列表"""
        if not self._connection_pool:
            return []
        
        conn = None
        try:
            conn = self._connection_pool.get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT error_type, error_count, suggested_fix
                    FROM error_patterns
                    ORDER BY error_count DESC
                    LIMIT %s
                """, (limit,))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"获取常见错误失败: {e}")
            return []
        finally:
            if conn:
                self._connection_pool.return_connection(conn)
    
    def get_recent_reflections(
        self,
        limit: int = 10,
        session_id: str = None
    ) -> List[Dict]:
        """获取最近的反思记录"""
        if not self._connection_pool:
            return self._reflection_history[-limit:]
        
        conn = None
        try:
            conn = self._connection_pool.get_connection()
            with conn.cursor() as cursor:
                if session_id:
                    cursor.execute("""
                        SELECT session_id, user_query, original_response,
                               corrected_response, quality_score, confidence,
                               reflection_type, created_at
                        FROM reflection_history
                        WHERE session_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    """, (session_id, limit))
                else:
                    cursor.execute("""
                        SELECT session_id, user_query, original_response,
                               corrected_response, quality_score, confidence,
                               reflection_type, created_at
                        FROM reflection_history
                        ORDER BY created_at DESC
                        LIMIT %s
                    """, (limit,))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"获取最近反思失败: {e}")
            return []
        finally:
            if conn:
                self._connection_pool.return_connection(conn)
    
    def learn_from_reflection(
        self,
        reflection_result: Dict
    ) -> Optional[str]:
        """
        从反思结果中学习，生成改进建议
        
        Args:
            reflection_result: 反思结果
            
        Returns:
            学习到的见解（如果有）
        """
        if not reflection_result.get("needs_correction"):
            return None
        
        errors = reflection_result.get("errors", [])
        suggestions = reflection_result.get("suggestions", [])
        
        if not errors:
            return None
        
        # 生成学习见解
        error_types = [e.get("type") for e in errors]
        
        insight = f"从反思中学习: 检测到 {len(errors)} 个问题"
        if error_types:
            insight += f"，主要错误类型: {', '.join(set(error_types))}"
        
        # 记录错误模式
        for error in errors:
            self.record_error_pattern(
                error_type=error.get("type", "unknown"),
                suggested_fix=error.get("message")
            )
        
        return insight
