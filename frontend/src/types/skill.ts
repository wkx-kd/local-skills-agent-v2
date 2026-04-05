export interface Skill {
  id: string;
  name: string;
  description: string;
  version: string;
  source_type: 'local' | 'git';
  source_url: string | null;
  is_active: boolean;
  created_at: string;
}

export interface SkillGroup {
  id: string;
  name: string;
  description: string | null;
  skills: Skill[];
  created_at: string;
}
