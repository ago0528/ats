import { CloseCircleOutlined } from '@ant-design/icons';
import { Card, Tag, Tooltip, Typography } from 'antd';
import { StandardDataTable } from '../../../components/common/StandardDataTable';

export type RowItem = {
  id: string;
  ordinal?: number | null;
  queryId?: string | null;
  query?: string | null;
  responseText?: string | null;
  responseTimeSec?: number | null;
  logicResult?: string | null;
  llmEvalStatus?: string | null;
  error?: string | null;
  executionProcess?: string | null;
  rawJson?: string | null;
  llmCriteria?: string | null;
  fieldPath?: string | null;
  expectedValue?: string | null;
};

const RUN_TABLE_INITIAL_COLUMN_WIDTHS = {
  queryId: 140,
  query: 300,
  responseText: 360,
  responseTimeSec: 120,
  logicResult: 140,
  llmEvalStatus: 140,
  error: 220,
};

const withOptional = (value: string | null | undefined, fallback = '-') => String(value ?? fallback);

function statusToTag(status: string) {
  const normalized = status.toLowerCase();
  if (normalized.includes('pass')) return <Tag color="success">PASS</Tag>;
  if (normalized.includes('fail')) return <Tag color="error">FAIL</Tag>;
  if (normalized.includes('skip')) return <Tag color="warning">SKIP</Tag>;
  return <Tag color="default">{status || '-'}</Tag>;
}

function responseTimeText(value: number | null | undefined) {
  if (value === null || value === undefined) return '-';
  return `${value.toFixed(3)}s`;
}

function detailLabel(label: string, value: string | null | undefined, fallback = '-') {
  return `${label}: ${withOptional(value, fallback)}`;
}

export const RUN_TABLE_COLUMNS = [
  {
    key: 'queryId',
    title: '질의 ID',
    dataIndex: 'queryId',
    sorter: (a: RowItem, b: RowItem) => String(a.queryId ?? '').localeCompare(String(b.queryId ?? '')),
  },
  {
    key: 'query',
    title: '질의',
    dataIndex: 'query',
    sorter: (a: RowItem, b: RowItem) => String(a.query ?? '').localeCompare(String(b.query ?? '')),
    ellipsis: true,
    render: (value: string) => (
      <Tooltip title={value}>
        <Typography.Text ellipsis={{ tooltip: value }}>{withOptional(value)}</Typography.Text>
      </Tooltip>
    ),
  },
  {
    key: 'responseText',
    title: '응답',
    dataIndex: 'responseText',
    width: 360,
    render: (value: string) => (
      <Typography.Text
        code
        style={{ whiteSpace: 'pre-wrap', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }}
      >
        {withOptional(value, '-') || '-'}
      </Typography.Text>
    ),
  },
  {
    key: 'responseTimeSec',
    title: '응답시간',
    dataIndex: 'responseTimeSec',
    width: 110,
    sorter: (a: RowItem, b: RowItem) => Number(a.responseTimeSec ?? 0) - Number(b.responseTimeSec ?? 0),
    render: (value: number | null) => responseTimeText(value),
  },
  {
    key: 'logicResult',
    title: '로직 검증결과',
    dataIndex: 'logicResult',
    sorter: (a: RowItem, b: RowItem) =>
      String(a.logicResult ?? '').localeCompare(String(b.logicResult ?? '')),
    render: (value: string) => statusToTag(withOptional(value)),
  },
  {
    key: 'llmEvalStatus',
    title: 'LLM 상태',
    dataIndex: 'llmEvalStatus',
    sorter: (a: RowItem, b: RowItem) =>
      String(a.llmEvalStatus ?? '').localeCompare(String(b.llmEvalStatus ?? '')),
    render: (value: string) => statusToTag(withOptional(value, '')),
  },
  {
    key: 'error',
    title: '오류',
    dataIndex: 'error',
    width: 220,
    ellipsis: true,
    render: (value: string) => {
      if (!value) {
        return <Typography.Text type="secondary">-</Typography.Text>;
      }

      return (
        <Tooltip title={value}>
          <Typography.Text type="danger" style={{ whiteSpace: 'pre-wrap' }}>
            <CloseCircleOutlined /> {withOptional(value)}
          </Typography.Text>
        </Tooltip>
      );
    },
  },
];

export function RunTable({ rows }: { rows: RowItem[] }) {
  const rowCount = rows.length;
  const hasRows = rows.length > 0;

  return (
    <StandardDataTable
      tableId="generic-run-legacy-results"
      initialColumnWidths={RUN_TABLE_INITIAL_COLUMN_WIDTHS}
      minColumnWidth={100}
      rowKey="id"
      className="run-table query-management-table"
      columns={RUN_TABLE_COLUMNS}
      dataSource={rows}
      rowClassName={(row) => (String(row.error || '').trim() ? 'ant-table-row-error' : '')}
      scroll={{ x: 1200, y: 420 }}
      locale={{
        emptyText: '현재 결과 데이터가 없습니다. 실행 생성 또는 결과 업데이트를 해주세요.',
      }}
      onRow={(row) => ({
        style: { cursor: 'default' },
        'data-row-index': row.id,
      })}
      title={() => (hasRows ? `총 ${rowCount}건` : '결과 데이터')}
      expandable={{
        expandedRowRender: (row) => (
          <Card size="small" className="run-row-details">
            <Typography.Paragraph className="run-row-details-title" style={{ marginBottom: 10 }}>
              {detailLabel('실행 프로세스', row.executionProcess, '없음')}
            </Typography.Paragraph>
            <Typography.Paragraph copyable style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
              {withOptional(row.rawJson, '').trim() || '-'}
            </Typography.Paragraph>
            <Typography.Text type="secondary" className="run-row-meta">
              {detailLabel('LLM 평가기준', row.llmCriteria)}
              {' / '}
              {detailLabel('검증 필드', row.fieldPath)}
              {' / '}
              {detailLabel('기대값', row.expectedValue)}
            </Typography.Text>
          </Card>
        ),
        rowExpandable: () => true,
      }}
    />
  );
}
