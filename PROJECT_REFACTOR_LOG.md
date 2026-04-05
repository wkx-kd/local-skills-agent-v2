# Local Skills Agent v2 重构项目 - 完整会话记录

## 项目概述

**原始项目**：一个本地 AI Agent 框架，采用 Flask + 原生 HTML/JS 的单体架构，仅支持单轮对话、无持久化存储、无记忆系统。

**重构目标**：迁移到前后端分离架构，新增多轮对话、记忆系统、文件上传、Web 搜索、Skill 管理等核心功能。

---

## 技术选型决策

经过讨论确认的技术栈：

| 层 | 技术选型 | 说明 |
|---|---|---|
| 后端框架 | **FastAPI** | 异步、WebSocket、自动 API 文档 |
| 前端框架 | **React + Vite + TypeScript** | 组件化、快速构建 |
| 结构化存储 | **PostgreSQL** | 用户、会话、消息、Skill 配置 |
| 向量存储 | **Milvus** | 长期记忆、RAG 文件检索 |
| Embedding | **通义千问 text-embedding-v3** | 复用现有 DashScope API Key |
| 实时通信 | **WebSocket** | 双向流式对话 |
| 认证 | **JWT Token** | 无状态、适合前后端分离 |
| 部署 | **Docker Compose** | PostgreSQL + Milvus + etcd + MinIO 一键部署 |

---

## 功能实现方案

### 1. 多轮对话

**数据模型**：
```
conversations: id, user_id, title, skill_group_id, created_at, updated_at
messages: id, conversation_id, role(user/assistant/system/tool), content(JSONB), token_count, created_at
```

**WebSocket 协议**：
```
Client → Server:
  { type: "message", content: "用户输入", files: ["file_id_1"] }
  { type: "stop" }  // 中断生成

Server → Client:
  { type: "text_delta", content: "流式文本片段" }
  { type: "tool_call", name: "execute_python", input: {...} }
  { type: "tool_result", tool_use_id: "...", output: "..." }
  { type: "done", message_id: "..." }
  { type: "error", detail: "..." }
```

### 2. 记忆系统 (三层架构)

| 层级 | 存储 | 生命周期 | 用途 |
|------|------|----------|------|
| **工作记忆** | Python 内存 | WebSocket 连接期间 | 当前对话的完整 messages 列表 |
| **短期记忆** | PostgreSQL | 跨会话，30 天过期 | 近期会话摘要、用户临时偏好、任务上下文 |
| **长期记忆** | Milvus + PostgreSQL | 永久 | 语义化的知识片段、结论、用户长期偏好 |

**写入策略（混合模式）**：
- 实时：Agent 判断为重要信息时，通过 `save_memory` tool 主动存储
- 异步：会话结束后后台提取关键信息
- 定期：后台任务去重、合并相似记忆、衰减低频记忆

**新增 Agent Tool**：
```python
save_memory(category: "preference"|"knowledge"|"fact"|"task", content: str, importance: float)
recall_memory(query: str, top_k: int = 5)
```

### 3. 文件上传 + RAG

**处理策略**：
| 文件大小 | 策略 | 处理方式 |
|----------|------|----------|
| < 20000 字符 (~5000 tokens) | `full_text` | 全文存储到 PostgreSQL，对话时直接注入 |
| >= 20000 字符 | `rag` | 分块 → Embedding → 存入 Milvus，对话时检索相关 chunks |

**支持的文件格式**：
- PDF: pdfplumber
- Word (.docx): python-docx
- Excel (.xlsx/.xls): pandas
- CSV: pandas
- 文本/代码: 直接读取

### 4. Web Search

**支持两种搜索提供商**：

| 提供商 | 特点 | 配置 |
|--------|------|------|
| **Tavily** | 专为 AI 设计，返回结构化结果 | `SEARCH_PROVIDER=tavily` + `TAVILY_API_KEY` |
| **SerpAPI** | Google 搜索结果 | `SEARCH_PROVIDER=serpapi` + `SERPAPI_API_KEY` |

**工具定义**：
```python
web_search(query: str, max_results: int = 5)
```

### 5. Skill 管理系统

**安装方式**：
| 方式 | API | 说明 |
|------|-----|------|
| Git clone | `POST /api/skills/install/git` | 输入 Git URL，自动克隆到 skills/ 目录 |
| ZIP 上传 | `POST /api/skills/install/upload` | 上传 ZIP 文件，自动解压到 skills/ 目录 |

**分组管理**：
- 用户可创建自定义 Skill 分组（如"数据分析"、"内容创作"、"研究调研"）
- 创建会话时选择 Skill 分组 → 该会话只加载分组内的 Skill 到 system prompt
- 不选分组 = 加载所有已激活的 Skill

---

## 项目目录结构

```
local_skills_agent_v2/
├── docker-compose.yml              # PostgreSQL + Milvus + etcd + MinIO
├── .env.example
│
├── backend/                        # FastAPI 后端
│   ├── main.py                     # FastAPI 入口
│   ├── requirements.txt
│   ├── alembic/                    # 数据库迁移
│   │   └── versions/
│   ├── app/
│   │   ├── config.py               # 环境变量, 配置管理
│   │   ├── database.py             # PostgreSQL 连接, SQLAlchemy
│   │   ├── models/                 # SQLAlchemy ORM 模型
│   │   │   ├── user.py             # 用户表
│   │   │   ├── conversation.py     # 会话表
│   │   │   ├── message.py          # 消息表
│   │   │   ├── memory.py           # 记忆表 (短期+长期元数据)
│   │   │   ├── skill.py            # Skill 元数据表
│   │   │   ├── skill_group.py      # Skill 分组表
│   │   │   └── uploaded_file.py    # 上传文件元数据表
│   │   ├── schemas/                # Pydantic 请求/响应模型
│   │   │   ├── auth.py
│   │   │   ├── conversation.py
│   │   │   ├── message.py
│   │   │   ├── skill.py
│   │   │   └── file.py
│   │   ├── routers/                # API 路由
│   │   │   ├── auth.py             # 注册/登录/刷新token
│   │   │   ├── conversations.py    # 会话 CRUD
│   │   │   ├── chat.py             # WebSocket 多轮对话
│   │   │   ├── skills.py           # Skill 安装/删除/分组管理
│   │   │   ├── files.py            # 文件上传/下载
│   │   │   └── memory.py           # 记忆查看/管理
│   │   ├── services/               # 业务逻辑层
│   │   │   ├── agent_service.py    # Agent 循环 + WebSocket 推送
│   │   │   ├── llm_client.py       # LLM 适配器 (Anthropic/OpenAI)
│   │   │   ├── memory_service.py   # 三层记忆管理
│   │   │   ├── skill_manager.py    # Skill 加载/构建 system prompt
│   │   │   ├── skill_installer.py  # Skill 安装 (Git/ZIP)
│   │   │   ├── file_parser.py      # 多格式文件解析
│   │   │   ├── rag_service.py      # RAG 分块 + 检索
│   │   │   ├── embedding_service.py# Embedding (text-embedding-v3)
│   │   │   ├── milvus_client.py    # Milvus 连接和操作
│   │   │   ├── search_service.py   # Web Search (Tavily/SerpAPI)
│   │   │   └── context_builder.py  # 上下文组装
│   │   ├── core/                   # 核心工具
│   │   │   ├── security.py         # JWT 生成/验证, 密码哈希
│   │   │   └── executor.py         # 代码执行沙箱
│   │   └── tasks/                  # 后台任务
│   │       └── memory_cleanup.py   # 定期记忆整理
│   └── skills/                     # Skill 文件存储目录
│       ├── data-analysis/
│       ├── pdf/
│       ├── marketing-materials/
│       └── xhs-research/
│
├── frontend/                       # React + Vite 前端
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/                    # API 调用封装
│   │   │   ├── client.ts           # Axios 实例, JWT 拦截器
│   │   │   ├── auth.ts
│   │   │   ├── conversations.ts
│   │   │   ├── skills.ts
│   │   │   └── files.ts
│   │   ├── hooks/                  # 自定义 Hooks
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useAuth.ts
│   │   │   └── useChat.ts
│   │   ├── stores/                 # Zustand 状态管理
│   │   │   ├── authStore.ts
│   │   │   ├── chatStore.ts
│   │   │   └── skillStore.ts
│   │   ├── components/             # UI 组件
│   │   │   ├── Chat/
│   │   │   │   ├── ChatWindow.tsx
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   └── InputArea.tsx
│   │   │   ├── Sidebar/
│   │   │   │   ├── ConversationList.tsx
│   │   │   │   └── SkillPanel.tsx
│   │   │   ├── Skills/
│   │   │   │   └── SkillsPage.tsx
│   │   │   └── Auth/
│   │   │       ├── LoginForm.tsx
│   │   │       └── RegisterForm.tsx
│   │   ├── pages/
│   │   │   ├── ChatPage.tsx
│   │   │   ├── SkillsPage.tsx
│   │   │   └── LoginPage.tsx
│   │   └── types/                  # TypeScript 类型定义
│   │       ├── chat.ts
│   │       ├── skill.ts
│   │       └── user.ts
│   └── public/
│
└── legacy/                         # 旧代码备份
    ├── local_skills_agent.py
    ├── web_app.py
    └── llm_client.py
```

---

## 实施阶段记录

### Phase 1: 基础架构搭建 ✅

**创建内容**：
- `docker-compose.yml` (PostgreSQL 16 + Milvus 2.4 + etcd + MinIO)
- FastAPI 项目骨架 + 数据库模型 + Alembic 迁移
- JWT 认证系统
- React + Vite 前端初始化 + 路由 + 认证页面

### Phase 2: 核心对话功能 ✅

**创建内容**：
- `agent_service.py` - 核心 Agent 循环
- `llm_client.py` - LLM 适配器（流式支持）
- `executor.py` - 代码执行沙箱
- `skill_manager.py` - Skill 管理
- `context_builder.py` - 上下文组装
- `chat.py` - WebSocket 路由

### Phase 3: 记忆系统 ✅

**创建内容**：
- `embedding_service.py` - Embedding 服务
- `milvus_client.py` - Milvus 客户端
- `memory_service.py` - 三层记忆管理
- `memory_cleanup.py` - 后台清理任务

### Phase 4: 文件上传 + RAG ✅

**创建内容**：
- `file_parser.py` - 多格式文件解析
- `rag_service.py` - RAG 分块和检索
- 更新 `context_builder.py` - 集成 RAG
- 更新 `files.py` - 异步文件处理

### Phase 5: Web Search ✅

**创建内容**：
- `search_service.py` - Tavily/SerpAPI 集成
- 更新 `agent_service.py` - web_search 工具实现

### Phase 6: Skill 管理 ✅

**创建内容**：
- `skill_installer.py` - Git/ZIP 安装
- 完善 `skills.py` 路由
- 前端 Skill 管理界面

---

## 上下文组装流程

每轮对话的上下文按以下顺序组装：

```
1. System Prompt
   ├── 基础人设指令
   ├── 当前 Skill 分组的 Skill 元数据
   └── 用户短期记忆摘要 (最近的偏好/上下文)

2. 长期记忆检索结果 (来自 Milvus, top-5 相关片段)

3. 文件 RAG 检索结果 (如果用户上传了文件)

4. 历史消息 (滑动窗口)
   ├── 早期消息的摘要 (压缩后约 500 tokens)
   └── 最近 N 轮完整消息

5. 当前用户消息
   ├── 用户文本
   └── 小文件全文 (< 5000 tokens 的附件)
```

**Token 预算分配** (以 128K 模型为例):

| 部分 | 预算 |
|------|------|
| System Prompt + Skills | ~4000 tokens |
| 记忆 + RAG 上下文 | ~8000 tokens |
| 历史摘要 | ~2000 tokens |
| 最近消息 (滑动窗口) | ~80000 tokens |
| 当前轮输入 | ~10000 tokens |
| 预留给模型输出 | ~24000 tokens |

---

## Agent 工具列表

```python
TOOLS = [
    "read_file",        # 读取本地文件
    "write_file",       # 写入文件
    "execute_python",   # 执行 Python 代码
    "execute_bash",     # 执行 Bash 命令
    "list_directory",   # 列出目录内容
    "web_search",       # 搜索互联网
    "save_memory",      # 保存到长期记忆
    "recall_memory",    # 检索长期记忆
]
```

---

## 环境变量配置

```env
# .env.example

# ─── LLM 后端 ────────────────────────────────
LLM_BACKEND=anthropic
DASHSCOPE_API_KEY=sk-xxxxxxxx
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# ─── PostgreSQL ──────────────────────────────
POSTGRES_USER=agent
POSTGRES_PASSWORD=agent_secret
POSTGRES_DB=agent_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# ─── Milvus ──────────────────────────────────
MILVUS_HOST=localhost
MILVUS_PORT=19530

# ─── Embedding ───────────────────────────────
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_DIMENSION=1024

# ─── Web Search ──────────────────────────────
SEARCH_PROVIDER=tavily
TAVILY_API_KEY=tvly-xxxxxxxx

# ─── JWT 认证 ────────────────────────────────
JWT_SECRET_KEY=your-super-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ─── 应用配置 ────────────────────────────────
APP_HOST=0.0.0.0
APP_PORT=8000
CORS_ORIGINS=["http://localhost:5173"]
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE_MB=50
```

---

## 启动方式

```bash
# 1. 复制环境变量配置
cp .env.example .env
# 编辑 .env 填入真实的 API Key

# 2. 启动基础服务 (PostgreSQL + Milvus)
docker-compose up -d

# 3. 安装后端依赖
cd backend
pip install -r requirements.txt

# 4. 运行数据库迁移
alembic upgrade head

# 5. 启动后端
uvicorn main:app --reload --port 8000

# 6. 安装前端依赖
cd ../frontend
npm install

# 7. 启动前端开发服务器
npm run dev

# 8. 访问应用
open http://localhost:5173
```

---

## 验证方案

1. **基础架构**: `docker-compose up` 启动所有服务，访问 FastAPI Swagger 文档 `/docs`
2. **认证**: 注册 → 登录 → 获取 JWT → 携带 token 访问 API
3. **多轮对话**: WebSocket 连接 → 发送多条消息 → 验证历史上下文保持
4. **记忆系统**: 对话中提到偏好 → 新会话中验证记忆被召回
5. **文件上传**: 上传 PDF → 对话中提问文件内容 → 验证 RAG 检索正确
6. **Web Search**: 提问时事问题 → 验证 Agent 自动调用搜索 → 返回最新信息
7. **Skill 管理**: 安装新 Skill → 创建分组 → 新会话选择分组 → 验证只加载分组内 Skill

---

## 关键文件迁移映射

| 旧文件 | 新位置 | 改造要点 |
|--------|--------|----------|
| `local_skills_agent.py` (agent_loop) | `backend/app/services/agent_service.py` | 改为 async，支持 WebSocket 推送，集成 context_builder |
| `local_skills_agent.py` (SkillManager) | `backend/app/services/skill_manager.py` | 增加数据库注册、分组过滤、安装/卸载 |
| `local_skills_agent.py` (LocalCodeExecutor) | `backend/app/core/executor.py` | 增加异步包装 |
| `llm_client.py` | `backend/app/services/llm_client.py` | 增加流式响应支持 (stream=True) |
| `web_app.py` | `backend/main.py` + routers | 拆分为 RESTful API + WebSocket |
| `frontend/index.html` | `frontend/src/` | 完全重写为 React 组件 |

---

## 项目状态

| Phase | 功能 | 状态 |
|-------|------|------|
| Phase 1 | 基础架构搭建 | ✅ 完成 |
| Phase 2 | 核心对话功能 | ✅ 完成 |
| Phase 3 | 记忆系统 | ✅ 完成 |
| Phase 4 | 文件上传 + RAG | ✅ 完成 |
| Phase 5 | Web Search | ✅ 完成 |
| Phase 6 | Skill 管理 | ✅ 完成 |

**项目重构完成！**