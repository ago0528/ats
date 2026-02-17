import { describe, expect, it } from 'vitest';

import type { ValidationRun } from '../../../api/types/validation';
import { canCompareRun, canCreateRun, canEvaluateRun, canExecuteRun } from '../utils/runWorkbench';

const run = (partial?: Partial<ValidationRun>): ValidationRun =>
  ({
    id: 'run-1',
    mode: 'REGISTERED',
    environment: 'dev',
    status: 'PENDING',
    agentId: 'ORCHESTRATOR_WORKER_V3',
    testModel: 'gpt-5.2',
    evalModel: 'gpt-5.2',
    repeatInConversation: 1,
    conversationRoomCount: 1,
    agentParallelCalls: 1,
    timeoutMs: 120000,
    totalItems: 10,
    doneItems: 0,
    errorItems: 0,
    llmDoneItems: 0,
    ...partial,
  }) as ValidationRun;

describe('run workbench gates', () => {
  it('checks create/execute/evaluate/compare gates', () => {
    expect(canCreateRun('')).toBe(false);
    expect(canCreateRun('test-set-1')).toBe(true);

    expect(canExecuteRun(run({ status: 'PENDING' }))).toBe(true);
    expect(canExecuteRun(run({ status: 'DONE' }))).toBe(false);

    expect(canEvaluateRun(run({ doneItems: 0, errorItems: 0 }))).toBe(false);
    expect(canEvaluateRun(run({ doneItems: 1, errorItems: 0 }))).toBe(true);
    expect(canEvaluateRun(run({ doneItems: 0, errorItems: 1 }))).toBe(true);

    expect(canCompareRun(run(), '')).toBe(false);
    expect(canCompareRun(run(), 'base-run-1')).toBe(true);
  });
});
