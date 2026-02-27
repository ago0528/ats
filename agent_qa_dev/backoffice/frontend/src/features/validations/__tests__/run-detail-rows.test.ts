import { describe, expect, it } from 'vitest';

import type { ValidationRun, ValidationRunItem } from '../../../api/types/validation';
import {
  buildHistoryRows,
  buildResultsKpi,
  buildResultsRows,
  filterHistoryRows,
  filterResultsRows,
  sortHistoryRows,
  sortResultsRows,
} from '../utils/historyDetailRows';

const run = (partial?: Partial<ValidationRun>): ValidationRun =>
  ({
    id: 'run-1',
    environment: 'dev',
    status: 'DONE',
    agentId: 'ORCHESTRATOR_ASSISTANT',
    testModel: 'gpt-5.2',
    evalModel: 'gpt-5.2',
    repeatInConversation: 1,
    conversationRoomCount: 1,
    agentParallelCalls: 1,
    timeoutMs: 1000,
    totalItems: 3,
    doneItems: 3,
    errorItems: 1,
    llmDoneItems: 3,
    createdAt: '2026-02-20T10:00:00Z',
    startedAt: '2026-02-20T10:00:00Z',
    finishedAt: '2026-02-20T10:00:09Z',
    ...partial,
  }) as ValidationRun;

const item = (id: string, partial?: Partial<ValidationRunItem>): ValidationRunItem =>
  ({
    id,
    runId: 'run-1',
    ordinal: 1,
    queryId: id,
    queryText: `query-${id}`,
    expectedResult: '',
    category: 'Happy path',
    logicFieldPath: '',
    logicExpectedValue: '',
    conversationRoomIndex: 1,
    repeatIndex: 1,
    conversationId: `conv-${id}`,
    rawResponse: 'ok',
    error: '',
    rawJson: '{}',
    executedAt: '2026-02-20T10:00:01Z',
    responseTimeSec: 1,
    llmEvaluation: {
      status: 'DONE',
      evalModel: 'gpt-5.2',
      metricScores: {
        intent: 4,
        accuracy: 4,
        stability: 5,
      },
      totalScore: 4.33,
      comment: 'ok',
      evaluatedAt: '2026-02-20T10:00:10Z',
    },
    ...partial,
  }) as ValidationRunItem;

describe('history detail row helpers', () => {
  it('sorts and filters history rows', () => {
    const rows = buildHistoryRows([
      item('a', { responseTimeSec: 11.1 }),
      item('b', { error: 'failure', responseTimeSec: 0.5 }),
      item('c', { responseTimeSec: 10.2 }),
    ]);

    const sorted = sortHistoryRows(rows);
    expect(sorted[0].item.id).toBe('b');
    expect(sorted[1].item.id).toBe('a');

    const filteredErrors = filterHistoryRows(sorted, {
      onlyErrors: true,
      onlySlow: false,
      status: 'all',
      dateRange: [null, null],
    });
    expect(filteredErrors).toHaveLength(1);
    expect(filteredErrors[0].item.id).toBe('b');

    const filteredSlow = filterHistoryRows(sorted, {
      onlyErrors: false,
      onlySlow: true,
      status: 'all',
      dateRange: [null, null],
    });
    expect(filteredSlow.map((row) => row.item.id)).toEqual(['a', 'c']);
  });

  it('sorts and filters result rows with metric focus', () => {
    const rows = buildResultsRows([
      item('a', {
        llmEvaluation: {
          status: 'DONE',
          evalModel: 'gpt-5.2',
          metricScores: { intent: 4, accuracy: 4, stability: 5 },
          totalScore: 4.3,
          comment: '',
        },
      }),
      item('b', {
        error: 'boom',
        llmEvaluation: {
          status: 'DONE_WITH_EXEC_ERROR',
          evalModel: 'gpt-5.2',
          metricScores: { intent: 1, accuracy: 1, stability: 0 },
          totalScore: 0.6,
          comment: '',
        },
      }),
      item('c', {
        llmEvaluation: {
          status: 'DONE',
          evalModel: 'gpt-5.2',
          metricScores: { intent: 2, accuracy: 2, stability: 5 },
          totalScore: 3.0,
          comment: '',
        },
      }),
    ]);

    const sorted = sortResultsRows(rows);
    expect(sorted[0].item.id).toBe('b');

    const lowScoreRows = filterResultsRows(sorted, {
      tablePreset: 'default',
      onlyLowScore: true,
      onlyAbnormal: false,
      onlySlow: false,
      onlyLatencyUnclassified: false,
      scoreBucketFilter: null,
      focusMetric: null,
    });
    expect(lowScoreRows.map((row) => row.item.id)).toEqual(['b']);

    const intentFocusedRows = filterResultsRows(sorted, {
      tablePreset: 'default',
      onlyLowScore: false,
      onlyAbnormal: false,
      onlySlow: false,
      onlyLatencyUnclassified: false,
      scoreBucketFilter: null,
      focusMetric: 'intent',
    });
    expect(intentFocusedRows.map((row) => row.item.id)).toEqual(['b', 'c']);

    const unclassifiedRows = filterResultsRows(sorted, {
      tablePreset: 'default',
      onlyLowScore: false,
      onlyAbnormal: false,
      onlySlow: false,
      onlyLatencyUnclassified: true,
      scoreBucketFilter: null,
      focusMetric: null,
    });
    expect(unclassifiedRows).toHaveLength(3);

    const bucketRows = filterResultsRows(sorted, {
      tablePreset: 'default',
      onlyLowScore: false,
      onlyAbnormal: false,
      onlySlow: false,
      onlyLatencyUnclassified: false,
      scoreBucketFilter: 1,
      focusMetric: null,
    });
    expect(bucketRows.map((row) => row.item.id)).toEqual(['b']);
  });

  it('keeps deterministic order when score and speed are tied', () => {
    const rows = buildResultsRows([
      item('a', {
        ordinal: 2,
        responseTimeSec: 1.5,
        llmEvaluation: {
          status: 'DONE',
          evalModel: 'gpt-5.2',
          metricScores: { intent: 3, accuracy: 3, stability: 5 },
          totalScore: 3,
          comment: '',
        },
      }),
      item('b', {
        ordinal: 1,
        responseTimeSec: 1.5,
        llmEvaluation: {
          status: 'DONE',
          evalModel: 'gpt-5.2',
          metricScores: { intent: 3, accuracy: 3, stability: 5 },
          totalScore: 3,
          comment: '',
        },
      }),
    ]);

    const sorted = sortResultsRows(rows);
    expect(sorted.map((row) => row.item.id)).toEqual(['b', 'a']);
  });

  it('builds KPI summary from run and items', () => {
    const items = [
      item('a'),
      item('b', { error: 'boom', llmEvaluation: { status: 'DONE_WITH_EXEC_ERROR', evalModel: 'gpt-5.2', metricScores: { intent: 1, accuracy: 1, stability: 0 }, totalScore: 0.66, comment: '' } }),
      item('c', { llmEvaluation: { status: 'DONE', evalModel: 'gpt-5.2', metricScores: { intent: 3, accuracy: 3, stability: 5 }, totalScore: 3.66, comment: '' } }),
    ];
    const kpi = buildResultsKpi(run(), items);
    expect(kpi.intent.sampleCount).toBe(3);
    expect(kpi.accuracy.sampleCount).toBe(3);
    expect(kpi.runMeta.totalRows).toBe(3);
    expect(kpi.scoreBuckets['0'] + kpi.scoreBuckets['1'] + kpi.scoreBuckets['2'] + kpi.scoreBuckets['3'] + kpi.scoreBuckets['4'] + kpi.scoreBuckets['5']).toBe(3);
  });

  it('reflects explicit latencyClass updates in KPI immediately', () => {
    const items = [
      item('a', {
        responseTimeSec: 1.1,
        latencyClass: 'SINGLE',
        llmEvaluation: {
          status: 'DONE',
          evalModel: 'gpt-5.2',
          metricScores: { latencySingle: 4 },
          totalScore: 4,
          comment: '',
        },
      }),
      item('b', {
        responseTimeSec: 2.2,
        latencyClass: 'MULTI',
        llmEvaluation: {
          status: 'DONE',
          evalModel: 'gpt-5.2',
          metricScores: { latencyMulti: 3 },
          totalScore: 3,
          comment: '',
        },
      }),
      item('c', { responseTimeSec: 3.3, latencyClass: 'UNCLASSIFIED' }),
    ];

    const kpi = buildResultsKpi(run(), items);
    expect(kpi.speedSingle.sampleCount).toBe(1);
    expect(kpi.speedMulti.sampleCount).toBe(1);
    expect(kpi.latencyUnclassifiedCount).toBe(1);
    expect(kpi.speedSingle.score).toBeCloseTo(4);
    expect(kpi.speedMulti.score).toBeCloseTo(3);
  });

  it('returns not-aggregated reasons when no items exist', () => {
    const kpi = buildResultsKpi(run({ totalItems: 0, doneItems: 0, errorItems: 0, llmDoneItems: 0 }), []);
    expect(kpi.intent.notAggregatedReason).toContain('집계되지 않았습니다');
    expect(kpi.accuracy.notAggregatedReason).toContain('집계되지 않았습니다');
    expect(kpi.speedSingle.notAggregatedReason).toContain('집계되지 않았습니다');
    expect(kpi.consistency.notAggregatedReason).toContain('반복 실행 수가 부족');
  });
});
