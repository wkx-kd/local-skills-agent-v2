export interface Conversation {
  id: string;
  title: string;
  model: string;
  skill_group_id: string | null;
  summary: string | null;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: any;
  token_count: number | null;
  created_at: string;
}

// WebSocket 消息类型
export interface WSMessageSend {
  type: 'message' | 'stop';
  content?: string;
  files?: string[];
  web_search?: boolean;
}

export interface WSMessageReceive {
  type: 'text_delta' | 'tool_call' | 'tool_result' | 'done' | 'error' | 'stopped';
  content?: string;
  name?: string;
  input?: any;
  tool_use_id?: string;
  output?: string;
  message_id?: string;
  detail?: string;
}
