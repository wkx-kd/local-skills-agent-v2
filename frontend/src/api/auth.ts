import client from './client';
import type { User, TokenResponse } from '../types/user';

export const authApi = {
  register: (data: { username: string; email: string; password: string }) =>
    client.post<User>('/auth/register', data),

  login: (data: { username: string; password: string }) =>
    client.post<TokenResponse>('/auth/login', data),

  getMe: () => client.get<User>('/auth/me'),

  refresh: (refresh_token: string) =>
    client.post<TokenResponse>('/auth/refresh', { refresh_token }),
};
