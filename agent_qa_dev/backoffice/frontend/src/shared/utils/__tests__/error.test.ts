import { describe, expect, it } from 'vitest';

import { getRequestErrorMessage } from '../error';

describe('error utils', () => {
  it('returns error from response string data', () => {
    const error = { response: { data: 'api error' } };
    expect(getRequestErrorMessage(error)).toBe('api error');
  });

  it('returns error from response detail field', () => {
    const error = { response: { data: { detail: 'detail error' } } };
    expect(getRequestErrorMessage(error)).toBe('detail error');
  });

  it('returns native error message', () => {
    expect(getRequestErrorMessage(new Error('native error'))).toBe('native error');
  });

  it('falls back when no error detail is available', () => {
    expect(getRequestErrorMessage({})).toBe('요청 처리 중 오류가 발생했습니다.');
    expect(getRequestErrorMessage({}, 'fallback')).toBe('fallback');
  });
});
