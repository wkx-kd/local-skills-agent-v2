import { useEffect, useRef } from 'react';
import { Empty, Spin } from 'antd';
import { useChatStore } from '../../stores/chatStore';
import MessageBubble from './MessageBubble';

export default function ChatWindow() {
  const { messages, streamContent, isGenerating, currentConversation } = useChatStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamContent]);

  if (!currentConversation) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Empty description="选择或创建一个对话" />
      </div>
    );
  }

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: '16px 24px' }}>
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      {isGenerating && streamContent && (
        <MessageBubble
          message={{
            id: 'streaming',
            conversation_id: currentConversation.id,
            role: 'assistant',
            content: [{ type: 'text', text: streamContent }],
            token_count: null,
            created_at: new Date().toISOString(),
          }}
        />
      )}
      {isGenerating && !streamContent && (
        <div style={{ textAlign: 'center', padding: 16 }}>
          <Spin tip="思考中..." />
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
