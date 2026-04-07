# Local Skills Agent v2

<p align="center">
  <strong>🚀 A Feature-Rich Local AI Agent Platform</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#configuration">Configuration</a> •
  <a href="README.md">中文</a>
</p>

---

## Features

- 🔄 **Multi-turn Conversation** - Real-time WebSocket communication with streaming output and message persistence
- 🧠 **Three-Layer Memory System** - Working memory, short-term memory, and long-term memory powered by Milvus vector retrieval
- 📁 **File Upload + RAG** - Support for PDF/Word/Excel/CSV with intelligent chunking and retrieval
- 🔍 **Web Search** - Integrated Tavily/SerpAPI for real-time information
- 🧩 **Skill Management** - Git/ZIP installation, custom grouping, per-session skill selection
- 👤 **Multi-user Support** - JWT authentication with data isolation

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI + SQLAlchemy + AsyncPG |
| Frontend | React + Vite + TypeScript + Ant Design |
| Database | PostgreSQL + Milvus |
| LLM | Qwen / OpenAI / Local Models |
| Deployment | Docker Compose |

## Quick Start

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd local_skills_agent_v2
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

### 3. Start Infrastructure Services

```bash
docker-compose up -d
```

Wait for PostgreSQL and Milvus to be ready (about 30 seconds).

### 4. Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 5. Run Database Migrations

```bash
alembic upgrade head
```

### 6. Start the Backend

```bash
uvicorn main:app --reload --port 8000
```

### 7. Install Frontend Dependencies

```bash
cd ../frontend
npm install
```

### 8. Start the Frontend

```bash
npm run dev
```

### 9. Access the Application

Open your browser and navigate to http://localhost:5173

## Architecture

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
│ (Structured)│   │  (Vector)   │
└─────────────┘   └─────────────┘
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `LLM_BACKEND` | LLM backend (`anthropic` / `openai`) | ✅ |
| `DASHSCOPE_API_KEY` | Alibaba DashScope API Key | ✅ |
| `POSTGRES_PASSWORD` | PostgreSQL password | ✅ |
| `JWT_SECRET_KEY` | JWT secret key | ✅ |
| `TAVILY_API_KEY` | Tavily search API key | For web search |
| `MILVUS_HOST` | Milvus host address | ✅ |

### LLM Configuration

**Qwen (Recommended)**:
```env
LLM_BACKEND=anthropic
DASHSCOPE_API_KEY=sk-xxxx
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

**Local Model (Ollama)**:
```env
LLM_BACKEND=openai
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
OPENAI_MODEL=qwen2.5:14b
```

## Project Structure

```
local_skills_agent_v2/
├── docker-compose.yml      # Docker service configuration
├── .env                    # Environment variables
├── backend/                # FastAPI backend
│   ├── main.py
│   ├── requirements.txt
│   ├── alembic/            # Database migrations
│   └── app/
│       ├── models/         # ORM models
│       ├── routers/        # API routes
│       ├── services/       # Business logic
│       └── core/           # Core utilities
├── frontend/               # React frontend
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   └── stores/
│   └── package.json
└── skills/                 # Skill files storage
```

## API Documentation

After starting the backend, access:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development

### Backend Development

```bash
cd backend
uvicorn main:app --reload
```

### Frontend Development

```bash
cd frontend
npm run dev
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head
```

## License

MIT

## Contributing

Issues and Pull Requests are welcome!
