import client from './client';
import type { Conversation } from '../types/chat';

export const conversationsApi = {
  list: (page = 1, pageSize = 20) =>
    client.get<{ conversations: Conversation[]; total: number }>('/conversations', {
      params: { page, page_size: pageSize },
    }),

  get: (id: string) => client.get<Conversation>(`/conversations/${id}`),

  create: (data: { title?: string; model?: string; skill_group_id?: string | null }) =>
    client.post<Conversation>('/conversations', data),

  update: (id: string, data: { title?: string; model?: string; skill_group_id?: string | null }) =>
    client.put<Conversation>(`/conversations/${id}`, data),

  delete: (id: string) => client.delete(`/conversations/${id}`),

  getMessages: (id: string, page = 1, pageSize = 50) =>
    client.get(`/conversations/${id}/messages`, {
      params: { page, page_size: pageSize },
    }),
};
