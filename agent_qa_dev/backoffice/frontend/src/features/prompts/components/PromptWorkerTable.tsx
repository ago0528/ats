import { Button, Space } from 'antd';

import { StandardDataTable } from '../../../components/common/StandardDataTable';
import type { PromptWorker } from '../utils/promptViewModel';

export function PromptWorkerTable({
  workers,
  loading,
  onView,
  onEdit,
  onReset,
  isWorkerFetching,
}: {
  workers: PromptWorker[];
  loading: boolean;
  onView: (workerType: string) => void;
  onEdit: (workerType: string) => void;
  onReset: (workerType: string) => void;
  isWorkerFetching: (workerType: string) => boolean;
}) {
  return (
    <StandardDataTable
      tableId="prompt-workers"
      initialColumnWidths={{ workerType: 260, description: 440, actions: 280 }}
      minColumnWidth={120}
      className="prompt-table"
      size="small"
      rowKey="workerType"
      dataSource={workers}
      loading={loading}
      columns={[
        {
          key: 'workerType',
          title: '워커',
          dataIndex: 'workerType',
          width: 260,
          ellipsis: true,
        },
        {
          key: 'description',
          title: '설명',
          dataIndex: 'description',
          width: 440,
          ellipsis: true,
        },
        {
          key: 'actions',
          title: '작업',
          dataIndex: 'actions',
          width: 280,
          render: (_: unknown, row: PromptWorker) => {
            const isFetching = isWorkerFetching(row.workerType);
            return (
              <Space size="small">
                <Button
                  onClick={() => onView(row.workerType)}
                  loading={isFetching}
                  disabled={isFetching}
                >
                  조회
                </Button>
                <Button
                  type="primary"
                  onClick={() => onEdit(row.workerType)}
                  loading={isFetching}
                  disabled={isFetching}
                >
                  수정
                </Button>
                <Button
                  onClick={() => onReset(row.workerType)}
                  disabled={isFetching}
                >
                  초기화
                </Button>
              </Space>
            );
          },
        },
      ]}
      bordered
      rowClassName="prompt-table-row"
      onRow={(row) => ({
        onDoubleClick: () => {
          onView(row.workerType);
        },
      })}
    />
  );
}
