import { Button, Descriptions, Empty, Space } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { buildValidationRunExportUrl } from '../../../api/validation';
import type { ValidationRun, ValidationRunItem } from '../../../api/types/validation';
import { StandardDataTable } from '../../../components/common/StandardDataTable';
import { formatDateTime } from '../../../shared/utils/dateTime';
import { HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS } from '../constants';
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
  onOpenInRunWorkspace?: (payload: { runId: string; testSetId?: string | null }) => void;
  historyDetailItemColumns: ColumnsType<ValidationRunItem>;
}) {
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
          href={currentRun && isHistoryDetailMatched ? buildValidationRunExportUrl(currentRun.id) : undefined}
          disabled={!currentRun || !isHistoryDetailMatched || runItems.length === 0}
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
            <Descriptions.Item label="Run ID">{currentRun.id}</Descriptions.Item>
            <Descriptions.Item label="상태">{currentRun.status}</Descriptions.Item>
            <Descriptions.Item label="생성시각">{formatDateTime(currentRun.createdAt)}</Descriptions.Item>
            <Descriptions.Item label="총/완료/오류">
              {currentRun.totalItems} / {currentRun.doneItems} / {currentRun.errorItems}
            </Descriptions.Item>
            <Descriptions.Item label="테스트 세트">{currentRun.testSetId || '-'}</Descriptions.Item>
            <Descriptions.Item label="에이전트">{currentRun.agentId}</Descriptions.Item>
            <Descriptions.Item label="모드">{currentRun.mode}</Descriptions.Item>
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
