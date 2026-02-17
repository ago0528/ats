import { StandardDataTable } from '../../../components/common/StandardDataTable';
import { HISTORY_INITIAL_COLUMN_WIDTHS } from '../constants';
import type { ValidationRun } from '../../../api/types/validation';
import type { ColumnsType } from 'antd/es/table';

export function ValidationHistorySection({
  runs,
  historyCurrentPage,
  historyPageSize,
  setHistoryCurrentPage,
  setHistoryPageSize,
  onOpenHistoryRunDetail,
  historyColumns,
}: {
  runs: ValidationRun[];
  historyCurrentPage: number;
  historyPageSize: number;
  setHistoryCurrentPage: (value: number) => void;
  setHistoryPageSize: (value: number) => void;
  onOpenHistoryRunDetail?: (runId: string) => void;
  historyColumns: ColumnsType<ValidationRun>;
}) {
  return (
    <StandardDataTable
      tableId="validation-history"
      initialColumnWidths={HISTORY_INITIAL_COLUMN_WIDTHS}
      minColumnWidth={96}
      wrapperClassName="validation-history-table-wrap"
      className="query-management-table validation-history-table"
      rowKey="id"
      size="small"
      tableLayout="fixed"
      dataSource={runs}
      onRow={onOpenHistoryRunDetail
        ? (row) => ({
          onClick: () => onOpenHistoryRunDetail(row.id),
          style: { cursor: 'pointer' },
        })
        : undefined}
      pagination={{
        current: historyCurrentPage,
        pageSize: historyPageSize,
        total: runs.length,
        onChange: (page, nextPageSize) => {
          if (nextPageSize !== historyPageSize) {
            setHistoryPageSize(nextPageSize);
            setHistoryCurrentPage(1);
            return;
          }
          setHistoryCurrentPage(page);
        },
      }}
      columns={historyColumns}
    />
  );
}
