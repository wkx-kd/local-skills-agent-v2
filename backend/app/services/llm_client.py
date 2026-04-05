"""
LLM 后端适配层 — 异步版本，支持流式和非流式

通过 settings.LLM_BACKEND 切换后端：
  anthropic（默认）— 使用 Anthropic SDK，对接 DashScope / Claude ���版
  openai            — 使用 OpenAI SDK，��接 Ollama / vLLM / LM Studio 等本地模型

统一接口：
  create_message(...)     -> LLMResponse       非流式
  create_message_stream(...)  -> AsyncGenerator  流式 (yield TextDelta / ToolUseBlock / Done)
"""

import json
import asyncio
from typing import AsyncGenerator
from dataclasses import dataclass, field

from app.config import settings


# ─── 统一数据结构 ──────────────────────────────────────────────────────────


@dataclass
class TextBlock:
    type: str = "text"
    text: str = ""


@dataclass
class ToolUseBlock:
    type: str = "tool_use"
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    content: list = field(default_factory=list)  # list[TextBlock | ToolUseBlock]
    stop_reason: str = "end_turn"


# 流式事件
@dataclass
class StreamEvent:
    """流式响应事件"""
    event_type: str = ""  # text_delta, tool_use_start, tool_use_delta, tool_use_end, done
    text: str = ""
    tool_id: str = ""
    tool_name: str = ""
    tool_input_json: str = ""  # 工具输入的 JSON 字符串（逐步拼接）
    stop_reason: str = ""


def content_to_history(content: list) -> list:
    """将 LLMResponse.content 转为 dict 列表，供追加到 messages 历史"""
    result = []
    for block in content:
        if isinstance(block, TextBlock):
            result.append({"type": "text", "text": block.text})
        elif isinstance(block, ToolUseBlock):
            result.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
    return result


# ─── Anthropic 后端 ──────────────────────────────────────────────────────────


def _create_anthropic_client():
    import anthropic
    return anthropic.Anthropic(
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.DASHSCOPE_BASE_URL,
        timeout=anthropic.Timeout(connect=10.0, read=120.0, write=10.0, pool=5.0),
    )


async def _anthropic_create_message(
    model: str, max_tokens: int, system: str, messages: list, tools: list,
) -> LLMResponse:
    """Anthropic 非流式调用（在线程池中运行同步 SDK）"""
    client = _create_anthropic_client()

    def _call():
        import anthropic as _anth
        for attempt in range(3):
            try:
                resp = client.messages.create(
                    model=model, max_tokens=max_tokens, system=system,
                    messages=messages, tools=tools,
                )
                content = []
                for block in resp.content:
                    if hasattr(block, "text"):
                        content.append(TextBlock(text=block.text))
                    elif block.type == "tool_use":
                        content.append(ToolUseBlock(id=block.id, name=block.name, input=block.input))
                return LLMResponse(content=content, stop_reason=resp.stop_reason)
            except (_anth.RateLimitError, _anth.InternalServerError):
                if attempt < 2:
                    import time
                    time.sleep(30)
                else:
                    raise

    return await asyncio.to_thread(_call)


async def _anthropic_stream_message(
    model: str, max_tokens: int, system: str, messages: list, tools: list,
) -> AsyncGenerator[StreamEvent, None]:
    """Anthropic 流式调用"""
    client = _create_anthropic_client()

    def _stream():
        with client.messages.stream(
            model=model, max_tokens=max_tokens, system=system,
            messages=messages, tools=tools,
        ) as stream:
            for event in stream:
                yield event
            # 最终响应
            yield stream.get_final_message()

    # 在线程中运行同步 stream，通过队列转发到异步
    import queue
    q: queue.Queue = queue.Queue()
    sentinel = object()

    def _run():
        try:
            current_tool_input = ""
            for event in _stream():
                event_type = getattr(event, "type", None)

                if event_type == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        q.put(StreamEvent(
                            event_type="tool_use_start",
                            tool_id=block.id,
                            tool_name=block.name,
                        ))
                        current_tool_input = ""

                elif event_type == "content_block_delta":
                    delta = event.delta
                    if hasattr(delta, "text"):
                        q.put(StreamEvent(event_type="text_delta", text=delta.text))
                    elif hasattr(delta, "partial_json"):
                        current_tool_input += delta.partial_json
                        q.put(StreamEvent(
                            event_type="tool_use_delta",
                            tool_input_json=current_tool_input,
                        ))

                elif event_type == "content_block_stop":
                    pass

                elif event_type == "message_stop":
                    pass

                # 最终消息对象（从 get_final_message）
                elif hasattr(event, "stop_reason"):
                    q.put(StreamEvent(
                        event_type="done",
                        stop_reason=event.stop_reason,
                    ))
        except Exception as e:
            q.put(e)
        finally:
            q.put(sentinel)

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _run)

    while True:
        try:
            item = await asyncio.to_thread(q.get, timeout=120)
        except Exception:
            break
        if item is sentinel:
            break
        if isinstance(item, Exception):
            raise item
        yield item


# ─── OpenAI 兼容后端 ─────────��───────────────────────────────────────────────


def _create_openai_client():
    from openai import OpenAI
    return OpenAI(
        base_url=settings.OPENAI_BASE_URL,
        api_key=settings.OPENAI_API_KEY,
        timeout=120.0,
    )


def _convert_tools_openai(tools: list) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


def _get_block_attr(block, attr: str, default=None):
    if isinstance(block, dict):
        return block.get(attr, default)
    return getattr(block, attr, default)


def _convert_messages_openai(system: str, messages: list) -> list:
    result = [{"role": "system", "content": system}]
    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "user":
            if isinstance(content, str):
                result.append({"role": "user", "content": content})
            elif isinstance(content, list):
                user_texts = []
                for item in content:
                    item_type = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)
                    if item_type == "tool_result":
                        result.append({
                            "role": "tool",
                            "tool_call_id": _get_block_attr(item, "tool_use_id"),
                            "content": _get_block_attr(item, "content", ""),
                        })
                    elif item_type == "text":
                        user_texts.append(_get_block_attr(item, "text", ""))
                if user_texts:
                    result.append({"role": "user", "content": " ".join(user_texts)})

        elif role == "assistant":
            if isinstance(content, str):
                result.append({"role": "assistant", "content": content})
            elif isinstance(content, list):
                text_parts = []
                tool_calls = []
                for block in content:
                    b_type = _get_block_attr(block, "type")
                    if b_type == "text":
                        text_parts.append(_get_block_attr(block, "text", ""))
                    elif b_type == "tool_use":
                        tool_calls.append({
                            "id": _get_block_attr(block, "id"),
                            "type": "function",
                            "function": {
                                "name": _get_block_attr(block, "name"),
                                "arguments": json.dumps(_get_block_attr(block, "input", {})),
                            },
                        })
                msg_obj = {"role": "assistant", "content": " ".join(text_parts) or None}
                if tool_calls:
                    msg_obj["tool_calls"] = tool_calls
                result.append(msg_obj)

    return result


async def _openai_create_message(
    model: str, max_tokens: int, system: str, messages: list, tools: list,
) -> LLMResponse:
    client = _create_openai_client()

    def _call():
        from openai import RateLimitError
        oai_messages = _convert_messages_openai(system, messages)
        oai_tools = _convert_tools_openai(tools)

        for attempt in range(3):
            try:
                resp = client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    max_tokens=max_tokens,
                    messages=oai_messages,
                    tools=oai_tools,
                    tool_choice="auto",
                )
                choice = resp.choices[0]
                msg = choice.message
                content = []
                if msg.content:
                    content.append(TextBlock(text=msg.content))
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        content.append(ToolUseBlock(
                            id=tc.id, name=tc.function.name,
                            input=json.loads(tc.function.arguments),
                        ))
                stop_reason = "end_turn" if choice.finish_reason == "stop" else "tool_use"
                return LLMResponse(content=content, stop_reason=stop_reason)
            except RateLimitError:
                if attempt < 2:
                    import time
                    time.sleep(30)
                else:
                    raise

    return await asyncio.to_thread(_call)


async def _openai_stream_message(
    model: str, max_tokens: int, system: str, messages: list, tools: list,
) -> AsyncGenerator[StreamEvent, None]:
    """OpenAI 流式 — 收集完整响应后一次性 yield（简化实现）"""
    # OpenAI 流式 tool_call 拼接较复杂，Phase 2 先用非流式模拟
    response = await _openai_create_message(model, max_tokens, system, messages, tools)
    for block in response.content:
        if isinstance(block, TextBlock):
            yield StreamEvent(event_type="text_delta", text=block.text)
        elif isinstance(block, ToolUseBlock):
            yield StreamEvent(
                event_type="tool_use_start",
                tool_id=block.id,
                tool_name=block.name,
                tool_input_json=json.dumps(block.input, ensure_ascii=False),
            )
    yield StreamEvent(event_type="done", stop_reason=response.stop_reason)


# ─── 统一入口 ──────────��─────────────────────────────────────────────────────


async def create_message(
    model: str, max_tokens: int, system: str, messages: list, tools: list,
) -> LLMResponse:
    if settings.LLM_BACKEND == "anthropic":
        return await _anthropic_create_message(model, max_tokens, system, messages, tools)
    elif settings.LLM_BACKEND == "openai":
        return await _openai_create_message(model, max_tokens, system, messages, tools)
    else:
        raise ValueError(f"不支持的 LLM_BACKEND: {settings.LLM_BACKEND}")


async def create_message_stream(
    model: str, max_tokens: int, system: str, messages: list, tools: list,
) -> AsyncGenerator[StreamEvent, None]:
    if settings.LLM_BACKEND == "anthropic":
        async for event in _anthropic_stream_message(model, max_tokens, system, messages, tools):
            yield event
    elif settings.LLM_BACKEND == "openai":
        async for event in _openai_stream_message(model, max_tokens, system, messages, tools):
            yield event
    else:
        raise ValueError(f"不支持的 LLM_BACKEND: {settings.LLM_BACKEND}")
