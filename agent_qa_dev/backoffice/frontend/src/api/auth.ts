import { api } from './client';
import type {
  AppEnvironment,
  AuthSessionResponse,
  LocalDevBypassPayload,
  LoginPayload,
} from '../app/types';

export async function loginAuth(payload: LoginPayload) {
  const { data } = await api.post<AuthSessionResponse>('/auth/login', payload);
  return data;
}

export async function getAuthSession(environment: AppEnvironment) {
  const { data } = await api.get<AuthSessionResponse>('/auth/session', {
    params: { environment },
  });
  return data;
}

export async function refreshAuthSession(environment: AppEnvironment) {
  const { data } = await api.post<AuthSessionResponse>('/auth/refresh', { environment });
  return data;
}

export async function logoutAuth() {
  const { data } = await api.post<{ ok: boolean }>('/auth/logout');
  return data;
}

export async function localDevBypassAuth(payload: LocalDevBypassPayload) {
  const { data } = await api.post<AuthSessionResponse>(
    '/auth/local-dev-bypass',
    payload,
  );
  return data;
}
