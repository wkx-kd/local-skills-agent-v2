import json
import uuid
from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.database import async_session
from app.models.conversation import Conversation
from app.models.skill_group import SkillGroup
from app.core.security import decode_token
from app.services.agent_service import AgentRunner
from app.services.skill_manager import SkillManager

router = APIRouter()

# 全局 SkillManager 实例（启动时扫描一次）
_skill_manager: SkillManager | None = None


def get_skill_manager() -> SkillManager:
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
    return _skill_manager


# 活跃的 AgentRunner 实例，用于支持 stop 命令
_active_runners: Dict[str, AgentRunner] = {}


async def authenticate_ws(websocket: WebSocket) -> uuid.UUID | None:
    """从 WebSocket 查询参数中验证 JWT token"""
    token = websocket.query_params.get("token")
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return uuid.UUID(payload["sub"])
    except Exception:
        return None


async def get_skill_names_for_group(db, group_id: str | None) -> list[str] | None:
    """获取指定分组下的 skill 名称列表"""
    if not group_id:
        return None
    result = await db.execute(select(SkillGroup).where(SkillGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        return None
    return [s.name for s in group.skills]


@router.websocket("/ws/{conversation_id}")
async def chat_websocket(websocket: WebSocket, conversation_id: uuid.UUID):
    user_id = await authenticate_ws(websocket)
    if not user_id:
        await websocket.close(code=4001, reason="认证失败")
        return

    await websocket.accept()

    # 验证会话归属并获取信息
    async with async_session() as db:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            await websocket.send_json({"type": "error", "detail": "会话不存在"})
            await websocket.close(code=4004)
            return

        model = conv.model
        skill_group_id = str(conv.skill_group_id) if conv.skill_group_id else None
        skill_names = await get_skill_names_for_group(db, skill_group_id)

    skill_manager = get_skill_manager()
    connection_id = str(uuid.uuid4())

    async def send_callback(data: dict):
        """将消息发送到 WebSocket"""
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "message":
                content = data.get("content", "")
                file_ids = data.get("files", [])
                web_search = data.get("web_search", False)

                # 创建 AgentRunner
                async with async_session() as db:
                    runner = AgentRunner(
                        db=db,
                        conversation_id=str(conversation_id),
                        user_id=str(user_id),
                        model=model,
                        skill_manager=skill_manager,
                        send_callback=send_callback,
                        skill_names=skill_names,
                        enable_web_search=web_search,
                    )
                    _active_runners[connection_id] = runner

                    try:
                        await runner.run(content, file_ids)
                        await db.commit()
                    except Exception:
                        await db.rollback()
                        raise
                    finally:
                        _active_runners.pop(connection_id, None)

            elif msg_type == "stop":
                runner = _active_runners.get(connection_id)
                if runner:
                    await runner.cancel()

    except WebSocketDisconnect:
        runner = _active_runners.pop(connection_id, None)
        if runner:
            await runner.cancel()
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "detail": str(e)})
        except Exception:
            pass