import { describe, it, expect } from 'vitest';
import { buildWorkerLabel } from '../utils/promptViewModel';

describe('prompt management', () => {
  it('formats worker label', () => {
    expect(buildWorkerLabel({ workerType: 'W', description: 'desc' })).toBe('W - desc');
  });
});
