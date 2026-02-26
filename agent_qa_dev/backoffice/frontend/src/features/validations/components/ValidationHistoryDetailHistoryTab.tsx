import {
  Alert,
  Button,
  Col,
  DatePicker,
  Row,
  Select,
  Space,
  Statistic,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useMemo } from 'react';
import { EyeOutlined } from '@ant-design/icons';

import { StandardDataTable } from '../../../components/common/StandardDataTable';
import {
  HISTORY_SLOW_THRESHOLD_SEC,
  HISTORY_TAB_INITIAL_COLUMN_WIDTHS,
} from '../constants';
import {
  buildHistorySummary,
  filterHistoryRows,
  sortHistoryRows,
  type HistoryRowView,
  type HistoryTableFilters,
} from '../utils/historyDetailRows';
import {
  AGGREGATING_LABEL,
  getRunItemStatusColor,
  NOT_AGGREGATED_LABEL,
} from '../utils/historyDetailDisplay';
import type { ValidationRun } from '../../../api/types/validation';

export function ValidationHistoryDetailHistoryTab({
  currentRun,
  rows,
  filters,
  onChangeFilters,
  currentPage,
  pageSize,
  setCurrentPage,
  setPageSize,
  onOpenRow,
}: {
  currentRun: ValidationRun | null;
  rows: HistoryRowView[];
  filters: HistoryTableFilters;
  onChangeFilters: (next: HistoryTableFilters) => void;
  currentPage: number;
  pageSize: number;
  setCurrentPage: (value: number) => void;
  setPageSize: (value: number) => void;
  onOpenRow: (row: HistoryRowView) => void;
}) {
  const summary = useMemo(
    () => buildHistorySummary(currentRun, rows),
    [currentRun, rows],
  );
  const filteredRows = useMemo(
    () => filterHistoryRows(sortHistoryRows(rows), filters),
    [rows, filters],
  );

  const columns = useMemo<ColumnsType<HistoryRowView>>(
    () => [
      {
        key: 'errorSummary',
        title: '오류',
        dataIndex: 'errorSummary',
        width: HISTORY_TAB_INITIAL_COLUMN_WIDTHS.errorSummary,
        ellipsis: true,
        render: (value: string, row) => {
          if (!row.hasError) {
            return <Typography.Text type="secondary">정상</Typography.Text>;
          }
          return (
            <Typography.Text type="danger" ellipsis={{ tooltip: value }}>
              {value}
            </Typography.Text>
          );
        },
      },
      {
        key: 'responseTimeSec',
        title: '총 응답시간',
        dataIndex: 'responseTimeText',
        width: HISTORY_TAB_INITIAL_COLUMN_WIDTHS.responseTimeSec,
        render: (value: string) => value || NOT_AGGREGATED_LABEL,
      },
      {
        key: 'executedAt',
        title: '실행시각',
        dataIndex: 'executedAtText',
        width: HISTORY_TAB_INITIAL_COLUMN_WIDTHS.executedAt,
      },
      {
        key: 'status',
        title: '상태',
        width: HISTORY_TAB_INITIAL_COLUMN_WIDTHS.status,
        render: (_, row) => (
          <Tag color={getRunItemStatusColor(row.status)}>{row.statusLabel}</Tag>
        ),
      },
      {
        key: 'detail',
        title: '상세보기',
        width: HISTORY_TAB_INITIAL_COLUMN_WIDTHS.detail,
        render: (_, row) => (
          <Button
            type="text"
            icon={<EyeOutlined />}
            onClick={(event) => {
              event.stopPropagation();
              onOpenRow(row);
            }}
          />
        ),
      },
    ],
    [onOpenRow],
  );

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Row gutter={[12, 12]} className="validation-kpi-grid">
        <Col xs={24} sm={12} md={8} lg={4}>
          <div className="validation-metric-tile">
            <Statistic title="실행 상태" value={summary.executionStatusText} />
          </div>
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <div className="validation-metric-tile">
            <Statistic title="실행 시간" value={summary.executionTimeText} />
          </div>
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <div className="validation-metric-tile">
            <Statistic title="실행 건수" value={summary.totalRowsText} />
          </div>
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <div className="validation-metric-tile">
            <Statistic title="오류 건수" value={summary.errorRowsText} />
          </div>
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <div className="validation-metric-tile">
            <Statistic title="응답속도 p50" value={summary.p50Text} />
          </div>
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <div className="validation-metric-tile">
            <Statistic title="응답속도 p95" value={summary.p95Text} />
          </div>
        </Col>
      </Row>

      <div className="validation-section-block">
        <div className="validation-section-header">
          <Typography.Title level={5} style={{ margin: 0 }}>
            테스트 이력
          </Typography.Title>
          <Space wrap>
            <Select
              value={filters.status}
              style={{ width: 180 }}
              options={[
                { label: '전체 상태', value: 'all' },
                { label: '성공', value: 'success' },
                { label: '실패', value: 'failed' },
                { label: '중단', value: 'stopped' },
                { label: '대기', value: 'pending' },
              ]}
              onChange={(nextStatus) => {
                onChangeFilters({
                  ...filters,
                  status: nextStatus,
                });
              }}
            />
            <Button
              type={filters.onlyErrors ? 'primary' : 'default'}
              onClick={() =>
                onChangeFilters({
                  ...filters,
                  onlyErrors: !filters.onlyErrors,
                })
              }
            >
              오류 이력 확인
            </Button>
            <Button
              type={filters.onlySlow ? 'primary' : 'default'}
              onClick={() =>
                onChangeFilters({
                  ...filters,
                  onlySlow: !filters.onlySlow,
                })
              }
            >
              느림({HISTORY_SLOW_THRESHOLD_SEC.toFixed(0)}s+)
            </Button>
            <DatePicker.RangePicker
              value={filters.dateRange as any}
              format="YYYY-MM-DD"
              onChange={(nextValue) =>
                onChangeFilters({
                  ...filters,
                  dateRange: nextValue
                    ? [
                        nextValue[0]
                          ? new Date(
                              (
                                nextValue[0] as { valueOf: () => number }
                              ).valueOf(),
                            )
                          : null,
                        nextValue[1]
                          ? new Date(
                              (
                                nextValue[1] as { valueOf: () => number }
                              ).valueOf(),
                            )
                          : null,
                      ]
                    : [null, null],
                })
              }
            />
          </Space>
        </div>

        {String(currentRun?.status || '').toUpperCase() === 'RUNNING' ? (
          <Alert
            type="info"
            showIcon
            message={AGGREGATING_LABEL}
            description="실행 중인 Run은 일부 집계가 계속 갱신됩니다."
          />
        ) : null}

        <StandardDataTable<HistoryRowView>
          tableId="validation-history-detail-history-tab"
          initialColumnWidths={HISTORY_TAB_INITIAL_COLUMN_WIDTHS}
          minColumnWidth={84}
          wrapperClassName="validation-history-detail-table-wrap"
          className="query-management-table validation-history-detail-table"
          rowKey="key"
          size="small"
          tableLayout="fixed"
          dataSource={filteredRows}
          columns={columns}
          onRow={(row) => ({
            onClick: () => onOpenRow(row),
            style: { cursor: 'pointer' },
          })}
          pagination={{
            current: currentPage,
            pageSize,
            total: filteredRows.length,
            onChange: (nextPage, nextPageSize) => {
              if (nextPageSize !== pageSize) {
                setPageSize(nextPageSize);
                setCurrentPage(1);
                return;
              }
              setCurrentPage(nextPage);
            },
          }}
        />
      </div>
    </Space>
  );
}
