import { describe, it, expect } from 'vitest';
import { buildWorkerLabel } from '../PromptManagementPage';
describe('prompt management', () => {
    it('formats worker label', () => {
        expect(buildWorkerLabel({ workerType: 'W', description: 'desc' })).toBe('W - desc');
    });
});
