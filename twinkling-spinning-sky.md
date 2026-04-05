# Local Skills Agent v2 - 前后端分离重构方案

## Context

当前项目是一个本地 AI Agent 框架，采用 Flask + 原生 HTML/JS 的单体架构，仅支持单轮对话、无持久化存储、无记忆系统、无文件上传和联网搜索能力。Skill 管理仅支持手动文件系统操作。

本次重构目标：迁移到前后端分离架构，并新增多轮对话、记忆系统、文件上传、Web 搜索、Skill 管理等核心功能，使其成为一个功能完整的多用户 AI Agent 平台。

---

## 技术选型总览

| 层 | 技术 | 说明 |
|---|---|---|
| 后端框架 | **FastAPI** | 异步、WebSocket、自动 API 文档 |
| 前端框架 | **React + Vite** | 组件化、TypeScript、快速构建 |
| 结构化存储 | **PostgreSQL** | 用户、会话、消息、Skill 配置 |
| 向量存储 | **Milvus** | 长期记忆、RAG 文件检索 |
| Embedding | **通义千问 text-embedding-v3** | 复用现有 DashScope API Key |
| 实时通信 | **WebSocket** | 双向流式对话 |
| 认证 | **JWT Token** | 无状态、适合前后端分离 |
| 部署 | **Docker Compose** | PostgreSQL + Milvus + 后端一键部署 |

---

## 项目目录结构

```
local_skills_agent_v2/
├── docker-compose.yml              # PostgreSQL + Milvus + Backend
├── .env.example
│
├── backend/                        # FastAPI 后端
│   ├── main.py                     # FastAPI 入口, CORS, 路由注册
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
│   │   │   ├── agent_service.py    # Agent 循环 (改造自 local_skills_agent.py)
│   │   │   ├── llm_client.py       # LLM 适配器 (改造自 llm_client.py)
│   │   │   ├── memory_service.py   # 三层记忆管理
│   │   │   ├── skill_manager.py    # Skill 加载/安装/删除 (改造自 SkillManager)
│   │   │   ├── file_service.py     # 文件解析 + RAG 分块
│   │   │   ├── embedding_service.py# Embedding 调用 (text-embedding-v3)
│   │   │   ├── search_service.py   # Web Search (Tavily/SerpAPI)
│   │   │   └── context_builder.py  # 上下文组装 (滑动窗口+摘要+记忆检索)
│   │   ├── core/                   # 核心工具
│   │   │   ├── security.py         # JWT 生成/验证, 密码哈希
│   │   │   ├── executor.py         # 代码执行沙箱 (改造自 LocalCodeExecutor)
│   │   │   └── websocket.py        # WebSocket 连接管理
│   │   └── tasks/                  # 后台任务
│   │       └── memory_cleanup.py   # 定期记忆整理 (去重/合并/衰减)
│   └── skills/                     # Skill 文件存储目录
│       ├── data-analysis/
│       ├── pdf/
│       ├── marketing-materials/
│       └── xhs-research/
│
├── frontend/                       # React + Vite 前端
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
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
│   │   │   ├── useWebSocket.ts     # WebSocket 连接管理
│   │   │   ├── useAuth.ts
│   │   │   └── useChat.ts
│   │   ├── stores/                 # 状态管理 (Zustand)
│   │   │   ├── authStore.ts
│   │   │   ├── chatStore.ts
│   │   │   └── skillStore.ts
│   │   ├── components/             # UI 组件
│   │   │   ├── Chat/
│   │   │   │   ├── ChatWindow.tsx      # 多轮对话主窗口
│   │   │   │   ├── MessageBubble.tsx   # 消息气泡 (文本/代码/工具调用)
│   │   │   │   ├── InputArea.tsx       # 输入区 (文本+文件上传)
│   │   │   │   └── ToolExecution.tsx   # 工具执行状态展示
│   │   │   ├── Sidebar/
│   │   │   │   ├── ConversationList.tsx
│   │   │   │   └── SkillPanel.tsx      # Skill 分组选择
│   │   │   ├── Skills/
│   │   │   │   ├── SkillStore.tsx      # Skill 商店/安装
│   │   │   │   ├── SkillManager.tsx    # 已安装 Skill 管理
│   │   │   │   └── SkillGroupEditor.tsx
│   │   │   ├── Auth/
│   │   │   │   ├── LoginForm.tsx
│   │   │   │   └── RegisterForm.tsx
│   │   │   └── common/
│   │   │       ├── FileUploader.tsx
│   │   │       └── MarkdownRenderer.tsx
│   │   ├── pages/
│   │   │   ├── ChatPage.tsx
│   │   │   ├── SkillsPage.tsx
│   │   │   ├── SettingsPage.tsx
│   │   │   └── LoginPage.tsx
│   │   └── types/                  # TypeScript 类型定义
│   │       ├── chat.ts
│   │       ├── skill.ts
│   │       └── user.ts
│   └── public/
│
└── legacy/                         # 旧代码备份 (重构完成后可删除)
    ├── local_skills_agent.py
    ├── web_app.py
    └── llm_client.py
```

---

## 功能实现方案

### 1. 多轮对话

**数据模型**:
```
conversations: id, user_id, title, skill_group_id, created_at, updated_at
messages: id, conversation_id, role(user/assistant/system/tool), content(JSONB), token_count, created_at
```

**WebSocket 协议**:
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

**流程**:
1. 用户通过 WebSocket 发送消息
2. 后端从 PostgreSQL 加载该会话历史消息
3. `context_builder` 组装上下文（滑动窗口 + 摘要 + 记忆检索 + 文件 RAG）
4. 调用 LLM，流式返回
5. Agent 循环执行工具调用，实时推送状态
6. 完成后将新消息持久化到 PostgreSQL

### 2. 记忆系统 (三层架构)

**第一层 - 工作记忆 (Working Memory)**:
- 存储位置：Python 内存 (per WebSocket connection)
- 内容：当前会话的完整 messages 列表
- 生命周期：WebSocket 连接断开时释放

**第二层 - 短期记忆 (Short-term Memory)**:
- 存储位置：PostgreSQL `memories` 表
- 内容：近期会话摘要、用户临时偏好、任务上下文
- 写入时机：每次会话结束时 LLM 自动提取
- 过期机制：30天未访问自动衰减权重，90天后归档
- 数据模型：
  ```
  memories: id, user_id, type(summary/preference/task), content, importance_score, 
            access_count, last_accessed_at, expires_at, created_at
  ```

**第三层 - 长期记忆 (Long-term Memory)**:
- 存储位置：Milvus (向量) + PostgreSQL (元数据)
- 内容：语义化的知识片段、结论、用户长期偏好
- 写入时机：**混合模式**
  - 实时：Agent 判断为重要信息时，通过 `save_memory` tool 主动存储
  - 异步：会话结束后后台提取关键信息
  - 定期：后台任务去重、合并相似记忆、衰减低频记忆
- 检索：每轮对话前，用当前问题 embedding 从 Milvus 检索 top-K 相关记忆

**新增 Agent Tool**:
```python
tools = [
    ...,  # 原有 5 个工具
    {"name": "web_search", "description": "搜索互联网获取最新信息", ...},
    {"name": "save_memory", "description": "将重要信息保存到长期记忆", ...},
    {"name": "recall_memory", "description": "检索长期记忆中的相关信息", ...},
]
```

### 3. 文件上传 + RAG

**上传流程**:
1. 前端通过 `POST /api/files/upload` 上传文件 (multipart/form-data)
2. 后端存储文件到 `uploads/{user_id}/` 目录
3. 文件解析（提取文本）：
   - PDF: `pdfplumber` / `pypdf`
   - Word: `python-docx`
   - Excel/CSV: `pandas`
   - 图片: `pytesseract` OCR 或 多模态 LLM 描述
   - 代码文件: 直接读取
4. 判断策略：
   - 文本 < 5000 tokens → 标记为 `full_text`，对话时全文注入
   - 文本 >= 5000 tokens → 分块 (chunk_size=512, overlap=50) → Embedding → 存入 Milvus
5. 元数据存入 PostgreSQL:
   ```
   uploaded_files: id, user_id, conversation_id, filename, file_type, file_size, 
                   storage_path, processing_status, chunk_count, created_at
   ```

**对话时检索**:
- 用户消息提及文件内容时，`context_builder` 从 Milvus 检索相关 chunks
- 注入到 messages 中作为 system context

### 4. Web Search

**实现为 Agent Tool**:
- 注册 `web_search` 工具到 Agent 的 tools 列表
- Agent 根据用户问题自主决定是否调用搜索
- 调用 Tavily/SerpAPI 获取结构化搜索结果
- 返回 top-5 结果摘要作为 tool_result

**配置**:
```env
SEARCH_PROVIDER=tavily          # tavily 或 serpapi
TAVILY_API_KEY=tvly-xxx
# 或
SERPAPI_API_KEY=xxx
```

**Tool 定义**:
```python
{
    "name": "web_search",
    "description": "搜索互联网获取实时信息。当用户询问最新事件、实时数据、或你不确定的事实时使用。",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "max_results": {"type": "integer", "default": 5}
        },
        "required": ["query"]
    }
}
```

### 5. Skill 管理系统

**数据模型**:
```
skills: id, name, description, version, source_type(local/git), source_url, 
        install_path, is_active, installed_by, created_at, updated_at

skill_groups: id, user_id, name, description, created_at
skill_group_members: skill_group_id, skill_id
```

**安装机制**:
- **Git 安装**: `POST /api/skills/install {"source": "git", "url": "https://github.com/user/skill-repo.git"}`
  - 后端 `git clone` 到 `skills/` 目录
  - 验证 SKILL.md 存在且格式正确
  - 注册到 PostgreSQL
- **本地上传**: `POST /api/skills/install` (multipart, zip 文件)
  - 解压到 `skills/` 目录
  - 同样验证 + 注册
- **卸载**: `DELETE /api/skills/{skill_id}`
  - 删除目录 + 数据库记录

**分组管理**:
- 用户可创建自定义 Skill 分组（如"数据分析"、"内容创作"、"研究调研"）
- 每个分组包含若干 Skill
- 创建会话时选择 Skill 分组 → 该会话只加载分组内的 Skill 到 system prompt
- 不选分组 = 加载所有已激活的 Skill

**API**:
```
POST   /api/skills/install          # 安装 Skill
DELETE /api/skills/{id}             # 卸载 Skill
GET    /api/skills                  # 列出所有 Skill
PUT    /api/skills/{id}/toggle      # 启用/禁用

POST   /api/skill-groups            # 创建分组
PUT    /api/skill-groups/{id}       # 更新分组 (名称/成员)
DELETE /api/skill-groups/{id}       # 删除分组
GET    /api/skill-groups            # 列出分组
```

---

## 上下文组装流程 (context_builder)

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

## 实施阶段

### Phase 1: 基础架构搭建
- Docker Compose 配置 (PostgreSQL + Milvus)
- FastAPI 项目骨架 + 数据库模型 + Alembic 迁移
- JWT 认证系统
- React + Vite 项目初始化 + 路由 + 认证页面

### Phase 2: 核心对话功能
- WebSocket 通信层
- Agent 循环改造 (从 local_skills_agent.py 迁移)
- 多轮会话管理 (CRUD + 消息持久化)
- 前端聊天界面 (对话列表 + 消息窗口 + 流式渲染)

### Phase 3: 记忆系统
- Embedding Service (text-embedding-v3)
- 三层记忆实现 (工作/短期/长期)
- context_builder 上下文组装
- 滑动窗口 + 摘要截断
- 后台记忆清理任务

### Phase 4: 文件上传 + RAG
- 文件上传 API + 前端组件
- 文件解析 (PDF/Word/Excel/图片)
- 分块 + Embedding + Milvus 存储
- RAG 检索集成到 context_builder

### Phase 5: Web Search
- search_service 实现 (Tavily/SerpAPI)
- 注册为 Agent Tool
- 前端搜索结果展示

### Phase 6: Skill 管理
- Skill CRUD API + 数据库模型
- Git clone / ZIP 上传安装
- Skill 分组管理
- 前端 Skill 管理界面 + 会话时分组选择

---

## 关键文件迁移映射

| 旧文件 | 新位置 | 改造要点 |
|--------|--------|----------|
| `local_skills_agent.py` (agent_loop) | `backend/app/services/agent_service.py` | 改为 async，支持 WebSocket 推送，集成 context_builder |
| `local_skills_agent.py` (SkillManager) | `backend/app/services/skill_manager.py` | 增加数据库注册、分组过滤、安装/卸载 |
| `local_skills_agent.py` (LocalCodeExecutor) | `backend/app/core/executor.py` | 基本不变，增加异步包装 |
| `local_skills_agent.py` (dispatch_tool) | `backend/app/services/agent_service.py` | 增加 web_search/save_memory/recall_memory 工具 |
| `llm_client.py` | `backend/app/services/llm_client.py` | 增加流式响应支持 (stream=True) |
| `web_app.py` | `backend/main.py` + routers | 拆分为 RESTful API + WebSocket |
| `frontend/index.html` | `frontend/src/` | 完全重写为 React 组件 |

---

## 验证方案

1. **基础架构**: `docker-compose up` 启动所有服务，访问 FastAPI Swagger 文档
2. **认证**: 注册 → 登录 → 获取 JWT → 携带 token 访问 API
3. **多轮对话**: WebSocket 连接 → 发送多条消息 → 验证历史上下文保持
4. **记忆系统**: 对话中提到偏好 → 新会话中验证记忆被召回
5. **文件上传**: 上传 PDF → 对话中提问文件内容 → 验证 RAG 检索正确
6. **Web Search**: 提问时事问题 → 验证 Agent 自动调用搜索 → 返回最新信息
7. **Skill 管理**: 安装新 Skill → 创建分组 → 新会话选择分组 → 验证只加载分组内 Skill
