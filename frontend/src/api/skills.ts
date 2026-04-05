import client from './client';
import type { Skill, SkillGroup } from '../types/skill';

export const skillsApi = {
  list: () => client.get<{ skills: Skill[]; total: number }>('/skills'),

  toggle: (id: string) => client.put<Skill>(`/skills/${id}/toggle`),

  uninstall: (id: string) => client.delete(`/skills/${id}`),

  installGit: (url: string) => client.post<Skill>('/skills/install/git', { source: 'git', url }),

  installUpload: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post<Skill>('/skills/install/upload', formData);
  },

  refresh: () => client.post<{ skills: Skill[]; total: number }>('/skills/refresh'),

  // Skill Groups
  listGroups: () => client.get<SkillGroup[]>('/skills/groups'),

  getGroup: (id: string) => client.get<SkillGroup>(`/skills/groups/${id}`),

  createGroup: (data: { name: string; description?: string; skill_ids?: string[] }) =>
    client.post<SkillGroup>('/skills/groups', data),

  updateGroup: (id: string, data: { name?: string; description?: string; skill_ids?: string[] }) =>
    client.put<SkillGroup>(`/skills/groups/${id}`, data),

  deleteGroup: (id: string) => client.delete(`/skills/groups/${id}`),
};
