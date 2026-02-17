import { describe, expect, it } from 'vitest';

import { calculateLineDiff, getLengthDelta } from './promptDiff';

describe('prompt diff utils', () => {
  it('calculates line diff summary', () => {
    const result = calculateLineDiff('a\nb\n', 'a\nc\n');
    expect(result.modified).toBe(1);
    expect(result.added).toBe(0);
    expect(result.removed).toBe(0);
    expect(result.diffText).toContain('- b');
    expect(result.diffText).toContain('+ c');
  });

  it('returns length delta string', () => {
    expect(getLengthDelta('abc', 'abc')).toBe('0');
    expect(getLengthDelta('a', 'abc')).toBe('+2');
    expect(getLengthDelta('abc', 'a')).toBe('-2');
  });
});
