import { useMemo } from 'react';
import { Button, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import type { ValidationRun, ValidationRunItem } from '../../../api/types/validation';
import { ValidationRunStatusTag } from '../../../components/common/ValidationRunStatusTag';
import { formatDateTime } from '../../../shared/utils/dateTime';
import {
  HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS,
  HISTORY_INITIAL_COLUMN_WIDTHS,
  RUN_ITEM_INITIAL_COLUMN_WIDTHS,
} from '../constants';

function renderEllipsisCell(value?: string, type?: 'danger') {
  const text = String(value ?? '').trim();
  if (!text) return '-';
  return (
    <Typography.Text type={type} ellipsis={{ tooltip: text }} style={{ display: 'block', width: '100%' }}>
      {text}
    </Typography.Text>
  );
}

export function useValidationColumns({
  handleSaveAsQuery,
}: {
  handleSaveAsQuery: (item: ValidationRunItem) => void;
}) {
  const runItemColumns = useMemo<ColumnsType<ValidationRunItem>>(
    () => [
      {
        key: 'ordinal',
        title: '#',
        dataIndex: 'ordinal',
        width: RUN_ITEM_INITIAL_COLUMN_WIDTHS.ordinal,
      },
      {
        key: 'queryText',
        title: '질의',
        dataIndex: 'queryText',
        width: RUN_ITEM_INITIAL_COLUMN_WIDTHS.queryText,
        ellipsis: true,
        render: (value: string) => renderEllipsisCell(value),
      },
      {
        key: 'roomRepeat',
        title: '방/반복',
        width: RUN_ITEM_INITIAL_COLUMN_WIDTHS.roomRepeat,
        render: (_, row: ValidationRunItem) => `${row.conversationRoomIndex}/${row.repeatIndex}`,
      },
      {
        key: 'rawResponse',
        title: '응답',
        dataIndex: 'rawResponse',
        width: RUN_ITEM_INITIAL_COLUMN_WIDTHS.rawResponse,
        ellipsis: true,
        render: (value: string) => renderEllipsisCell(value),
      },
      {
        key: 'error',
        title: '오류',
        dataIndex: 'error',
        width: RUN_ITEM_INITIAL_COLUMN_WIDTHS.error,
        ellipsis: true,
        render: (value: string) => renderEllipsisCell(value, 'danger'),
      },
      {
        key: 'logic',
        title: 'Logic',
        width: RUN_ITEM_INITIAL_COLUMN_WIDTHS.logic,
        render: (_, row: ValidationRunItem) => row.logicEvaluation?.result || '-',
      },
      {
        key: 'llm',
        title: 'LLM',
        width: RUN_ITEM_INITIAL_COLUMN_WIDTHS.llm,
        render: (_, row: ValidationRunItem) => row.llmEvaluation?.status || '-',
      },
      {
        key: 'actions',
        title: '작업',
        width: RUN_ITEM_INITIAL_COLUMN_WIDTHS.actions,
        render: (_, row: ValidationRunItem) => <Button onClick={() => handleSaveAsQuery(row)}>질의 저장</Button>,
      },
    ],
    [handleSaveAsQuery],
  );

  const historyDetailItemColumns = useMemo<ColumnsType<ValidationRunItem>>(
    () => [
      {
        key: 'ordinal',
        title: '#',
        dataIndex: 'ordinal',
        width: HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS.ordinal,
      },
      {
        key: 'queryText',
        title: '질의',
        dataIndex: 'queryText',
        width: HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS.queryText,
        ellipsis: true,
        render: (value: string) => renderEllipsisCell(value),
      },
      {
        key: 'roomRepeat',
        title: '방/반복',
        width: HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS.roomRepeat,
        render: (_, row: ValidationRunItem) => `${row.conversationRoomIndex}/${row.repeatIndex}`,
      },
      {
        key: 'executedAt',
        title: '실행시각',
        dataIndex: 'executedAt',
        width: HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS.executedAt,
        render: (value?: string | null) => formatDateTime(value || undefined),
      },
      {
        key: 'rawResponse',
        title: '응답',
        dataIndex: 'rawResponse',
        width: HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS.rawResponse,
        ellipsis: true,
        render: (value: string) => renderEllipsisCell(value),
      },
      {
        key: 'error',
        title: '오류',
        dataIndex: 'error',
        width: HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS.error,
        ellipsis: true,
        render: (value: string) => renderEllipsisCell(value, 'danger'),
      },
      {
        key: 'logic',
        title: 'Logic',
        width: HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS.logic,
        render: (_, row: ValidationRunItem) => row.logicEvaluation?.result || '-',
      },
      {
        key: 'llm',
        title: 'LLM',
        width: HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS.llm,
        render: (_, row: ValidationRunItem) => row.llmEvaluation?.status || '-',
      },
    ],
    [],
  );

  const historyColumns = useMemo<ColumnsType<ValidationRun>>(
    () => [
      {
        key: 'runId',
        title: 'Run ID',
        dataIndex: 'id',
        width: HISTORY_INITIAL_COLUMN_WIDTHS.runId,
        ellipsis: true,
        render: (value: string) => renderEllipsisCell(value),
      },
      {
        key: 'mode',
        title: '모드',
        dataIndex: 'mode',
        width: HISTORY_INITIAL_COLUMN_WIDTHS.mode,
      },
      {
        key: 'status',
        title: '상태',
        dataIndex: 'status',
        width: HISTORY_INITIAL_COLUMN_WIDTHS.status,
        render: (value: string) => <ValidationRunStatusTag status={value} />, 
      },
      {
        key: 'agentId',
        title: '에이전트',
        dataIndex: 'agentId',
        width: HISTORY_INITIAL_COLUMN_WIDTHS.agentId,
        ellipsis: true,
        render: (value: string) => renderEllipsisCell(value),
      },
      {
        key: 'items',
        title: '총/완료/오류',
        width: HISTORY_INITIAL_COLUMN_WIDTHS.items,
        render: (_, row: ValidationRun) => `${row.totalItems} / ${row.doneItems} / ${row.errorItems}`,
      },
      {
        key: 'createdAt',
        title: '생성시각',
        dataIndex: 'createdAt',
        width: HISTORY_INITIAL_COLUMN_WIDTHS.createdAt,
        render: (value?: string) => formatDateTime(value),
      },
    ],
    [],
  );

  return {
    runItemColumns,
    historyDetailItemColumns,
    historyColumns,
  };
}
