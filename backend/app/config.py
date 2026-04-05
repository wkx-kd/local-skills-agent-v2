from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path


class Settings(BaseSettings):
    # LLM
    LLM_BACKEND: str = "anthropic"
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    OPENAI_BASE_URL: str = "http://localhost:11434/v1"
    OPENAI_API_KEY: str = "ollama"
    OPENAI_MODEL: str = "qwen2.5:14b"

    # PostgreSQL
    POSTGRES_USER: str = "agent"
    POSTGRES_PASSWORD: str = "agent_secret"
    POSTGRES_DB: str = "agent_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Milvus
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530

    # Embedding
    EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_DIMENSION: int = 1024

    # Web Search
    SEARCH_PROVIDER: str = "duckduckgo"
    TAVILY_API_KEY: str = ""
    SERPAPI_API_KEY: str = ""

    # JWT
    JWT_SECRET_KEY: str = "your-super-secret-key-change-this"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # App
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # Paths
    PROJECT_DIR: Path = Path(__file__).resolve().parent.parent.parent
    SKILLS_DIR: Path = PROJECT_DIR / "skills"

    model_config = {"env_file": "../.env", "env_file_encoding": "utf-8"}


settings = Settings()
