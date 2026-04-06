#!/bin/bash
set -e

echo "[Entrypoint] Waiting for PostgreSQL..."
until python -c "
import asyncio, asyncpg, os
async def check():
    await asyncpg.connect(
        host=os.getenv('POSTGRES_HOST','postgres'),
        port=int(os.getenv('POSTGRES_PORT','5432')),
        user=os.getenv('POSTGRES_USER','agent'),
        password=os.getenv('POSTGRES_PASSWORD','agent_secret'),
        database=os.getenv('POSTGRES_DB','agent_db'),
    )
asyncio.run(check())
" 2>/dev/null; do
    echo "[Entrypoint] PostgreSQL not ready, retrying in 3s..."
    sleep 3
done
echo "[Entrypoint] PostgreSQL is ready."

echo "[Entrypoint] Running database migrations..."
alembic upgrade head

echo "[Entrypoint] Starting application..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
