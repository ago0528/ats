import { normalizeCsvCell, resolveColumnIndex, splitCsvLine, toNormalizedCsvLines } from '../../../shared/utils/csv';

import { BULK_UPLOAD_PREVIEW_LIMIT } from '../constants';
import type { UploadPreviewParseResult, UploadPreviewRow } from '../types';

export async function parseUploadPreviewFile(file: File): Promise<UploadPreviewParseResult> {
  const filename = (file.name || '').toLowerCase();
  if (!filename.endsWith('.csv')) {
    return {
      rows: [],
      totalRows: 0,
      emptyText: '엑셀 파일은 미리보기를 지원하지 않아요. 업로드는 가능합니다.',
    };
  }

  const lines = toNormalizedCsvLines(await file.text());
  if (lines.length <= 1) {
    return {
      rows: [],
      totalRows: 0,
      emptyText: 'CSV 파일에 미리볼 데이터가 없어요.',
    };
  }

  const headers = splitCsvLine(lines[0]).map(normalizeCsvCell);
  const queryIndex = resolveColumnIndex(headers, ['질의', 'query', 'query_text']);
  const categoryIndex = resolveColumnIndex(headers, ['카테고리', 'category']);
  const groupIndex = resolveColumnIndex(headers, ['그룹', 'group', 'group_name', 'groupId', 'group_id']);
  const expectedResultIndex = resolveColumnIndex(headers, ['기대 결과', '기대결과', '기대값', 'expectedResult', 'expected_result', 'expected']);
  const latencyClassIndex = resolveColumnIndex(headers, ['latencyClass', 'latency_class', '응답속도유형', '응답속도 유형']);

  const parsedRows = lines.slice(1).reduce<UploadPreviewRow[]>((acc, line, index) => {
    const columns = splitCsvLine(line).map(normalizeCsvCell);
    const queryText = queryIndex >= 0 ? (columns[queryIndex] || '') : '';
    const category = categoryIndex >= 0 ? (columns[categoryIndex] || '') : '';
    const groupName = groupIndex >= 0 ? (columns[groupIndex] || '') : '';
    const expectedResult = expectedResultIndex >= 0 ? (columns[expectedResultIndex] || '') : '';
    const latencyClass = latencyClassIndex >= 0 ? (columns[latencyClassIndex] || '') : '';

    if (
      !queryText
      && !category
      && !groupName
      && !expectedResult
      && !latencyClass
    ) {
      return acc;
    }

    acc.push({
      key: String(index + 1),
      queryText: queryText || '-',
      category: category || '-',
      groupName: groupName || '-',
      expectedResult: expectedResult || '-',
      latencyClass: latencyClass || '-',
    });
    return acc;
  }, []);

  return {
    rows: parsedRows.slice(0, BULK_UPLOAD_PREVIEW_LIMIT),
    totalRows: parsedRows.length,
    emptyText: '표시할 질의가 없어요.',
    warningText: queryIndex < 0 ? 'CSV 헤더에 "질의" 컬럼이 없어요.' : undefined,
  };
}
