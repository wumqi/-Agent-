"""
配置处理器 - 支持从 .env 文件加载配置
从环境变量或 .env 文件读取配置
"""

import os
import json
from utils.path_tool import get_abs_path


def _load_env_file():
    """加载 .env 文件到环境变量"""
    env_path = get_abs_path(".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释
                    if not line or line.startswith('#'):
                        continue
                    # 解析 KEY=VALUE
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # 如果环境变量未设置，则从 .env 设置
                        if key not in os.environ:
                            os.environ[key] = value
            print(f"已加载配置文件: {env_path}")
        except Exception as e:
            print(f"加载 .env 文件失败: {e}")


# 加载 .env 文件
_load_env_file()


def load_rag_config() -> dict:
    """加载RAG配置，从 .env 文件读取"""
    config = {}
    
    # 从环境变量加载
    env_mapping = {
        "RAG_CHAT_MODEL_NAME": "chat_model_name",
        "RAG_EMBEDDING_MODEL_NAME": "embedding_model_name",
        "RAG_REDIS_HOST": "redis_host",
        "RAG_REDIS_PORT": "redis_port",
        "RAG_REDIS_DB": "redis_db",
        "RAG_REDIS_PASSWORD": "redis_password",
        "RAG_CACHE_EXPIRE_SECONDS": "cache_expire_seconds",
    }
    
    for env_name, config_key in env_mapping.items():
        env_value = os.getenv(env_name)
        if env_value is not None:
            if config_key in ["redis_port", "redis_db", "cache_expire_seconds"]:
                try:
                    config[config_key] = int(env_value)
                except ValueError:
                    config[config_key] = env_value
            else:
                config[config_key] = env_value
    
    return config


def load_chroma_config() -> dict:
    """加载Chroma配置，从 .env 文件读取"""
    config = {}
    
    # 从环境变量加载
    env_mapping = {
        "CHROMA_COLLECTION_NAME": "collection_name",
        "CHROMA_PERSIST_DIRECTORY": "persist_directory",
        "CHROMA_K": "k",
        "CHROMA_DATA_PATH": "data_path",
        "CHROMA_MD5_HEX_STORE": "md5_hex_store",
        "CHROMA_CHUNK_SIZE": "chunk_size",
        "CHROMA_CHUNK_OVERLAP": "chunk_overlap",
    }
    
    for env_name, config_key in env_mapping.items():
        env_value = os.getenv(env_name)
        if env_value is not None:
            if config_key in ["k", "chunk_size", "chunk_overlap"]:
                try:
                    config[config_key] = int(env_value)
                except ValueError:
                    config[config_key] = env_value
            else:
                config[config_key] = env_value
    
    # 处理列表类型
    allow_types = os.getenv("CHROMA_ALLOW_KNOWLEDGE_FILE_TYPE")
    if allow_types:
        try:
            config["allow_knowledge_file_type"] = json.loads(allow_types)
        except json.JSONDecodeError:
            config["allow_knowledge_file_type"] = [t.strip() for t in allow_types.split(",")]
    
    separators = os.getenv("CHROMA_SEPARATORS")
    if separators:
        try:
            config["separators"] = json.loads(separators)
        except json.JSONDecodeError:
            pass
    
    return config


def load_prompts_config() -> dict:
    """加载Prompts配置，从 .env 文件读取"""
    config = {}
    
    # 从环境变量加载
    env_mapping = {
        "PROMPTS_MAIN_PROMPT_PATH": "main_prompt_path",
        "PROMPTS_RAG_SUMMARIZE_PROMPT_PATH": "rag_summarize_prompt_path",
        "PROMPTS_REPORT_PROMPT_PATH": "report_prompt_path",
    }
    
    for env_name, config_key in env_mapping.items():
        env_value = os.getenv(env_name)
        if env_value is not None:
            config[config_key] = env_value
    
    return config


def load_agent_config() -> dict:
    """加载Agent配置，从 .env 文件读取"""
    config = {}
    
    # 从环境变量加载
    env_mapping = {
        "AGENT_EXTERNAL_DATA_PATH": "external_data_path",
        "AGENT_GAODE_KEY": "gaode_key",
    }
    
    for env_name, config_key in env_mapping.items():
        env_value = os.getenv(env_name)
        if env_value is not None:
            config[config_key] = env_value
    
    return config


def load_db_config() -> dict:
    """加载数据库配置，从 .env 文件读取"""
    config = {}
    
    # 从环境变量加载
    env_mapping = {
        "DB_HOST": "host",
        "DB_PORT": "port",
        "DB_USER": "user",
        "DB_PASSWORD": "password",
        "DB_DATABASE": "database",
        "DB_MAX_CONNECTIONS": "max_connections",
        "DB_MIN_IDLE_CONNECTIONS": "min_idle_connections",
        "DB_CONNECTION_TIMEOUT": "connection_timeout",
        "DB_MAX_RETRY_COUNT": "max_retry_count",
    }
    
    for env_name, config_key in env_mapping.items():
        env_value = os.getenv(env_name)
        if env_value is not None:
            if config_key in ["port", "max_connections", "min_idle_connections", 
                             "connection_timeout", "max_retry_count"]:
                try:
                    config[config_key] = int(env_value)
                except ValueError:
                    config[config_key] = env_value
            else:
                config[config_key] = env_value
    
    return config


# 全局配置实例
rag_conf = load_rag_config()
db_conf = load_db_config()
chroma_conf = load_chroma_config()
prompts_conf = load_prompts_config()
agent_conf = load_agent_config()

if __name__ == '__main__':
    print("RAG配置:", rag_conf)
    print("数据库配置:", db_conf)
    print("Chroma配置:", chroma_conf)
    print("Prompts配置:", prompts_conf)
    print("Agent配置:", agent_conf)
