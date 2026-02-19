import { describe, expect, it } from 'vitest';

import { normalizePromptSnapshot } from './promptSnapshot';

describe('prompt snapshot utils', () => {
  it('uses new response fields first', () => {
    const snapshot = normalizePromptSnapshot({
      before: 'legacy-before',
      after: 'legacy-after',
      currentPrompt: 'ats-current',
      previousPrompt: '',
    });

    expect(snapshot.currentPrompt).toBe('ats-current');
    expect(snapshot.previousPrompt).toBe('');
  });

  it('falls back to legacy before/after response', () => {
    const snapshot = normalizePromptSnapshot({
      before: 'legacy-before',
      after: 'legacy-after',
    });

    expect(snapshot.currentPrompt).toBe('legacy-after');
    expect(snapshot.previousPrompt).toBe('legacy-before');
  });

  it('falls back to before when after is missing', () => {
    const snapshot = normalizePromptSnapshot({
      before: 'legacy-before-only',
    });

    expect(snapshot.currentPrompt).toBe('legacy-before-only');
    expect(snapshot.previousPrompt).toBe('legacy-before-only');
  });
});
