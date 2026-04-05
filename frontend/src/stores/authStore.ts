import { create } from 'zustand';
import type { User } from '../types/user';
import { authApi } from '../api/auth';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  fetchUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: !!localStorage.getItem('access_token'),
  loading: false,

  login: async (username, password) => {
    const res = await authApi.login({ username, password });
    localStorage.setItem('access_token', res.data.access_token);
    localStorage.setItem('refresh_token', res.data.refresh_token);
    const userRes = await authApi.getMe();
    set({ user: userRes.data, isAuthenticated: true });
  },

  register: async (username, email, password) => {
    await authApi.register({ username, email, password });
  },

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    set({ user: null, isAuthenticated: false });
  },

  fetchUser: async () => {
    try {
      set({ loading: true });
      const res = await authApi.getMe();
      set({ user: res.data, isAuthenticated: true, loading: false });
    } catch {
      set({ user: null, isAuthenticated: false, loading: false });
    }
  },
}));
