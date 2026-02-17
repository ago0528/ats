import { describe, expect, it } from 'vitest';

import { emptyRuntimeSecrets, normalizeBearerToken } from './runtimeSecrets';

describe('runtime secret helpers', () => {
  it('creates empty runtime secrets', () => {
    expect(emptyRuntimeSecrets()).toEqual({ bearer: '', cms: '', mrs: '' });
  });

  it('normalizes bearer token', () => {
    expect(normalizeBearerToken('Bearer abc')).toBe('abc');
    expect(normalizeBearerToken('abc')).toBe('abc');
    expect(normalizeBearerToken('')).toBe('');
  });
});
