import type { QueryBulkUpdatePreviewRow as QueryBulkUpdatePreviewApiRow, ValidationQuery } from '../../../api/types/validation';
import { formatDateYYYYMMDD } from '../../../shared/utils/dateTime';

import type { BulkUpdatePreviewRow } from '../types';

export const BULK_UPDATE_CSV_HEADERS = [
  '쿼리 ID',
  '질의',
  '카테고리',
  '그룹',
  '테스트 세트 수',
  '테스트 세트',
  'targetAssistant',
  'contextJson',
  '기대 결과',
  'Logic 검증 필드',
  'Logic 기대값',
  '등록일자',
  '최근 수정일자',
] as const;

const CHANGED_FIELD_LABELS: Record<string, string> = {
  category: '카테고리',
  group: '그룹',
  queryText: '질의',
  expectedResult: '기대 결과',
  logicFieldPath: 'Logic 검증 필드',
  logicExpectedValue: 'Logic 기대값',
  targetAssistant: 'targetAssistant',
  contextJson: 'contextJson',
};

function toCsvCell(value: string) {
  if (!/[",\n\r]/.test(value)) return value;
  return `"${value.replace(/"/g, '""')}"`;
}

function toStringValue(value: unknown) {
  if (value === null || value === undefined) return '';
  return String(value);
}

export function buildBulkUpdateCsvContent(items: ValidationQuery[]) {
  const lines = [
    BULK_UPDATE_CSV_HEADERS.join(','),
    ...items.map((item) => [
      item.id,
      item.queryText || '',
      item.category || '',
      item.groupName || '',
      String(item.testSetUsage?.count || 0),
      (item.testSetUsage?.testSetNames || []).join(', '),
      item.targetAssistant || '',
      item.contextJson || '',
      item.expectedResult || '',
      item.logicFieldPath || '',
      item.logicExpectedValue || '',
      formatDateYYYYMMDD(item.createdAt, ''),
      formatDateYYYYMMDD(item.updatedAt, ''),
    ].map((cell) => toCsvCell(toStringValue(cell))).join(',')),
  ];
  return `\uFEFF${lines.join('\n')}`;
}

export function toChangedFieldLabels(changedFields: string[]) {
  return changedFields.map((field) => CHANGED_FIELD_LABELS[field] || field);
}

export function mapBulkUpdatePreviewRows(rows: QueryBulkUpdatePreviewApiRow[]): BulkUpdatePreviewRow[] {
  return rows.map((row) => ({
    key: `${row.rowNo}:${row.queryId || ''}`,
    rowNo: row.rowNo,
    queryId: row.queryId || '-',
    queryText: row.queryText || '-',
    status: row.status,
    changedFields: toChangedFieldLabels(Array.isArray(row.changedFields) ? row.changedFields : []),
  }));
}
