# WebSocket 无响应问题排查总结

## 问题现象

项目部署到阿里云 ECS 后，前端发送消息无任何响应，但登录、创建会话等 REST API 功能正常。本地开发环境无此问题。

---

## 排查步骤

### 第一步：查看后端日志

```bash
docker compose logs --tail=50 backend
```

**结论**：后端日志显示 REST API 请求正常（注册、登录、获取会话等均返回 200），但没有任何 WebSocket 连接记录。

---

### 第二步：查看 Nginx 日志

```bash
docker compose logs --tail=50 frontend
```

**结论**：Nginx 访问日志同样没有任何 `/api/chat/ws/` 路径的请求记录，说明浏览器根本没有发出 WebSocket 连接请求。

---

### 第三步：确认 Nginx 配置正确

```bash
docker exec agent_frontend cat /etc/nginx/conf.d/default.conf
```

**结论**：Nginx WebSocket 代理配置正确，`Connection "upgrade"`、`proxy_http_version 1.1`、超时时间均设置正常。

---

### 第四步：验证 WebSocket 路由是否可达

在服务器上直接用 curl 模拟 WebSocket 握手：

```bash
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  -H "Sec-WebSocket-Version: 13" \
  "http://localhost/api/chat/ws/00000000-0000-0000-0000-000000000000?token=test"
```

**结果**：
```
HTTP/1.1 403 Forbidden
```

**结论**：Nginx 正确将 WebSocket 请求转发到后端，后端也正确拒绝了无效 token（返回 403）。说明服务端链路完全正常，问题在前端 JavaScript。

---

### 第五步：检查浏览器控制台

打开 DevTools → Console，发送一条消息后，出现报错：

```
Uncaught (in promise) TypeError: crypto.randomUUID is not a function
    at onKeyDown
```

**根本原因找到。**

---

## 根本原因

`crypto.randomUUID()` 是 Web Crypto API 的方法，**只在安全上下文（HTTPS 或 localhost）中可用**。

通过 `http://服务器IP` 访问时，该方法不存在，导致：

1. 用户按下 Enter 发送消息
2. `sendMessage` 调用 `crypto.randomUUID()` 为消息生成 ID
3. 抛出 `TypeError: crypto.randomUUID is not a function`
4. 函数提前终止，WebSocket 连接从未建立
5. 用户看到消息没有响应

本地开发使用 `localhost`（安全上下文），所以不受影响。

---

## 修复方案

在 `frontend/src/hooks/useChat.ts` 中添加降级函数，替换所有 `crypto.randomUUID()` 调用：

```typescript
function generateId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // HTTP 环境降级方案
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}
```

将代码中所有 `crypto.randomUUID()` 替换为 `generateId()`。

---

## 经验总结

| 检查项 | 工具 | 作用 |
|--------|------|------|
| 服务端链路 | `docker compose logs` | 确认请求是否到达后端 |
| Nginx 路由 | `curl` 模拟 WebSocket 握手 | 验证代理配置是否生效 |
| 前端错误 | 浏览器 DevTools Console | 发现 JS 运行时异常 |

**关键教训**：部分 Web API（如 `crypto.randomUUID`、`navigator.clipboard` 等）仅在安全上下文中可用。通过 HTTP 部署时，需提前测试或使用兼容性降级方案。长期解决方案是为服务器配置 HTTPS。
