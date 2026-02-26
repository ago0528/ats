import { describe, expect, it } from 'vitest';

import {
  buildRuntimeActorKey,
  emptyRuntimeSecrets,
  normalizeBearerToken,
} from './runtimeSecrets';

describe('runtime secret helpers', () => {
  it('creates empty runtime secrets', () => {
    expect(emptyRuntimeSecrets()).toEqual({ bearer: '', cms: '', mrs: '' });
  });

  it('normalizes bearer token', () => {
    expect(normalizeBearerToken('Bearer abc')).toBe('abc');
    expect(normalizeBearerToken('abc')).toBe('abc');
    expect(normalizeBearerToken('')).toBe('');
  });

  it('builds deterministic actor key from normalized runtime tokens', async () => {
    const actorKey = await buildRuntimeActorKey({
      bearer: 'Bearer abc',
      cms: 'cms',
      mrs: 'mrs',
    });
    const sameInputKey = await buildRuntimeActorKey({
      bearer: 'abc',
      cms: 'cms',
      mrs: 'mrs',
    });
    expect(actorKey).toBe(sameInputKey);
    expect(actorKey.length).toBeGreaterThan(0);
    if (globalThis.crypto?.subtle) {
      expect(actorKey).toBe(
        '3e46fb691ac201eb98aba298b76891abab7254b27869ecf65c3ae969a89d703e',
      );
    }
  });
});
