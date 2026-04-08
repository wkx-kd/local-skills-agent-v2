# 流式输出 / 工具调用显示 / Web 搜索按钮 三问题排查总结

## 问题现象

1. **流式输出失效**：AI 回复时流式逐字显示异常，使用工具后表现尤为明显
2. **工具调用信息显示在前端**：对话框中出现 `[调用工具: web_search]`、`[工具结果: ...]` 等不应展示给用户的内容
3. **手动开启 web_search 按钮不生效**：点亮地球图标后，AI 并不会主动搜索；但偶尔在不开启时 AI 也会自行搜索

---

## 排查步骤

### 第一步：确认工具调用信息的来源

阅读 `frontend/src/hooks/useChat.ts`，发现 WebSocket 消息处理逻辑：

```typescript
case 'tool_call':
  store.appendStreamContent(`\n[调用工具: ${data.name}]\n`);  // ← 问题根源
  break;
case 'tool_result':
  store.appendStreamContent(`\n[工具结果: ${data.output?.slice(0, 200)}]\n`);  // ← 问题根源
  break;
```

`tool_call` 和 `tool_result` 事件本是后端内部执行状态，却被拼接进了 `streamContent`，直接暴露给用户。

---

### 第二步：分析流式输出为何表现异常

追踪完整数据流：

| 时序 | 后端发送 | 前端 streamContent |
|------|---------|-------------------|
| 1 | text_delta（工具调用前的文本） | "我来帮你搜索…" |
| 2 | tool_call | "我来帮你搜索…\n[调用工具: web_search]\n" |
| 3 | tool_result | "我来帮你搜索…\n[调用工具: web_search]\n\n[工具结果: ...]\n" |
| 4 | text_delta（最终回答） | 继续追加 |
| 5 | done | 将以上所有内容保存为消息 |

**问题 A**：`streamContent` 被污染，工具调用信息混入最终消息。

**问题 B**：后端数据库只保存**最后一轮**（工具执行完后的回答）的文本，而前端 `streamContent` 保存了**所有轮次**的文本累加。刷新页面后消息内容与流式显示时不一致。

---

### 第三步：分析 web_search 按钮不生效

阅读代码链路：

```
InputArea.tsx: useWebSearch 状态 → sendMessage(..., useWebSearch)
useChat.ts: send({ web_search: webSearch })
chat.py: web_search = data.get("web_search", False) → AgentRunner(enable_web_search=web_search)
agent_service.py: if not self.enable_web_search: 移除 web_search 工具
```

代码逻辑本身正确，开启后 web_search 工具确实会出现在工具列表中。

**根本原因**：工具出现在列表中 ≠ 模型一定会使用它。模型只在认为"有必要"时才调用工具，没有任何系统提示指示它在用户明确开启时应当主动搜索。

---

## 根本原因

| 问题 | 根本原因 |
|------|---------|
| 工具调用信息出现在对话框 | `tool_call`/`tool_result` 事件被错误地追加到 `streamContent` |
| 流式体验异常 | 同上 + 多轮累计的 `streamContent` 与数据库内容不一致 |
| web_search 按钮看似无效 | 工具可用 ≠ 模型主动使用，缺少系统提示引导 |

---

## 修复方案

### 修复一：`frontend/src/hooks/useChat.ts`

**核心思路**：`tool_call` 收到时重置 `streamContent`（此后显示 Spin 等待工具执行），`tool_result` 静默忽略。最终只有工具执行完毕后的 text_delta 进入 `streamContent`，与数据库存储的内容完全一致。

```typescript
case 'tool_call':
  // Reset stream so pre-tool partial text doesn't persist;
  // Spin will show while tool runs, then final response streams in
  store.resetStreamContent();
  break;
case 'tool_result':
  // Tool result is internal — ignore
  break;
```

**修复效果对比**：

| 时序 | 修复前 streamContent | 修复后 streamContent |
|------|---------------------|---------------------|
| 工具调用前文本 | "我来帮你搜索…" | "我来帮你搜索…" |
| tool_call 到达 | 追加 "[调用工具: ...]" | **重置为 ''**（显示 Spin）|
| tool_result 到达 | 追加 "[工具结果: ...]" | 无变化（仍为 ''）|
| 最终回答 text_delta | 继续累加 | 从 '' 开始累加最终回答 |
| done 时保存的消息 | 包含所有中间过程 | **只含最终回答**，与数据库一致 |

---

### 修复二：`backend/app/services/agent_service.py`

**核心思路**：当 `enable_web_search=True` 时，向系统提示追加明确的搜索指导语，引导模型主动使用 `web_search` 工具。

```python
if self.enable_web_search:
    enriched_system += (
        "\n\n## Web 搜索已启用\n"
        "用户已明确开启 Web 搜索。当问题涉及实时信息、最新事件、当前价格/数据或你不确定的"
        "事实时，请主动调用 web_search 工具进行搜索，而不是仅凭训练数据作答。"
    )
```

---

## 验证方法

### 验证后端代码已生效

```bash
docker exec agent_backend grep -n "Web 搜索已启用" /app/app/services/agent_service.py
# 预期：输出包含该字符串的行号
```

### 验证前端代码已生效

```bash
docker exec agent_frontend grep -r "resetStreamContent" /usr/share/nginx/html/assets/
# 预期：找到包含该字符串的 .js 编译产物
```

---

## 部署流程

由于服务器网络原因（HTTP/2 帧层错误）无法直接 `git pull`，使用 `scp` 单文件传输：

```bash
# 在本地执行
scp backend/app/services/agent_service.py root@<IP>:/opt/agent/backend/app/services/agent_service.py
scp frontend/src/hooks/useChat.ts root@<IP>:/opt/agent/frontend/src/hooks/useChat.ts

# 在服务器执行
docker compose up -d --build backend frontend
```

如后续 `git pull` 仍因 HTTP/2 失败，可尝试：

```bash
git config --global http.version HTTP/1.1
git pull origin main
```

---

## 经验总结

| 检查项 | 方法 | 说明 |
|--------|------|------|
| WebSocket 消息处理逻辑 | 阅读 `useChat.ts` switch-case | 所有 WS 事件类型都需考虑是否应展示给用户 |
| 流式与数据库内容一致性 | 对比后端保存逻辑与前端累积逻辑 | 后端只保存最后一轮文本，前端需同步 |
| 工具按钮不生效 | 检查工具可用性 vs 模型使用意愿 | 工具在列表中 ≠ 模型会主动调用，需系统提示引导 |
| 验证容器内代码版本 | `docker exec container grep -n "关键字" /app/...` | 确认新代码已进入容器，避免"改了但没生效"的误判 |

**关键教训**：

- WebSocket 的内部状态事件（tool_call、tool_result）属于**执行过程信息**，不应直接显示在对话流中，应通过专门的 UI 元素（如进度指示器）展示或完全隐藏
- 流式显示的内容与数据库存储的内容必须保持**来源一致**，否则刷新后用户会看到不同的内容
- 给模型提供工具只是"授权"，让模型**主动使用**工具还需要在系统提示中给出明确指导
