import { describe, it, expect } from 'vitest';
import { RUN_TABLE_COLUMNS } from '../components/RunTable';
import { RUN_CREATION_LABEL, RUN_CREATION_HELP_TOOLTIP } from '../GenericRunPage';

describe('generic flow', () => {
  it('defines required result columns', () => {
    expect(RUN_TABLE_COLUMNS.map((x) => x.dataIndex)).toEqual([
      'queryId',
      'query',
      'responseText',
      'responseTimeSec',
      'logicResult',
      'llmEvalStatus',
      'error',
    ]);
  });

  it('uses updated UX labels', () => {
    expect(RUN_CREATION_LABEL).toBe('검증 실행 생성');
    expect(RUN_CREATION_HELP_TOOLTIP).toContain('1단계');
  });
});
