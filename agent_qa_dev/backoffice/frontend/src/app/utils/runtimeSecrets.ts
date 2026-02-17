import type { RuntimeSecrets } from '../types';

export function emptyRuntimeSecrets(): RuntimeSecrets {
  return { bearer: '', cms: '', mrs: '' };
}

export function normalizeBearerToken(value: string) {
  const token = (value || '').trim();
  if (!token) return '';
  const bearerPrefix = /^bearer\s+/i;
  if (bearerPrefix.test(token)) {
    return token.slice(token.match(bearerPrefix)?.[0]?.length ?? 0).trim();
  }
  return token;
}
