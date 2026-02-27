import { describe, expect, it } from 'vitest';

import type { ValidationRunItem } from '../../../api/types/validation';
import {
  buildRunItemIdsByQueryId,
  hasEvaluationResult,
  hasExecutionResult,
  needsRunItemActionConfirm,
  resolveScopedRunItemIds,
} from './runItemScope';

const item = (id: string, partial?: Partial<ValidationRunItem>): ValidationRunItem =>
  ({
    id,
    runId: 'run-1',
    ordinal: 1,
    queryId: `q-${id}`,
    queryText: `query-${id}`,
    expectedResult: '',
    category: 'Happy path',
    logicFieldPath: '',
    logicExpectedValue: '',
    conversationRoomIndex: 1,
    repeatIndex: 1,
    conversationId: `conv-${id}`,
    rawResponse: '',
    error: '',
    rawJson: '{}',
    ...partial,
  }) as ValidationRunItem;

describe('runItemScope utils', () => {
  it('detects execution/evaluation results', () => {
    expect(hasExecutionResult(item('1'))).toBe(false);
    expect(hasExecutionResult(item('2', { rawResponse: 'ok' }))).toBe(true);
    expect(hasEvaluationResult(item('3'))).toBe(false);
    expect(
      hasEvaluationResult(
        item('4', {
          llmEvaluation: {
            status: 'DONE',
            evalModel: 'gpt-5.2',
            metricScores: {},
            comment: '',
          },
        }),
      ),
    ).toBe(true);
  });

  it('builds and resolves scoped ids by query id', () => {
    const rows = [
      item('a', { queryId: 'q1' }),
      item('b', { queryId: 'q1' }),
      item('c', { queryId: 'q2' }),
    ];
    const map = buildRunItemIdsByQueryId(rows);

    expect(map.get('q1')).toEqual(['a', 'b']);
    expect(resolveScopedRunItemIds(rows[0], map)).toEqual(['a', 'b']);
    expect(resolveScopedRunItemIds(rows[2], map)).toEqual(['c']);
  });

  it('determines whether confirmation is needed', () => {
    const rows = [
      item('a', { queryId: 'q1', rawResponse: 'ok' }),
      item('b', { queryId: 'q1' }),
    ];

    expect(needsRunItemActionConfirm(rows, ['a', 'b'])).toBe(true);
    expect(needsRunItemActionConfirm(rows, ['b'])).toBe(false);
  });
});
