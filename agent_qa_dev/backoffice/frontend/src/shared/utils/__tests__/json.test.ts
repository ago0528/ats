import { describe, expect, it } from 'vitest';

import { parseJsonOrOriginal, stringifyPretty, tryPrettyJson } from '../json';

describe('json utils', () => {
  it('parses json or returns original string', () => {
    expect(parseJsonOrOriginal('{"a":1}')).toEqual({ a: 1 });
    expect(parseJsonOrOriginal('plain-text')).toBe('plain-text');
    expect(parseJsonOrOriginal('')).toBeUndefined();
  });

  it('stringifies values with fallback behavior', () => {
    expect(stringifyPretty({ a: 1 })).toBe('{\n  "a": 1\n}');
    expect(stringifyPretty('raw')).toBe('raw');
    expect(stringifyPretty(undefined, 'x')).toBe('x');
  });

  it('pretty-prints raw json strings safely', () => {
    expect(tryPrettyJson('{"a":1}')).toBe('{\n  "a": 1\n}');
    expect(tryPrettyJson('raw')).toBe('raw');
    expect(tryPrettyJson(undefined)).toBe('-');
  });
});
