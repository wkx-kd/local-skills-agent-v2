import { useCallback, useRef } from 'react';
import { useChatStore } from '../stores/chatStore';
import { useWebSocket } from './useWebSocket';
import type { WSMessageReceive } from '../types/chat';

function generateId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

export function useChat() {
  const store = useChatStore();
  const currentConvId = useRef<string | null>(null);

  const handleMessage = useCallback((data: WSMessageReceive) => {
    switch (data.type) {
      case 'text_delta':
        store.appendStreamContent(data.content || '');
        break;
      case 'tool_call':
        // Reset stream so pre-tool partial text doesn't persist;
        // Spin will show while tool runs, then final response streams in
        store.resetStreamContent();
        break;
      case 'tool_result':
        // Tool result is internal — ignore
        break;
      case 'done':
        store.setIsGenerating(false);
        // 将流式内容转为正式消息
        const content = useChatStore.getState().streamContent;
        if (content) {
          store.addMessage({
            id: data.message_id || generateId(),
            conversation_id: currentConvId.current || '',
            role: 'assistant',
            content: [{ type: 'text', text: content }],
            token_count: null,
            created_at: new Date().toISOString(),
          });
        }
        store.resetStreamContent();
        break;
      case 'error':
        store.setIsGenerating(false);
        store.resetStreamContent();
        console.error('Agent error:', data.detail);
        break;
    }
  }, [store]);

  const { connect, send, disconnect } = useWebSocket({
    onMessage: handleMessage,
    onClose: () => store.setIsGenerating(false),
  });

  const sendMessage = useCallback(async (content: string, fileIds?: string[], webSearch?: boolean) => {
    const conv = store.currentConversation;
    if (!conv) return;

    // 添加用户消息到列表
    store.addMessage({
      id: generateId(),
      conversation_id: conv.id,
      role: 'user',
      content: [{ type: 'text', text: content }],
      token_count: null,
      created_at: new Date().toISOString(),
    });

    currentConvId.current = conv.id;
    store.setIsGenerating(true);
    store.resetStreamContent();

    // 等待 WebSocket 连接建立后再发送
    await connect(conv.id);
    send({ type: 'message', content, files: fileIds, web_search: webSearch });
  }, [store, connect, send]);

  const stopGeneration = useCallback(() => {
    send({ type: 'stop' });
    store.setIsGenerating(false);
  }, [send, store]);

  return { sendMessage, stopGeneration, disconnect };
}
