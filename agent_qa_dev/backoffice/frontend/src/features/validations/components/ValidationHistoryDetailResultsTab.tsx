import {
  Button,
  Col,
  Collapse,
  Descriptions,
  Row,
  Select,
  Space,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useMemo } from 'react';
import { InfoCircleOutlined, WarningOutlined } from '@ant-design/icons';

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
  NOT_AGGREGATED_LABEL,
} from '../utils/historyDetailDisplay';
import type {
  ValidationRun,
  ValidationRunItem,
} from '../../../api/types/validation';

type FocusMetric = ResultsFilters['focusMetric'];

const PRESET_OPTIONS: Array<{ label: string; value: ResultsTablePreset }> = [
  { label: '기본 보기', value: 'default' },
  { label: `총 점수 ${RESULT_LOW_SCORE_THRESHOLD}점 이하`, value: 'low' },
  { label: '오류/비정상', value: 'abnormal' },
  { label: `응답 ${HISTORY_SLOW_THRESHOLD_SEC.toFixed(0)}초 이상`, value: 'slow' },
];

const FOCUS_METRIC_LABELS: Record<NonNullable<FocusMetric>, string> = {
  intent: '의도 충족',
  accuracy: '정확성',
  consistency: '일관성',
  speed: '응답 속도',
  stability: '안정성',
};

const compareText = (left?: string | null, right?: string | null) =>
  String(left || '').localeCompare(String(right || ''), 'ko');

const compareNullableNumber = (left?: number | null, right?: number | null) => {
  if (left === null || left === undefined)
    return right === null || right === undefined ? 0 : 1;
  if (right === null || right === undefined) return -1;
  return left - right;
};

const LATENCY_CLASS_TAG_COLOR: Record<ResultsRowView['latencyClass'], string> =
  {
    SINGLE: 'blue',
    MULTI: 'purple',
    UNCLASSIFIED: 'default',
  };

function toMetricValue(
  score: number | null,
  formatter?: (value: number | null) => string,
) {
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
  valueTooltip,
  notAggregatedReason,
  selected,
  onClick,
}: {
  title: string;
  value: string;
  primaryText: string;
  valueTooltip?: string;
  notAggregatedReason?: string;
  selected: boolean;
  onClick: () => void;
}) {
  const infoTooltipLines = [valueTooltip, notAggregatedReason].filter(Boolean);
  return (
    <button
      type="button"
      className={`validation-metric-tile validation-metric-tile-clickable${selected ? ' is-selected' : ''}`}
      onClick={onClick}
    >
      <Typography.Text className="validation-kpi-tile-title">
        {title}
      </Typography.Text>
      <div className="validation-kpi-tile-value-row">
        <Typography.Text className="validation-kpi-tile-value">
          {value}
        </Typography.Text>
        {infoTooltipLines.length > 0 ? (
          <Tooltip
            title={(
              <span style={{ whiteSpace: 'pre-line' }}>
                {infoTooltipLines.join('\n')}
              </span>
            )}
          >
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
  const kpi = useMemo(
    () => buildResultsKpi(currentRun, runItems),
    [currentRun, runItems],
  );
  const filteredRows = useMemo(
    () => filterResultsRows(sortResultsRows(rows), filters),
    [rows, filters],
  );

  const columns = useMemo<ColumnsType<ResultsRowView>>(
    () => [
      {
        key: 'ordinal',
        title: '#',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.ordinal,
        fixed: 'left',
        render: (_, row) => row.item.ordinal,
        sorter: (left, right) => left.item.ordinal - right.item.ordinal,
        defaultSortOrder: 'ascend',
      },
      {
        key: 'queryText',
        title: '질의',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.queryText,
        fixed: 'left',
        ellipsis: true,
        sorter: (left, right) =>
          compareText(left.item.queryText, right.item.queryText),
        render: (_, row) => row.item.queryText || '-',
      },
      {
        key: 'totalScore',
        title: '총 점수',
        dataIndex: 'totalScoreText',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.totalScore,
        sorter: (left, right) =>
          compareNullableNumber(left.totalScore, right.totalScore),
      },
      {
        key: 'intent',
        title: '의도 충족',
        dataIndex: 'intentScoreText',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.intent,
        sorter: (left, right) =>
          compareNullableNumber(left.intentScore, right.intentScore),
      },
      {
        key: 'accuracy',
        title: '정확성',
        dataIndex: 'accuracyScoreText',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.accuracy,
        sorter: (left, right) =>
          compareNullableNumber(left.accuracyScore, right.accuracyScore),
      },
      {
        key: 'consistency',
        title: '일관성',
        dataIndex: 'consistencyScoreText',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.consistency,
        sorter: (left, right) =>
          compareNullableNumber(left.consistencyScore, right.consistencyScore),
      },
      {
        key: 'latencySingle',
        title: '응답 속도 (싱글)',
        dataIndex: 'latencySingleScoreText',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.speedSingle,
        sorter: (left, right) =>
          compareNullableNumber(
            left.latencySingleScore,
            right.latencySingleScore,
          ),
      },
      {
        key: 'latencyMulti',
        title: '응답 속도 (멀티)',
        dataIndex: 'latencyMultiScoreText',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.speedMulti,
        sorter: (left, right) =>
          compareNullableNumber(
            left.latencyMultiScore,
            right.latencyMultiScore,
          ),
      },
      {
        key: 'stability',
        title: '안정성',
        dataIndex: 'stabilityScoreText',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.stability,
        sorter: (left, right) =>
          compareNullableNumber(left.stabilityScore, right.stabilityScore),
      },
      {
        key: 'speed',
        title: '응답 속도',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.speed,
        sorter: (left, right) => {
          const speedCompare = compareNullableNumber(
            left.speedSec,
            right.speedSec,
          );
          if (speedCompare !== 0) return speedCompare;
          return compareText(left.latencyClassLabel, right.latencyClassLabel);
        },
        render: (_, row) => (
          <Space size={6}>
            <Typography.Text>{row.speedText}</Typography.Text>
            <Tag
              color={LATENCY_CLASS_TAG_COLOR[row.latencyClass]}
              style={{ marginInlineEnd: 0 }}
            >
              {row.latencyClassLabel}
            </Tag>
          </Space>
        ),
      },
      {
        key: 'evaluatedAt',
        title: '평가일시',
        dataIndex: 'evaluatedAtText',
        width: RESULTS_TAB_INITIAL_COLUMN_WIDTHS.evaluatedAt,
        sorter: (left, right) => left.evaluatedAtTs - right.evaluatedAtTs,
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

  const clearAllFilters = () => {
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

  const activeFilterTags = useMemo(() => {
    const tags: Array<{ key: string; label: string; clear: () => void }> = [];
    if (filters.tablePreset !== 'default') {
      const presetLabel = PRESET_OPTIONS.find((option) => option.value === filters.tablePreset)?.label || filters.tablePreset;
      tags.push({
        key: 'preset',
        label: `프리셋: ${presetLabel}`,
        clear: () => onChangeFilters({ ...filters, tablePreset: 'default' }),
      });
    }
    if (filters.onlyLatencyUnclassified) {
      tags.push({
        key: 'latencyUnclassified',
        label: '미분류 응답 속도만',
        clear: () => onChangeFilters({ ...filters, onlyLatencyUnclassified: false }),
      });
    }
    if (filters.focusMetric) {
      tags.push({
        key: 'focusMetric',
        label: `지표 포커스: ${FOCUS_METRIC_LABELS[filters.focusMetric]}`,
        clear: () => onChangeFilters({ ...filters, focusMetric: null }),
      });
    }
    if (filters.scoreBucketFilter !== null) {
      tags.push({
        key: 'scoreBucket',
        label: `총점 버킷: ${filters.scoreBucketFilter}점`,
        clear: () => onChangeFilters({ ...filters, scoreBucketFilter: null }),
      });
    }
    if (filters.onlyLowScore) {
      tags.push({
        key: 'onlyLowScore',
        label: `총 점수 ${RESULT_LOW_SCORE_THRESHOLD}점 이하`,
        clear: () => onChangeFilters({ ...filters, onlyLowScore: false }),
      });
    }
    if (filters.onlyAbnormal) {
      tags.push({
        key: 'onlyAbnormal',
        label: '오류/비정상',
        clear: () => onChangeFilters({ ...filters, onlyAbnormal: false }),
      });
    }
    if (filters.onlySlow) {
      tags.push({
        key: 'onlySlow',
        label: `응답 ${HISTORY_SLOW_THRESHOLD_SEC.toFixed(0)}초 이상`,
        clear: () => onChangeFilters({ ...filters, onlySlow: false }),
      });
    }
    return tags;
  }, [filters, onChangeFilters]);

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Row
        gutter={[12, 12]}
        className="validation-kpi-grid validation-results-kpi-grid"
      >
        <Col xs={24} sm={12} md={8} lg={4}>
          <MetricTile
            title="의도 충족"
            selected={filters.focusMetric === 'intent'}
            onClick={() => toggleFocusMetric('intent')}
            value={toMetricValue(kpi.intent.score)}
            primaryText={`대상 질의 ${kpi.intent.sampleCount}개`}
            valueTooltip={`점수 기준: intent 점수(0~5) 평균\n대상: intent 점수가 있는 질의`}
            notAggregatedReason={
              kpi.intent.score === null
                ? kpi.intent.notAggregatedReason || undefined
                : undefined
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
            valueTooltip={`점수 기준: accuracy 점수(0~5) 평균\n대상: accuracy 점수가 있는 질의`}
            notAggregatedReason={
              kpi.accuracy.score === null
                ? kpi.accuracy.notAggregatedReason || undefined
                : undefined
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
            valueTooltip={`점수 기준: 동일 질의 반복 실행의 일관성 점수(0~5) 평균\n대상: 반복 비교 가능한 질의`}
            notAggregatedReason={
              kpi.consistency.status === 'PENDING'
                ? kpi.consistency.notAggregatedReason || undefined
                : undefined
            }
          />
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <MetricTile
            title="응답 속도 (싱글)"
            selected={filters.focusMetric === 'speed'}
            onClick={() => toggleFocusMetric('speed')}
            value={toMetricValue(kpi.speedSingle.score)}
            primaryText={`대상 질의 ${kpi.speedSingle.sampleCount}개`}
            valueTooltip={`점수 기준: latencySingle 점수(0~5) 평균${kpi.speedSingle.avgSec === null ? '' : `\n평균: ${formatSecText(kpi.speedSingle.avgSec)}`}`}
            notAggregatedReason={
              kpi.speedSingle.score === null
                ? kpi.speedSingle.notAggregatedReason || undefined
                : undefined
            }
          />
        </Col>
        <Col xs={24} sm={12} md={8} lg={4}>
          <MetricTile
            title="응답 속도 (멀티)"
            selected={filters.focusMetric === 'speed'}
            onClick={() => toggleFocusMetric('speed')}
            value={toMetricValue(kpi.speedMulti.score)}
            primaryText={`대상 질의 ${kpi.speedMulti.sampleCount}개`}
            valueTooltip={`점수 기준: latencyMulti 점수(0~5) 평균${kpi.speedMulti.avgSec === null ? '' : `\n평균: ${formatSecText(kpi.speedMulti.avgSec)}`}`}
            notAggregatedReason={
              kpi.speedMulti.score === null
                ? kpi.speedMulti.notAggregatedReason || undefined
                : undefined
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
            valueTooltip={`점수 기준: stability 점수(0~5) 평균\n대상: 전체 질의`}
            notAggregatedReason={
              kpi.stability.score === null
                ? kpi.stability.notAggregatedReason || undefined
                : undefined
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
                <Descriptions.Item label="총 건수">
                  {kpi.runMeta.totalRows}
                </Descriptions.Item>
                <Descriptions.Item label="완료 건수">
                  {kpi.runMeta.doneRows}
                </Descriptions.Item>
                <Descriptions.Item label="오류 건수">
                  {kpi.runMeta.errorRows}
                </Descriptions.Item>
                <Descriptions.Item label="LLM 평가 건수">
                  {kpi.runMeta.llmDoneRows}
                </Descriptions.Item>
                <Descriptions.Item label="평균 응답시간">
                  {kpi.runMeta.averageResponseTimeText}
                </Descriptions.Item>
                <Descriptions.Item label="응답시간 p50">
                  {kpi.runMeta.responseTimeP50Text}
                </Descriptions.Item>
                <Descriptions.Item label="응답시간 p95">
                  {kpi.runMeta.responseTimeP95Text}
                </Descriptions.Item>
                <Descriptions.Item label="LLM 평가율">
                  {kpi.runMeta.llmDoneRateText}
                </Descriptions.Item>
                <Descriptions.Item label="LLM PASS율">
                  {kpi.runMeta.llmPassRateText}
                </Descriptions.Item>
                <Descriptions.Item label="LLM 평균 점수">
                  {kpi.runMeta.llmTotalScoreAvgText}
                </Descriptions.Item>
              </Descriptions>
            ),
          },
        ]}
      />

      <div className="validation-section-block">
        <div className="validation-section-header">
          <Space size={6}>
            <Typography.Title level={5} style={{ margin: 0 }}>
              결과 테이블
            </Typography.Title>
            {kpi.latencyUnclassifiedCount > 0 ? (
              <Tooltip
                title={`미분류 응답 속도 데이터 ${kpi.latencyUnclassifiedCount}건이 있습니다.`}
              >
                <WarningOutlined
                  style={{ color: '#faad14', fontSize: 14, cursor: 'help' }}
                />
              </Tooltip>
            ) : null}
          </Space>
          <Space direction="vertical" size={8} style={{ alignItems: 'flex-end' }}>
            <Space wrap>
              <Select
                value={filters.tablePreset}
                options={PRESET_OPTIONS}
                style={{ width: 220 }}
                onChange={(tablePreset) =>
                  onChangeFilters({
                    ...filters,
                    tablePreset,
                    scoreBucketFilter: null,
                  })
                }
              />
            </Space>
            {activeFilterTags.length > 0 ? (
              <Space wrap>
                {activeFilterTags.map((filterTag) => (
                  <Tag
                    key={filterTag.key}
                    closable
                    onClose={(event) => {
                      event.preventDefault();
                      filterTag.clear();
                    }}
                  >
                    {filterTag.label}
                  </Tag>
                ))}
                <Button size="small" type="link" onClick={clearAllFilters}>
                  전체 해제
                </Button>
              </Space>
            ) : null}
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
