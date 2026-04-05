import client from './client';

export interface UploadedFile {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  processing_status: string;
  processing_strategy: string | null;
  chunk_count: number;
  created_at: string;
}

export const filesApi = {
  upload: (file: File, conversationId?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    const params = conversationId ? { conversation_id: conversationId } : {};
    return client.post<UploadedFile>('/files/upload', formData, { params });
  },

  list: (conversationId?: string, page = 1, pageSize = 20) =>
    client.get<{ files: UploadedFile[]; total: number }>('/files', {
      params: { conversation_id: conversationId, page, page_size: pageSize },
    }),

  delete: (id: string) => client.delete(`/files/${id}`),

  downloadUrl: (id: string) => `/api/files/${id}/download`,
};
