import { Button, Descriptions, Empty, Space } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useMemo } from 'react';

import { buildValidationRunExportUrl } from '../../../api/validation';
import type {
  ValidationRun,
  ValidationRunItem,
} from '../../../api/types/validation';
import { StandardDataTable } from '../../../components/common/StandardDataTable';
import { HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS } from '../constants';
import {
  getRunDisplayName,
  getRunExecutionConfigText,
  getValidationRunAggregateSummary,
} from '../utils/runDisplay';
import {
  getEvaluationStateLabel,
  getEvaluationProgressText,
} from '../utils/runProgress';
import { getExecutionStateLabel } from '../utils/runStatus';
import { DownloadOutlined, ExportOutlined } from '@ant-design/icons';

export function ValidationHistoryDetailSection({
  historyRunId,
  currentRun,
  isHistoryDetailMatched,
  runItems,
  runItemsCurrentPage,
  runItemsPageSize,
  setRunItemsCurrentPage,
  setRunItemsPageSize,
  onBackToHistory,
  onOpenInRunWorkspace,
  historyDetailItemColumns,
  testSetNameById = {},
}: {
  historyRunId?: string;
  currentRun: ValidationRun | null;
  isHistoryDetailMatched: boolean;
  runItems: ValidationRunItem[];
  runItemsCurrentPage: number;
  runItemsPageSize: number;
  setRunItemsCurrentPage: (value: number) => void;
  setRunItemsPageSize: (value: number) => void;
  onBackToHistory?: () => void;
  onOpenInRunWorkspace?: (payload: {
    runId: string;
    testSetId?: string | null;
  }) => void;
  historyDetailItemColumns: ColumnsType<ValidationRunItem>;
  testSetNameById?: Record<string, string>;
}) {
  const testSetName = useMemo(
    () =>
      currentRun?.testSetId
        ? testSetNameById?.[currentRun.testSetId] || currentRun.testSetId
        : '-',
    [currentRun, testSetNameById],
  );
  const aggregateSummary = useMemo(
    () => getValidationRunAggregateSummary(currentRun, runItems),
    [currentRun, runItems],
  );
  const executionStateLabel = useMemo(
    () => getExecutionStateLabel(currentRun),
    [currentRun],
  );
  const evaluationStateLabel = useMemo(
    () => getEvaluationStateLabel(currentRun, runItems),
    [currentRun, runItems],
  );

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <Space>
        <Button onClick={() => onBackToHistory?.()}>목록으로</Button>
        <Button
          icon={<ExportOutlined />}
          onClick={() => {
            if (!currentRun) return;
            onOpenInRunWorkspace?.({
              runId: currentRun.id,
              testSetId: currentRun.testSetId ?? undefined,
            });
          }}
          disabled={!currentRun || !isHistoryDetailMatched}
        >
          검증 실행에서 이 run 열기
        </Button>
        <Button
          type="primary"
          icon={<DownloadOutlined />}
          href={
            currentRun && isHistoryDetailMatched
              ? buildValidationRunExportUrl(currentRun.id)
              : undefined
          }
          disabled={
            !currentRun || !isHistoryDetailMatched || runItems.length === 0
          }
        >
          엑셀 다운로드
        </Button>
      </Space>

      {!historyRunId ? (
        <Empty description="선택된 Run ID가 없습니다." />
      ) : !isHistoryDetailMatched ? (
        <Empty description="Run 상세를 불러오는 중입니다." />
      ) : currentRun ? (
        <>
          <Descriptions size="small" bordered column={3}>
            <Descriptions.Item label="Run 이름">
              <span title={currentRun.id}>{getRunDisplayName(currentRun)}</span>
            </Descriptions.Item>
            <Descriptions.Item label="테스트 세트">
              {testSetName}
            </Descriptions.Item>
            <Descriptions.Item label="실행 상태">
              {executionStateLabel}
            </Descriptions.Item>
            <Descriptions.Item label="평가 상태">
              {evaluationStateLabel}
            </Descriptions.Item>
            <Descriptions.Item label="실행 구성">
              {getRunExecutionConfigText(currentRun)}
            </Descriptions.Item>
            <Descriptions.Item label="에이전트 모드">
              {currentRun.agentId}
            </Descriptions.Item>
            <Descriptions.Item label="총/완료/오류">
              {currentRun.totalItems} / {currentRun.doneItems} /{' '}
              {currentRun.errorItems}
            </Descriptions.Item>
            <Descriptions.Item label="LLM 평가 진행">
              {getEvaluationProgressText(runItems)}
            </Descriptions.Item>
            <Descriptions.Item label="평가 모델">
              {currentRun.evalModel}
            </Descriptions.Item>
            <Descriptions.Item label="평균 응답시간(초)">
              {aggregateSummary.averageResponseTimeSecText}
            </Descriptions.Item>
            <Descriptions.Item label="응답시간 p50(초)">
              {aggregateSummary.responseTimeP50SecText}
            </Descriptions.Item>
            <Descriptions.Item label="응답시간 p95(초)">
              {aggregateSummary.responseTimeP95SecText}
            </Descriptions.Item>
            <Descriptions.Item label="Logic PASS율">
              {aggregateSummary.logicPassRateText}
            </Descriptions.Item>
            <Descriptions.Item label="LLM 평가율">
              {aggregateSummary.llmDoneRateText}
            </Descriptions.Item>
            <Descriptions.Item label="LLM PASS율">
              {aggregateSummary.llmPassRateText}
            </Descriptions.Item>
            <Descriptions.Item label="LLM 평균 점수">
              {aggregateSummary.llmTotalScoreAvgText}
            </Descriptions.Item>
          </Descriptions>

          <StandardDataTable
            tableId="validation-history-detail-items"
            initialColumnWidths={HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS}
            minColumnWidth={84}
            wrapperClassName="validation-history-detail-table-wrap"
            className="query-management-table validation-history-detail-table"
            rowKey="id"
            size="small"
            tableLayout="fixed"
            dataSource={runItems}
            locale={{ emptyText: <Empty description="실행 결과 없음" /> }}
            pagination={{
              current: runItemsCurrentPage,
              pageSize: runItemsPageSize,
              total: runItems.length,
              onChange: (page, nextPageSize) => {
                if (nextPageSize !== runItemsPageSize) {
                  setRunItemsPageSize(nextPageSize);
                  setRunItemsCurrentPage(1);
                  return;
                }
                setRunItemsCurrentPage(page);
              },
            }}
            columns={historyDetailItemColumns}
          />
        </>
      ) : (
        <Empty description="런 상세를 찾을 수 없습니다." />
      )}
    </Space>
  );
}
