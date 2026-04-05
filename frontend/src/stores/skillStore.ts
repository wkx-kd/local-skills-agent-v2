import { create } from 'zustand';
import type { Skill, SkillGroup } from '../types/skill';
import { skillsApi } from '../api/skills';

interface SkillState {
  skills: Skill[];
  skillGroups: SkillGroup[];
  selectedGroupId: string | null;

  fetchSkills: () => Promise<void>;
  fetchSkillGroups: () => Promise<void>;
  toggleSkill: (id: string) => Promise<void>;
  setSelectedGroupId: (id: string | null) => void;
}

export const useSkillStore = create<SkillState>((set) => ({
  skills: [],
  skillGroups: [],
  selectedGroupId: null,

  fetchSkills: async () => {
    const res = await skillsApi.list();
    set({ skills: res.data.skills });
  },

  fetchSkillGroups: async () => {
    const res = await skillsApi.listGroups();
    set({ skillGroups: res.data });
  },

  toggleSkill: async (id) => {
    const res = await skillsApi.toggle(id);
    set((state) => ({
      skills: state.skills.map((s) => (s.id === id ? res.data : s)),
    }));
  },

  setSelectedGroupId: (id) => set({ selectedGroupId: id }),
}));
