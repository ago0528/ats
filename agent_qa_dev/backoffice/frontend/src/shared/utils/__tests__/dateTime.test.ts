import { describe, expect, it } from 'vitest';

import {
  formatDateTime,
  formatLocaleDateTime,
  formatLocaleTime,
  formatShortDate,
  toTimestamp,
} from '../dateTime';

describe('dateTime utils', () => {
  it('formats date time in fixed pattern', () => {
    expect(formatDateTime('2024-01-02T03:04:00')).toBe('2024-01-02 03:04');
  });

  it('returns raw value when datetime is invalid', () => {
    expect(formatDateTime('invalid')).toBe('invalid');
  });

  it('formats short date', () => {
    expect(formatShortDate('2024-11-09T12:10:00')).toBe('24-11-09');
  });

  it('returns dash for invalid short date', () => {
    expect(formatShortDate('invalid')).toBe('-');
  });

  it('converts to timestamp', () => {
    expect(toTimestamp('2024-01-01T00:00:00Z')).toBeGreaterThan(0);
    expect(toTimestamp('invalid')).toBe(0);
  });

  it('formats locale outputs safely', () => {
    expect(formatLocaleDateTime('2024-01-01T00:00:00Z')).not.toBe('-');
    expect(formatLocaleDateTime('invalid')).toBe('-');
    expect(formatLocaleTime('2024-01-01T00:00:00Z')).not.toBe('-');
    expect(formatLocaleTime('invalid')).toBe('-');
  });
});
