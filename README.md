# 企业级智能客服与知识管理系统

基于多智能体架构的企业级智能客服与知识管理系统，支持多轮对话、知识库检索、工具调用等功能。

## ✨ 项目特性

- **多智能体架构**：基于 Supervisor 主控调度器的多智能体协作系统
- **RAG 知识库检索**：基于 ChromaDB 的向量检索引擎
- **MCP 协议封装**：标准化工具调用协议
- **多轮对话持久化**：基于 MySQL 的会话存储
- **Redis 缓存**：增强上下文理解，支持更长对话历史
- **自我反思机制**：响应质量评估与自动错误纠正
- **双端支持**：Streamlit 前端 + FastAPI 后端 API

## 🛠️ 技术栈

| 分类 | 技术 | 版本 |
|------|------|------|
| 前端框架 | Streamlit | >=1.28.0 |
| 后端框架 | FastAPI | >=0.110.0 |
| 数据库 | MySQL | - |
| 向量数据库 | ChromaDB | >=0.4.0 |
| 缓存 | Redis | >=5.0.0 |
| AI 框架 | LangChain | >=0.1.0 |
| 向量化模型 | DashScope Embeddings | text-embedding-v4 |
| 聊天模型 | Qwen | qwen3-max |

## 📁 项目结构

```
├── agent/                    # 智能体模块
│   ├── multi_agent/          # 多智能体架构
│   │   ├── supervisor.py     # Supervisor 主控调度器
│   │   └── nodes/            # 分支节点
│   │       ├── rag_node.py   # RAG 知识库检索节点
│   │       ├── chat_node.py  # 闲聊问答节点
│   │       ├── tool_node.py  # 工具调用节点
│   │       └── fallback_node.py  # 异常兜底节点
│   ├── mcp/                  # MCP 协议封装
│   │   ├── protocol.py       # MCP 协议数据模型
│   │   ├── server.py         # MCP Server
│   │   └── client.py         # MCP Client
│   ├── tools/                # 工具集合
│   ├── reflection_agent.py   # 自我反思模块
│   └── error_correction.py   # 错误纠正模块
├── api/                      # FastAPI 后端
│   ├── main.py               # 应用入口
│   ├── routers/              # 路由定义
│   ├── schemas/              # 数据模型
│   └── middleware/           # 中间件
├── rag/                      # RAG 知识库检索
│   ├── vector_store.py       # 向量存储
│   └── rag_service.py        # RAG 服务
├── utils/                    # 工具函数
│   ├── config_handler.py     # 配置处理
│   ├── session_manager.py    # 会话管理
│   ├── redis_manager.py      # Redis 缓存管理
│   └── audit_logger.py       # 审计日志
├── components/               # Streamlit 组件
├── data/                     # 知识库数据
├── prompts/                  # 提示词模板
├── .env                      # 环境变量配置
├── app.py                    # Streamlit 前端入口
└── requirements.txt          # 依赖清单
```

## 🚀 快速开始

### 环境要求

- Python >= 3.10
- MySQL >= 8.0
- Redis >= 7.0

### 安装步骤

1. **克隆项目**

```bash
git clone <repository-url>
cd Agent项目
```

2. **安装依赖**

```bash
pip install -r requirements.txt
```

3. **配置环境变量**

复制 `.env.example` 到 `.env` 并修改配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_DATABASE=agent_chat

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379

# AI 模型配置
RAG_CHAT_MODEL_NAME=qwen3-max
RAG_EMBEDDING_MODEL_NAME=text-embedding-v4
```

4. **初始化数据库**

创建 MySQL 数据库：

```sql
CREATE DATABASE agent_chat CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 运行方式

#### 方式一：Streamlit 前端应用

```bash
streamlit run app.py
```

访问地址：`http://localhost:8501`

#### 方式二：FastAPI 后端服务

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

访问地址：
- API 文档：`http://localhost:8000/docs`
- ReDoc 文档：`http://localhost:8000/redoc`

## 🔌 API 接口

### 认证接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/token` | 获取访问令牌 |

### 聊天接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/chat/stream` | SSE 流式问答 |
| POST | `/api/v1/chat` | 非流式问答 |

### 会话接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/sessions` | 获取会话列表 |
| POST | `/api/v1/sessions` | 创建新会话 |
| GET | `/api/v1/sessions/{session_id}` | 获取会话详情 |
| DELETE | `/api/v1/sessions/{session_id}` | 删除会话 |

## 🧠 多智能体架构

### 架构设计

```
用户输入
    │
    ▼
┌───────────────┐
│ Supervisor    │  ← 主控调度器
│ 意图识别      │
│ 路由分发      │
└───────┬───────┘
        │
   ┌────┴────┬─────────┬─────────────┐
   ▼         ▼         ▼             ▼
┌──────┐ ┌──────┐ ┌────────┐ ┌──────────┐
│ RAG  │ │ Chat │ │  Tool  │ │ Fallback │
│ Node │ │ Node │ │  Node  │ │   Node   │
└───┬──┘ └───┬──┘ └───┬────┘ └────┬─────┘
    │         │        │           │
    └─────────┴────────┴───────────┘
                │
                ▼
        ┌─────────────┐
        │ Reflection  │ ← 自我反思评估
        │   Agent     │
        └─────────────┘
```

### 智能体节点

| 节点 | 职责 | 触发条件 |
|------|------|----------|
| **RagNode** | 知识库检索 | 包含"制度""流程""政策""报销"等关键词 |
| **ChatNode** | 闲聊问答 | 日常对话，不涉及专业知识 |
| **ToolNode** | 工具调用 | 包含"天气""时间""计算"等关键词 |
| **FallbackNode** | 异常兜底 | 其他节点处理失败时 |

## 📝 配置说明

### 环境变量

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `DB_HOST` | 数据库主机 | localhost |
| `DB_PORT` | 数据库端口 | 3306 |
| `REDIS_HOST` | Redis 主机 | localhost |
| `REDIS_PORT` | Redis 端口 | 6379 |
| `CHROMA_PERSIST_DIRECTORY` | ChromaDB 存储目录 | chroma_db |
| `CONTEXT_MAX_HISTORY` | 最大对话历史数 | 50 |
| `LOG_LEVEL` | 日志级别 | INFO |

## 🔄 MCP 协议

项目实现了 MCP（Model Context Protocol）协议，用于标准化工具调用：

- **请求格式**：JSON-RPC 2.0 兼容
- **参数校验**：自动参数类型检查
- **错误处理**：标准化错误码

## 🔒 安全特性

- **JWT 认证**：基于 Token 的用户认证
- **输入验证**：防 SQL 注入、XSS 攻击
- **审计日志**：记录关键操作日志
- **连接池**：优化数据库连接管理

## 📊 知识库

知识库文件存放在 `data/` 目录下，支持 `.txt` 格式：


## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 📞 联系方式

如有问题或建议，请提交 Issue 或联系开发者。