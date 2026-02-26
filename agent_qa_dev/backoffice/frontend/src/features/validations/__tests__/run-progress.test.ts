import { describe, expect, it } from 'vitest';

import type { ValidationRun, ValidationRunItem } from '../../../api/types/validation';
import {
  getEvaluationProgressText,
  getEvaluationStateLabel,
  getExecutionStateLabel,
  getRunStageAvailability,
} from '../utils/runProgress';

const run = (status: string): ValidationRun =>
  ({
    id: 'run-1',
    environment: 'dev',
    status,
    agentId: 'ORCHESTRATOR_WORKER_V3',
    testModel: 'gpt-5.2',
    evalModel: 'gpt-5.2',
    repeatInConversation: 1,
    conversationRoomCount: 1,
    agentParallelCalls: 1,
    timeoutMs: 1000,
    totalItems: 1,
    doneItems: 0,
    errorItems: 0,
    llmDoneItems: 0,
  }) as ValidationRun;

const item = (partial?: Partial<ValidationRunItem>): ValidationRunItem =>
  ({
    id: 'item-1',
    runId: 'run-1',
    ordinal: 1,
    queryText: 'q',
    expectedResult: '',
    category: 'Happy path',
    logicFieldPath: '',
    logicExpectedValue: '',
    conversationRoomIndex: 1,
    repeatIndex: 1,
    conversationId: '',
    rawResponse: '',
    error: '',
    rawJson: '',
    ...partial,
  }) as ValidationRunItem;

describe('run progress helpers', () => {
  it('calculates stage availability', () => {
    expect(getRunStageAvailability(null, [])).toEqual({
      executeEnabled: false,
      evaluateEnabled: false,
      resultEnabled: false,
    });
    expect(getRunStageAvailability(run('PENDING'), [])).toEqual({
      executeEnabled: true,
      evaluateEnabled: false,
      resultEnabled: false,
    });
    expect(getRunStageAvailability(run('DONE'), [item({ rawResponse: 'ok' })])).toEqual({
      executeEnabled: true,
      evaluateEnabled: true,
      resultEnabled: true,
    });
  });

  it('calculates execution labels', () => {
    expect(getExecutionStateLabel(null)).toBe('미생성');
    expect(getExecutionStateLabel(run('PENDING'))).toBe('실행대기');
    expect(getExecutionStateLabel(run('RUNNING'))).toBe('실행중');
    expect(getExecutionStateLabel(run('DONE'))).toBe('실행완료');
    expect(getExecutionStateLabel(run('FAILED'))).toBe('실행실패');
  });

  it('calculates evaluation labels and progress', () => {
    expect(getEvaluationStateLabel(run('DONE'), [])).toBe('평가대기');
    expect(getEvaluationStateLabel(run('DONE'), [item(), item({ llmEvaluation: { status: 'DONE' } as ValidationRunItem['llmEvaluation'] })])).toBe('평가중');
    expect(
      getEvaluationStateLabel(run('DONE'), [
        item({ llmEvaluation: { status: 'DONE' } as ValidationRunItem['llmEvaluation'] }),
        item({ id: 'item-2', llmEvaluation: { status: 'DONE' } as ValidationRunItem['llmEvaluation'] }),
      ]),
    ).toBe('평가완료');
    expect(
      getEvaluationProgressText([
        item({ llmEvaluation: { status: 'DONE' } as ValidationRunItem['llmEvaluation'] }),
        item({ id: 'item-2' }),
      ]),
    ).toBe('1 / 2');
  });
});
