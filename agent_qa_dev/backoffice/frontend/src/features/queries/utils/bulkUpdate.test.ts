import { describe, expect, it } from 'vitest';

import type { ValidationQuery } from '../../../api/types/validation';
import { buildBulkUpdateCsvContent, BULK_UPDATE_CSV_HEADERS, mapBulkUpdatePreviewRows, toChangedFieldLabels } from './bulkUpdate';

function buildQuery(overrides?: Partial<ValidationQuery>): ValidationQuery {
  return {
    id: 'q-1',
    queryText: 'hello',
    expectedResult: 'ok',
    category: 'Happy path',
    groupId: 'g-1',
    groupName: '그룹A',
    logicFieldPath: 'assistantMessage',
    logicExpectedValue: '채용',
    contextJson: '{"foo":"bar"}',
    targetAssistant: 'ORCHESTRATOR_WORKER_V3',
    createdBy: 'tester',
    createdAt: '2026-02-18T00:00:00Z',
    updatedAt: '2026-02-19T00:00:00Z',
    latestRunSummary: undefined,
    testSetUsage: { count: 2, testSetNames: ['세트A', '세트B'] },
    ...overrides,
  };
}

describe('bulk update csv utils', () => {
  it('builds csv with fixed header order', () => {
    const csv = buildBulkUpdateCsvContent([buildQuery()]);
    const [headerLine] = csv.replace('\uFEFF', '').split('\n');
    expect(headerLine).toBe(BULK_UPDATE_CSV_HEADERS.join(','));
  });

  it('escapes csv values and formats dates as YYYY-MM-DD', () => {
    const csv = buildBulkUpdateCsvContent([
      buildQuery({
        queryText: 'hello, "world"',
        contextJson: '{"line":"a\\nb"}',
      }),
    ]);
    const lines = csv.replace('\uFEFF', '').split('\n');
    expect(lines[1]).toContain('"hello, ""world"""');
    expect(lines[1]).toContain('2026-02-18');
    expect(lines[1]).toContain('2026-02-19');
  });

  it('maps changed fields into Korean labels', () => {
    expect(toChangedFieldLabels(['queryText', 'logicFieldPath'])).toEqual(['질의', 'Logic 검증 필드']);
  });

  it('maps preview rows for table rendering', () => {
    const rows = mapBulkUpdatePreviewRows([
      {
        rowNo: 1,
        queryId: 'q-1',
        queryText: 'hello',
        status: 'planned-update',
        changedFields: ['category', 'logicExpectedValue'],
      },
    ]);
    expect(rows[0]).toMatchObject({
      key: '1:q-1',
      queryId: 'q-1',
      changedFields: ['카테고리', 'Logic 기대값'],
    });
  });
});
