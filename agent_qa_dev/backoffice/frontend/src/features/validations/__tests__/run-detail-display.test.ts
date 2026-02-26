import { describe, expect, it } from 'vitest';

import type { ValidationRunItem } from '../../../api/types/validation';
import {
  getAgentModeLabel,
  getModelLabel,
  getRunItemStatus,
  getRunStatusLabel,
  UNCLASSIFIED_LABEL,
  UNKNOWN_LABEL,
} from '../utils/historyDetailDisplay';

const baseItem = (partial?: Partial<ValidationRunItem>): ValidationRunItem =>
  ({
    id: 'item-1',
    runId: 'run-1',
    ordinal: 1,
    queryText: 'query',
    expectedResult: '',
    category: 'Happy path',
    logicFieldPath: '',
    logicExpectedValue: '',
    conversationRoomIndex: 1,
    repeatIndex: 1,
    conversationId: 'conv-1',
    rawResponse: '',
    error: '',
    rawJson: '',
    ...partial,
  }) as ValidationRunItem;

describe('history detail display labels', () => {
  it('maps run status labels', () => {
    expect(getRunStatusLabel('PENDING')).toBe('대기');
    expect(getRunStatusLabel('RUNNING')).toBe('진행중');
    expect(getRunStatusLabel('DONE')).toBe('완료');
    expect(getRunStatusLabel('FAILED')).toBe('실패');
    expect(getRunStatusLabel('UNKNOWN')).toBe(UNKNOWN_LABEL);
  });

  it('maps agent/model labels with fallback', () => {
    expect(getAgentModeLabel('ORCHESTRATOR_WORKER_V3')).toBe('AUTO');
    expect(getAgentModeLabel('RECRUIT_PLAN_ASSISTANT')).toBe('실행 에이전트');
    expect(getAgentModeLabel('NOT_DEFINED')).toBe(UNKNOWN_LABEL);

    expect(getModelLabel('gpt-5.2')).toBe('GPT-5.2');
    expect(getModelLabel('gpt-5-mini')).toBe('GPT-5 Mini');
    expect(getModelLabel('random')).toBe(UNKNOWN_LABEL);
  });

  it('computes run item display status', () => {
    expect(getRunItemStatus(baseItem({ rawResponse: 'ok', executedAt: '2026-02-20T00:00:00Z' }))).toBe('success');
    expect(getRunItemStatus(baseItem({ error: 'boom' }))).toBe('failed');
    expect(
      getRunItemStatus(
        baseItem({
          llmEvaluation: {
            status: 'SKIPPED_NO_CRITERIA',
            evalModel: '',
            metricScores: {},
            comment: '',
          },
        }),
      ),
    ).toBe('stopped');
    expect(getRunItemStatus(baseItem())).toBe('pending');
  });

  it('keeps unclassified constant stable', () => {
    expect(UNCLASSIFIED_LABEL).toBe('미분류');
  });
});
