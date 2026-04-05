# Local Skills Agent v2

<p align="center">
  <strong>🚀 一个功能完整的本地 AI Agent 平台</strong>
</p>

<p align="center">
  <a href="#特性">特性</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#架构">架构</a> •
  <a href="#配置">配置</a> •
  <a href="README_EN.md">English</a>
</p>

---

## 特性

- 🔄 **多轮对话** - WebSocket 实时通信，支持流式输出和历史消息持久化
- 🧠 **三层记忆系统** - 工作记忆、短期记忆、长期记忆，基于 Milvus 向量检索
- 📁 **文件上传 + RAG** - 支持 PDF/Word/Excel/CSV 等多格式文件，智能分块检索
- 🔍 **Web 搜索** - 集成 Tavily/SerpAPI，让 Agent 获取实时信息
- 🧩 **Skill 管理** - Git/ZIP 安装，自定义分组，会话级 Skill 选择
- 👤 **多用户支持** - JWT 认证，数据隔离

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI + SQLAlchemy + AsyncPG |
| 前端 | React + Vite + TypeScript + Ant Design |
| 数据库 | PostgreSQL + Milvus |
| LLM | 通义千问 / OpenAI / 本地模型 |
| 部署 | Docker Compose |

## 快速开始

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd local_skills_agent_v2
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

### 3. 启动基础服务

```bash
docker-compose up -d
```

等待 PostgreSQL 和 Milvus 启动完成（约 30 秒）。

### 4. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 5. 运行数据库迁移

```bash
alembic upgrade head
```

### 6. 启动后端

```bash
uvicorn main:app --reload --port 8000
```

### 7. 安装前端依赖

```bash
cd ../frontend
npm install
```

### 8. 启动前端

```bash
npm run dev
```

### 9. 访问应用

打开浏览器访问 http://localhost:5173

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐ │
│  │  Chat   │  │  Skills │  │  Files  │  │  Conversation   │ │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────────┬────────┘ │
└───────┼────────────┼────────────┼────────────────┼──────────┘
        │            │            │                │
        │ WebSocket  │ REST API   │ REST API       │ REST API
        ▼            ▼            ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│                     Backend (FastAPI)                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    Agent Service                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐  │   │
│  │  │ LLM Client  │  │   Tools     │  │ Context Builder│  │   │
│  │  └─────────────┘  └─────────────┘  └───────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐  │
│  │  Memory    │  │    RAG     │  │     Skill Manager      │  │
│  │  Service   │  │  Service   │  │                        │  │
│  └─────┬──────┘  └─────┬──────┘  └────────────────────────┘  │
└────────┼───────────────┼──────────────────────────────────────┘
         │               │
         ▼               ▼
┌─────────────┐   ┌─────────────┐
│ PostgreSQL  │   │   Milvus    │
│  (结构化)   │   │  (向量)     │
└─────────────┘   └─────────────┘
```

## 配置

### 环境变量

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `LLM_BACKEND` | LLM 后端 (`anthropic` / `openai`) | ✅ |
| `DASHSCOPE_API_KEY` | 阿里云 DashScope API Key | ✅ |
| `POSTGRES_PASSWORD` | PostgreSQL 密码 | ✅ |
| `JWT_SECRET_KEY` | JWT 密钥 | ✅ |
| `TAVILY_API_KEY` | Tavily 搜索 API Key | 搜索功能需要 |
| `MILVUS_HOST` | Milvus 地址 | ✅ |

### LLM 配置

**通义千问 (推荐)**:
```env
LLM_BACKEND=anthropic
DASHSCOPE_API_KEY=sk-xxxx
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

**本地模型 (Ollama)**:
```env
LLM_BACKEND=openai
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
OPENAI_MODEL=qwen2.5:14b
```

## 目录结构

```
local_skills_agent_v2/
├── docker-compose.yml      # Docker 服务配置
├── .env                    # 环境变量
├── backend/                # FastAPI 后端
│   ├── main.py
│   ├── requirements.txt
│   ├── alembic/            # 数据库迁移
│   └── app/
│       ├── models/         # ORM 模型
│       ├── routers/        # API 路由
│       ├── services/       # 业务逻辑
│       └── core/           # 核心工具
├── frontend/               # React 前端
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   └── stores/
│   └── package.json
└── skills/                 # Skill 文件存储
```

## API 文档

启动后端后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 开发

### 后端开发

```bash
cd backend
uvicorn main:app --reload
```

### 前端开发

```bash
cd frontend
npm run dev
```

### 数据库迁移

```bash
# 创建迁移
alembic revision --autogenerate -m "description"

# 执行迁移
alembic upgrade head
```

## License

MIT

## 贡献

欢迎提交 Issue 和 Pull Request！