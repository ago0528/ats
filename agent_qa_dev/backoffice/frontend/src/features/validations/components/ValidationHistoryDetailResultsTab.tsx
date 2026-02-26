import { Alert, Button, Col, Collapse, Descriptions, Row, Select, Space, Tag, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useMemo } from 'react';
import { InfoCircleOutlined } from '@ant-design/icons';

import { StandardDataTable } from '../../../components/common/StandardDataTable';
import {
  HISTORY_SLOW_THRESHOLD_SEC,
  RESULT_LOW_SCORE_THRESHOLD,
  RESULTS_TAB_INITIAL_COLUMN_WIDTHS,
} from '../constants';
import {
  buildResultsKpi,
  filterResultsRows,
  sortResultsRows,
  type ResultsFilters,
  type ResultsRowView,
  type ResultsTablePreset,
} from '../utils/historyDetailRows';
import {
  formatPercentText,
  formatSecText,
  getRunItemStatusColor,
  NOT_AGGREGATED_LABEL,
} from '../utils/historyDetailDisplay';
import type { ValidationRun, ValidationRunItem } from '../../../api/types/validation';

type FocusMetric = ResultsFilters['focusMetric'];

const PRESET_OPTIONS: Array<{ label: string; value: ResultsTablePreset }> = [
  { label: '기본 보기', value: 'default' },
  { label: '저점 보기', value: 'low' },
  { label: '오류 보기', value: 'abnormal' },
  { label: '느림 보기', value: 'slow' },
];

function toMetricValue(score: number | null, formatter?: (value: number | null) => string) {
  if (formatter) {
    return formatter(score);
  }
  if (score === null) return NOT_AGGREGATED_LABEL;
  return score.toFixed(2);
}

function MetricTile({
  title,
  value,
  primaryText,
  notAggregatedReason,
  selected,
  onClick,
}: {
  title: string;
  value: string;
  primaryText: string;
  notAggregatedReason?: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`validation-metric-tile validation-metric-tile-clickable${selected ? ' is-selected' : ''}`}
      onClick={onClick}
    >
      <Typography.Text className="validation-kpi-tile-title">{title}</Typography.Text>
      <div className="validation-kpi-tile-value-row">
        <Typography.Text className="validation-kpi-tile-value">{value}</Typography.Text>
        {notAggregatedReason ? (
          <Tooltip title={notAggregatedReason}>
            <InfoCircleOutlined className="validation-kpi-tile-info" />
          </Tooltip>
        ) : null}
      </div>
      <Typography.Text type="secondary">{primaryText}</Typography.Text>
    </button>
  );
}

export function ValidationHistoryDetailResultsTab({
  currentRun,
  runItems,
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
  runItems: ValidationRunItem[];
  rows: ResultsRowView[];
  filters: ResultsFilters;
  onChangeFilters: (next: ResultsFilters) => void;
  currentPage: number;
  pageSize: number;
  setCurrentPage: (value: number) => void;
  setPageSize: (value: number) => void;
  onOpenRow: (row: ResultsRowView) => void;
}) {
  const kpi = useMemo(() => buildResultsKpi(currentRun, runItems), [currentRun, runItems]);
  const filteredRows = useMemo(
    () => filterResultsRows(sortResultsRows(rows), filters),
    [rows, filters],
  );

  const columns = useMemo<ColumnsType<ResultsRowView>>(
    () => [
      {
        key: 'queryText',
        title: '질의',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.queryText,
        ellipsis: true,
        render: (_, row) => row.item.queryText || '-',
      },
      {
        key: 'totalScore',
        title: '총 점수',
        dataIndex: 'totalScoreText',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.totalScore,
      },
      {
        key: 'intent',
        title: '의도 충족',
        dataIndex: 'intentScoreText',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.intent,
      },
      {
        key: 'accuracy',
        title: '정확성',
        dataIndex: 'accuracyScoreText',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.accuracy,
      },
      {
        key: 'consistency',
        title: '일관성',
        dataIndex: 'consistencyScoreText',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.consistency,
      },
      {
        key: 'speed',
        title: '응답 속도',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.speed,
        render: (_, row) => `${row.speedText} · ${row.latencyClassLabel}`,
      },
      {
        key: 'stability',
        title: '안정성',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.stability,
        render: (_, row) => (
          <Tag color={getRunItemStatusColor(row.abnormal ? 'failed' : 'success')}>
            {row.stabilityScoreText}
          </Tag>
        ),
      },
    ],
    [],
  );

  const toggleFocusMetric = (metric: FocusMetric) => {
    onChangeFilters({
      ...filters,
      focusMetric: filters.focusMetric === metric ? null : metric,
    });
  };

  const clearFilters = () => {
    onChangeFilters({
      tablePreset: 'default',
      onlyLowScore: false,
      onlyAbnormal: false,
      onlySlow: false,
      onlyLatencyUnclassified: false,
      scoreBucketFilter: null,
      focusMetric: null,
    });
  };

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Row gutter={[12, 12]} className="validation-kpi-grid validation-results-kpi-grid">
        <Col xs={24} sm={12} md={8} lg={4}>
          <MetricTile
            title="의도 충족"
            selected={filters.focusMetric === 'intent'}
            onClick={() => toggleFocusMetric('intent')}
            value={toMetricValue(kpi.intent.score)}
            primaryText={`대상 질의 ${kpi.intent.sampleCount}개`}
            notAggregatedReason={
              kpi.intent.score === null ? (kpi.intent.notAggregatedReason || undefined) : undefined
            }
          />
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <MetricTile
            title="정확성"
            selected={filters.focusMetric === 'accuracy'}
            onClick={() => toggleFocusMetric('accuracy')}
            value={toMetricValue(kpi.accuracy.score)}
            primaryText={`대상 질의 ${kpi.accuracy.sampleCount}개`}
            notAggregatedReason={
              kpi.accuracy.score === null ? (kpi.accuracy.notAggregatedReason || undefined) : undefined
            }
          />
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          {/*
            consistency는 sampleCount가 0이면 PENDING(=집계 없음) 상태로 렌더링한다.
          */}
          <MetricTile
            title="일관성"
            selected={filters.focusMetric === 'consistency'}
            onClick={() => toggleFocusMetric('consistency')}
            value={
              kpi.consistency.status === 'PENDING'
                ? NOT_AGGREGATED_LABEL
                : toMetricValue(kpi.consistency.score)
            }
            primaryText={`대상 질의 ${kpi.consistency.sampleCount}개`}
            notAggregatedReason={
              kpi.consistency.status === 'PENDING'
                ? (kpi.consistency.notAggregatedReason || undefined)
                : undefined
            }
          />
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <MetricTile
            title="응답 속도 (싱글)"
            selected={filters.focusMetric === 'speed'}
            onClick={() => toggleFocusMetric('speed')}
            value={toMetricValue(kpi.speedSingle.avgSec, formatSecText)}
            primaryText={`대상 질의 ${kpi.speedSingle.sampleCount}개`}
            notAggregatedReason={
              kpi.speedSingle.avgSec === null ? (kpi.speedSingle.notAggregatedReason || undefined) : undefined
            }
          />
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <MetricTile
            title="응답 속도 (멀티)"
            selected={filters.focusMetric === 'speed'}
            onClick={() => toggleFocusMetric('speed')}
            value={toMetricValue(kpi.speedMulti.avgSec, formatSecText)}
            primaryText={`대상 질의 ${kpi.speedMulti.sampleCount}개`}
            notAggregatedReason={
              kpi.speedMulti.avgSec === null ? (kpi.speedMulti.notAggregatedReason || undefined) : undefined
            }
          />
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <MetricTile
            title="안정성"
            selected={filters.focusMetric === 'stability'}
            onClick={() => toggleFocusMetric('stability')}
            value={toMetricValue(kpi.stability.score)}
            primaryText={`에러율 ${formatPercentText(kpi.stability.errorRate)}`}
            notAggregatedReason={
              kpi.stability.score === null ? (kpi.stability.notAggregatedReason || undefined) : undefined
            }
          />
        </Col>
      </Row>

      <Collapse
        items={[
          {
            key: 'meta',
            label: 'Run 메타',
            children: (
              <Descriptions size="small" bordered column={2}>
                <Descriptions.Item label="총 건수">{kpi.runMeta.totalRows}</Descriptions.Item>
                <Descriptions.Item label="완료 건수">{kpi.runMeta.doneRows}</Descriptions.Item>
                <Descriptions.Item label="오류 건수">{kpi.runMeta.errorRows}</Descriptions.Item>
                <Descriptions.Item label="LLM 평가 건수">{kpi.runMeta.llmDoneRows}</Descriptions.Item>
                <Descriptions.Item label="평균 응답시간">{kpi.runMeta.averageResponseTimeText}</Descriptions.Item>
                <Descriptions.Item label="응답시간 p50">{kpi.runMeta.responseTimeP50Text}</Descriptions.Item>
                <Descriptions.Item label="응답시간 p95">{kpi.runMeta.responseTimeP95Text}</Descriptions.Item>
                <Descriptions.Item label="Logic PASS율">{kpi.runMeta.logicPassRateText}</Descriptions.Item>
                <Descriptions.Item label="LLM 평가율">{kpi.runMeta.llmDoneRateText}</Descriptions.Item>
                <Descriptions.Item label="LLM PASS율">{kpi.runMeta.llmPassRateText}</Descriptions.Item>
                <Descriptions.Item label="LLM 평균 점수">{kpi.runMeta.llmTotalScoreAvgText}</Descriptions.Item>
              </Descriptions>
            ),
          },
        ]}
      />

      {kpi.latencyUnclassifiedCount > 0 ? (
        <Alert
          type="warning"
          showIcon
          message={`미분류 응답 속도 데이터 ${kpi.latencyUnclassifiedCount}건이 있습니다.`}
          action={
            <Button
              size="small"
              type="link"
              onClick={() =>
                onChangeFilters({
                  ...filters,
                  onlyLatencyUnclassified: true,
                })
              }
            >
              미분류 항목만 보기
            </Button>
          }
        />
      ) : null}

      <div className="validation-section-block">
        <div className="validation-section-header">
          <Typography.Title level={5} style={{ margin: 0 }}>
            결과 테이블
          </Typography.Title>
          <Space wrap>
            <Select
              value={filters.tablePreset}
              options={PRESET_OPTIONS}
              style={{ width: 140 }}
              onChange={(tablePreset) =>
                onChangeFilters({
                  ...filters,
                  tablePreset,
                })
              }
            />
            <Button
              type={filters.onlyLowScore ? 'primary' : 'default'}
              onClick={() =>
                onChangeFilters({
                  ...filters,
                  onlyLowScore: !filters.onlyLowScore,
                })
              }
            >
              저점({RESULT_LOW_SCORE_THRESHOLD}점 이하)
            </Button>
            <Button
              type={filters.onlyAbnormal ? 'primary' : 'default'}
              onClick={() =>
                onChangeFilters({
                  ...filters,
                  onlyAbnormal: !filters.onlyAbnormal,
                })
              }
            >
              오류/비정상
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
            <Tooltip title="전체 필터 초기화">
              <Button onClick={clearFilters}>초기화</Button>
            </Tooltip>
          </Space>
        </div>

        <StandardDataTable<ResultsRowView>
          tableId="validation-history-detail-results-tab"
          initialColumnWidths={RESULTS_TAB_INITIAL_COLUMN_WIDTHS}
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
