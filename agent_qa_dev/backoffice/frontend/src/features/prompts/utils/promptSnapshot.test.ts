import { describe, expect, it } from 'vitest';

import {
  normalizeEvalPromptSnapshot,
  normalizePromptSnapshot,
  normalizePromptText,
} from './promptSnapshot';

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

  it('normalizes unusual line terminators to LF', () => {
    expect(normalizePromptText('a\r\nb\rc\u2028d\u2029e')).toBe('a\nb\nc\nd\ne');

    const snapshot = normalizePromptSnapshot({
      before: 'one\u2028two',
      after: 'three\u2029four',
      currentPrompt: 'x\r\ny',
      previousPrompt: 'p\rq',
    });

    expect(snapshot.before).toBe('one\ntwo');
    expect(snapshot.after).toBe('three\nfour');
    expect(snapshot.currentPrompt).toBe('x\ny');
    expect(snapshot.previousPrompt).toBe('p\nq');
  });

  it('normalizes evaluation prompt snapshot fields', () => {
    const snapshot = normalizeEvalPromptSnapshot({
      promptKey: 'validation_scoring',
      currentPrompt: 'line1\r\nline2',
      previousPrompt: 'old\u2028prompt',
      currentVersionLabel: 'v3.0.0',
      previousVersionLabel: 'v2.9.0',
      updatedAt: '2026-03-01T00:00:00',
      updatedBy: 'qa_admin',
    });

    expect(snapshot.promptKey).toBe('validation_scoring');
    expect(snapshot.currentPrompt).toBe('line1\nline2');
    expect(snapshot.previousPrompt).toBe('old\nprompt');
    expect(snapshot.currentVersionLabel).toBe('v3.0.0');
    expect(snapshot.previousVersionLabel).toBe('v2.9.0');
    expect(snapshot.updatedBy).toBe('qa_admin');
  });
});
