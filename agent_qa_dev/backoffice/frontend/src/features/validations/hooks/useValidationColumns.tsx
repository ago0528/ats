import { useMemo } from 'react';
import { Tag, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import type { ValidationRun, ValidationRunItem } from '../../../api/types/validation';
import { formatDateTime } from '../../../shared/utils/dateTime';
import {
  HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS,
  HISTORY_INITIAL_COLUMN_WIDTHS,
  RUN_ITEM_INITIAL_COLUMN_WIDTHS,
} from '../constants';
import {
  getResponseTimeText,
  getRunDisplayName,
  getRunEvaluationProgressText,
  getRunExecutionConfigText,
} from '../utils/runDisplay';
import { getEvaluationStateLabel, getExecutionStateLabel } from '../utils/runStatus';

function renderEllipsisCell(value?: string, type?: 'danger') {
  const text = String(value ?? '').trim();
  if (!text) return '-';
  return (
    <Typography.Text type={type} ellipsis={{ tooltip: text }} style={{ display: 'block', width: '100%' }}>
      {text}
    </Typography.Text>
  );
}

const normalizeStatus = (value?: string) => String(value ?? '').trim().toUpperCase();

const renderStateTag = (value: string, color: string) => (
  <Tag color={color} style={{ marginInlineEnd: 0 }}>
    {value}
  </Tag>
);

const getRunStateTagColor = (state: string) => {
  if (state === '실행완료' || state === '평가완료') {
    return 'success';
  }

  switch (state) {
    case '미생성':
      return 'default';
    case '실행대기':
      return 'warning';
    case '평가대기':
      return 'warning';
    case '실행중':
      return 'processing';
    case '평가중':
      return 'processing';
    case '실행실패':
      return 'error';
    default:
      return 'default';
  }
};

const getLogicResultTag = (value?: string) => {
  const status = normalizeStatus(value);
  if (!status) {
    return <span>-</span>;
  }
  if (status === 'PASS') {
    return renderStateTag(status, 'success');
  }
  if (status.startsWith('FAIL')) {
    return renderStateTag(status, 'error');
  }
  if (status.startsWith('SKIPPED')) {
    return renderStateTag(status, 'default');
  }
  return renderStateTag(status, 'default');
};

const getLlmEvaluationTag = (value?: string) => {
  const status = normalizeStatus(value);
  if (!status) {
    return <span>-</span>;
  }
  if (status.startsWith('DONE')) {
    return renderStateTag('DONE', 'success');
  }
  if (status.startsWith('SKIPPED')) {
    return renderStateTag(status, 'default');
  }
  if (status.startsWith('FAILED')) {
    return (
      <Tooltip title={status}>
        {renderStateTag('FAILED', 'error')}
      </Tooltip>
    );
  }
  if (status === 'PENDING') {
    return renderStateTag('PENDING', 'warning');
  }
  return renderStateTag(status, 'processing');
};

type UseValidationColumnsOptions = {
  testSetNameById?: Record<string, string>;
};

export function useValidationColumns(options: UseValidationColumnsOptions = {}) {
  const testSetNameById = options.testSetNameById ?? {};

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
        render: (_, row: ValidationRunItem) => getLogicResultTag(row.logicEvaluation?.result),
      },
      {
        key: 'llm',
        title: 'LLM',
        width: RUN_ITEM_INITIAL_COLUMN_WIDTHS.llm,
        render: (_, row: ValidationRunItem) => getLlmEvaluationTag(row.llmEvaluation?.status),
      },
    ],
    [],
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
        key: 'responseTimeSec',
        title: '총 응답시간',
        width: HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS.responseTimeSec,
        render: (_, row: ValidationRunItem) => getResponseTimeText(row.responseTimeSec, row.latencyMs),
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
        render: (_, row: ValidationRunItem) => getLogicResultTag(row.logicEvaluation?.result),
      },
      {
        key: 'llm',
        title: 'LLM',
        width: HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS.llm,
        render: (_, row: ValidationRunItem) => getLlmEvaluationTag(row.llmEvaluation?.status),
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
        key: 'runName',
        title: 'Run 이름',
        dataIndex: 'name',
        width: HISTORY_INITIAL_COLUMN_WIDTHS.runName,
        render: (value: string, row: ValidationRun) => renderEllipsisCell(value || getRunDisplayName(row)),
      },
      {
        key: 'testSet',
        title: '테스트 세트',
        dataIndex: 'testSetId',
        width: HISTORY_INITIAL_COLUMN_WIDTHS.testSet,
        render: (value?: string | null) => {
          if (!value) return '-';
          return renderEllipsisCell(testSetNameById[value] || value);
        },
      },
      {
        key: 'status',
        title: '실행 상태',
        width: HISTORY_INITIAL_COLUMN_WIDTHS.executionStatus,
        render: (_, row) => {
          const stateLabel = getExecutionStateLabel(row);
          return (
            <Tooltip title={stateLabel}>
              {renderStateTag(stateLabel, getRunStateTagColor(stateLabel))}
            </Tooltip>
          );
        },
      },
      {
        key: 'evaluationStatus',
        title: '평가 상태',
        width: HISTORY_INITIAL_COLUMN_WIDTHS.evaluationStatus,
        render: (_, row) => {
          const stateLabel = getEvaluationStateLabel(row);
          return (
            <Tooltip title={stateLabel}>
              {renderStateTag(stateLabel, getRunStateTagColor(stateLabel))}
            </Tooltip>
          );
        },
      },
      {
        key: 'executionConfig',
        title: '실행 구성',
        dataIndex: 'id',
        width: HISTORY_INITIAL_COLUMN_WIDTHS.executionConfig,
        render: (_, row: ValidationRun) => getRunExecutionConfigText(row),
      },
      {
        key: 'agentMode',
        title: '에이전트 모드',
        dataIndex: 'agentId',
        width: HISTORY_INITIAL_COLUMN_WIDTHS.agentMode,
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
        key: 'llmProgress',
        title: 'LLM 평가 진행',
        width: HISTORY_INITIAL_COLUMN_WIDTHS.llmEvalProgress,
        render: (_, row: ValidationRun) => getRunEvaluationProgressText(row),
      },
      {
        key: 'evalModel',
        title: '평가 모델',
        dataIndex: 'evalModel',
        width: HISTORY_INITIAL_COLUMN_WIDTHS.evalModel,
        ellipsis: true,
      },
    ],
    [testSetNameById],
  );

  return {
    runItemColumns,
    historyDetailItemColumns,
    historyColumns,
  };
}
