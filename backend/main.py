from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, conversations, chat, skills, files, memory


async def init_skills_on_startup():
    """
    启动时扫描 skills 目录，将现有的 Skill 注册到数据库。
    """
    from app.database import async_session
    from app.services.skill_installer import SkillInstaller

    async with async_session() as db:
        installer = SkillInstaller(db)
        await installer.refresh_skills()
        print("[Startup] Skills initialized from filesystem")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.tasks.memory_cleanup import start_scheduler, stop_scheduler

    # 初始化 Skills（从文件系统扫描并注册到数据库）
    await init_skills_on_startup()

    # 启动后台任务调度器
    start_scheduler()

    yield

    # Shutdown
    stop_scheduler()


app = FastAPI(
    title="Local Skills Agent",
    description="AI Agent 平台 - 支持多轮对话、记忆系统、文件上传、Web搜索、Skill管理",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["会话"])
app.include_router(chat.router, prefix="/api/chat", tags=["对话"])
app.include_router(skills.router, prefix="/api/skills", tags=["Skill管理"])
app.include_router(files.router, prefix="/api/files", tags=["文件"])
app.include_router(memory.router, prefix="/api/memory", tags=["记忆"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True)