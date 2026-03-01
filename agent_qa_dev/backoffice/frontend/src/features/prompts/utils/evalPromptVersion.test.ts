import { describe, expect, it } from 'vitest';

import {
  getEvalPromptVersionValidationMessage,
  isValidEvalPromptVersionLabel,
} from './evalPromptVersion';

describe('eval prompt version utils', () => {
  it('accepts a valid version label', () => {
    expect(isValidEvalPromptVersionLabel('v3.0.0')).toBe(true);
    expect(getEvalPromptVersionValidationMessage('v3.0.0')).toBe('');
  });

  it('rejects empty or invalid labels', () => {
    expect(isValidEvalPromptVersionLabel('')).toBe(false);
    expect(isValidEvalPromptVersionLabel('-invalid')).toBe(false);
    expect(getEvalPromptVersionValidationMessage('')).toContain('입력');
    expect(getEvalPromptVersionValidationMessage('-invalid')).toContain('형식');
  });
});
