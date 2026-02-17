import { describe, expect, it } from 'vitest';

import {
  normalizeCsvCell,
  normalizeCsvText,
  resolveColumnIndex,
  splitCsvLine,
  toNormalizedCsvLines,
} from '../csv';

describe('csv utils', () => {
  it('splits csv line with quoted cells', () => {
    expect(splitCsvLine('a,"b,b",c')).toEqual(['a', 'b,b', 'c']);
  });

  it('normalizes csv cell quote wrappers', () => {
    expect(normalizeCsvCell('" hello "')).toBe('hello');
  });

  it('resolves column index by candidates', () => {
    expect(resolveColumnIndex(['질의', '카테고리'], ['query', '질의'])).toBe(0);
    expect(resolveColumnIndex(['질의', '카테고리'], ['group'])).toBe(-1);
  });

  it('normalizes newline variants and bom lines', () => {
    expect(normalizeCsvText('a\r\nb\rc')).toBe('a\nb\nc');
    expect(toNormalizedCsvLines('\uFEFFh1,h2\n\n1,2')).toEqual(['h1,h2', '1,2']);
  });
});
