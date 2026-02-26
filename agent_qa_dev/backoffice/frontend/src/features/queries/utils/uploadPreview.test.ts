import { describe, expect, it } from 'vitest';

import { parseUploadPreviewFile } from './uploadPreview';

describe('query upload preview parser', () => {
  it('parses csv preview rows', async () => {
    const csv = '질의,카테고리,그룹\nhello,Happy path,group-a\n';
    const file = new File([csv], 'queries.csv', { type: 'text/csv' });

    const result = await parseUploadPreviewFile(file);
    expect(result.totalRows).toBe(1);
    expect(result.rows[0]).toMatchObject({ queryText: 'hello', category: 'Happy path', groupName: 'group-a' });
  });

  it('parses optional query columns from template headers', async () => {
    const csv = [
      '질의,카테고리,그룹,targetAssistant,contextJson,기대 결과,Logic 검증 필드,Logic 기대값,latencyClass',
      'hello,Happy path,group-a,ASSISTANT_A,{"recruitPlanId":123},결과 설명,assistantMessage,채용,SINGLE',
    ].join('\n');
    const file = new File([csv], 'queries.csv', { type: 'text/csv' });

    const result = await parseUploadPreviewFile(file);
    expect(result.totalRows).toBe(1);
    expect(result.rows[0]).toMatchObject({
      queryText: 'hello',
      category: 'Happy path',
      groupName: 'group-a',
      targetAssistant: 'ASSISTANT_A',
      contextJson: '{recruitPlanId:123}',
      expectedResult: '결과 설명',
      logicFieldPath: 'assistantMessage',
      logicExpectedValue: '채용',
      latencyClass: 'SINGLE',
    });
  });

  it('returns excel warning for non-csv files', async () => {
    const file = new File(['x'], 'queries.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const result = await parseUploadPreviewFile(file);
    expect(result.totalRows).toBe(0);
    expect(result.emptyText).toContain('미리보기를 지원하지 않아요');
  });
});
