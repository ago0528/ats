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

function hasAnyRuntimeToken(tokens: RuntimeSecrets) {
  return Boolean(
    normalizeBearerToken(tokens.bearer)
    || (tokens.cms || '').trim()
    || (tokens.mrs || '').trim(),
  );
}

function bufferToHex(buffer: ArrayBuffer) {
  const bytes = new Uint8Array(buffer);
  return Array.from(bytes).map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

function fallbackTokenHash(text: string) {
  let hashA = 0x811c9dc5;
  let hashB = 0x9e3779b1;
  for (let index = 0; index < text.length; index += 1) {
    const code = text.charCodeAt(index);
    hashA ^= code;
    hashA = Math.imul(hashA, 0x01000193);
    hashB ^= code + index;
    hashB = Math.imul(hashB, 0x85ebca6b);
  }
  const first = (hashA >>> 0).toString(16).padStart(8, '0');
  const second = (hashB >>> 0).toString(16).padStart(8, '0');
  const reversed = text.split('').reverse().join('');
  let hashC = 0xc2b2ae35;
  for (let index = 0; index < reversed.length; index += 1) {
    const code = reversed.charCodeAt(index);
    hashC ^= code + index;
    hashC = Math.imul(hashC, 0x27d4eb2f);
  }
  const third = (hashC >>> 0).toString(16).padStart(8, '0');
  return `${first}${second}${third}`;
}

export async function buildRuntimeActorKey(tokens: RuntimeSecrets): Promise<string> {
  if (!hasAnyRuntimeToken(tokens)) {
    return '';
  }

  const normalized = [
    normalizeBearerToken(tokens.bearer),
    (tokens.cms || '').trim(),
    (tokens.mrs || '').trim(),
  ].join('|');

  const subtle = globalThis.crypto?.subtle;
  if (!subtle) {
    return fallbackTokenHash(normalized);
  }

  try {
    const encoded = new TextEncoder().encode(normalized);
    const digest = await subtle.digest('SHA-256', encoded);
    return bufferToHex(digest);
  } catch {
    return fallbackTokenHash(normalized);
  }
}
