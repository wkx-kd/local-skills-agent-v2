import { create } from 'zustand';
import type { Conversation, Message } from '../types/chat';
import { conversationsApi } from '../api/conversations';

interface ChatState {
  conversations: Conversation[];
  currentConversation: Conversation | null;
  messages: Message[];
  isGenerating: boolean;
  streamContent: string;

  fetchConversations: () => Promise<void>;
  setCurrentConversation: (conv: Conversation | null) => void;
  createConversation: (data: { title?: string; model?: string; skill_group_id?: string | null }) => Promise<Conversation>;
  deleteConversation: (id: string) => Promise<void>;
  fetchMessages: (conversationId: string) => Promise<void>;
  addMessage: (message: Message) => void;
  setIsGenerating: (val: boolean) => void;
  appendStreamContent: (delta: string) => void;
  resetStreamContent: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  conversations: [],
  currentConversation: null,
  messages: [],
  isGenerating: false,
  streamContent: '',

  fetchConversations: async () => {
    const res = await conversationsApi.list();
    set({ conversations: res.data.conversations });
  },

  setCurrentConversation: (conv) => {
    set({ currentConversation: conv, messages: [], streamContent: '' });
  },

  createConversation: async (data) => {
    const res = await conversationsApi.create(data);
    const conv = res.data;
    set((state) => ({ conversations: [conv, ...state.conversations], currentConversation: conv }));
    return conv;
  },

  deleteConversation: async (id) => {
    await conversationsApi.delete(id);
    set((state) => {
      const conversations = state.conversations.filter((c) => c.id !== id);
      const currentConversation = state.currentConversation?.id === id ? null : state.currentConversation;
      return { conversations, currentConversation, messages: currentConversation ? state.messages : [] };
    });
  },

  fetchMessages: async (conversationId) => {
    const res = await conversationsApi.getMessages(conversationId);
    set({ messages: res.data.messages });
  },

  addMessage: (message) => {
    set((state) => ({ messages: [...state.messages, message] }));
  },

  setIsGenerating: (val) => set({ isGenerating: val }),
  appendStreamContent: (delta) => set((state) => ({ streamContent: state.streamContent + delta })),
  resetStreamContent: () => set({ streamContent: '' }),
}));
