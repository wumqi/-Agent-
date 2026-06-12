"""
文件处理工具模块

提供文件操作相关的工具函数，包括：
- 文件MD5计算
- 文件列表获取（支持类型过滤）
- PDF/TXT文件加载
"""

import hashlib
import os.path
from typing import Tuple, List, Optional

from langchain_community.document_loaders import PyPDFLoader, TextLoader

from utils.logger_handler import logger

def get_file_md5_hex(filepath: str) -> Optional[str]:
    """
    计算文件的MD5值（十六进制字符串）
    
    Args:
        filepath: 文件的绝对路径
        
    Returns:
        文件的MD5十六进制字符串，失败返回None
        
    特点：
        - 使用4KB分片读取，避免大文件占用过多内存
        - 支持二进制文件读取
    """
    if not os.path.exists(filepath):
        logger.error(f"[MD5计算] 文件不存在: {filepath}")
        return None
        
    if not os.path.isfile(filepath):
        logger.error(f"[MD5计算] 路径不是文件: {filepath}")
        return None

    md5_obj = hashlib.md5()
    chunk_size = 4096  # 4KB分片读取，避免大文件爆内存
    
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                md5_obj.update(chunk)
            md5_hex = md5_obj.hexdigest()
            logger.debug(f"[MD5计算] 成功: {filepath} -> {md5_hex[:8]}...")
            return md5_hex
    except Exception as e:
        logger.error(f"[MD5计算] 失败 {filepath}: {str(e)}")
        return None


def listdir_with_allowed_type(path: str, allowed_types: Tuple[str, ...]) -> Tuple[str, ...]:
    """
    获取指定目录下所有允许类型的文件列表
    
    Args:
        path: 目录路径
        allowed_types: 允许的文件后缀元组，如 ("txt", "pdf")
        
    Returns:
        符合条件的文件路径元组，出错返回空元组
        
    Note:
        文件后缀匹配不区分大小写
    """
    files: List[str] = []

    if not os.path.isdir(path):
        logger.error(f"[文件列表] 路径不是目录: {path}")
        return tuple(files)

    for filename in os.listdir(path):
        if filename.lower().endswith(allowed_types):
            full_path = os.path.join(path, filename)
            if os.path.isfile(full_path):
                files.append(full_path)
                logger.debug(f"[文件列表] 发现文件: {filename}")

    logger.info(f"[文件列表] 目录 {path} 中发现 {len(files)} 个符合条件的文件")
    return tuple(files)


def pdf_loader(filepath: str, passwd: Optional[str] = None) -> List:
    """
    加载PDF文件内容
    
    Args:
        filepath: PDF文件路径
        passwd: PDF密码（可选）
        
    Returns:
        LangChain Document对象列表
    """
    try:
        logger.debug(f"[PDF加载] 开始加载: {filepath}")
        loader = PyPDFLoader(filepath, passwd)
        documents = loader.load()
        logger.info(f"[PDF加载] 成功，共 {len(documents)} 页")
        return documents
    except Exception as e:
        logger.error(f"[PDF加载] 失败 {filepath}: {str(e)}")
        return []


def txt_loader(filepath: str) -> List:
    """
    加载TXT文件内容
    
    Args:
        filepath: TXT文件路径（UTF-8编码）
        
    Returns:
        LangChain Document对象列表
    """
    try:
        logger.debug(f"[TXT加载] 开始加载: {filepath}")
        loader = TextLoader(filepath, encoding="utf-8")
        documents = loader.load()
        logger.info(f"[TXT加载] 成功")
        return documents
    except Exception as e:
        logger.error(f"[TXT加载] 失败 {filepath}: {str(e)}")
        return []