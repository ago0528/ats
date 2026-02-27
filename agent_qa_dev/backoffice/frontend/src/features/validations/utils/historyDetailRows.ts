import type { ValidationRun, ValidationRunItem } from '../../../api/types/validation';
import { formatDateTime, toTimestamp } from '../../../shared/utils/dateTime';
import { HISTORY_SLOW_THRESHOLD_SEC, RESULT_LOW_SCORE_THRESHOLD } from '../constants';
import {
  formatScoreText,
  formatSecText,
  getLatencyClassLabel,
  getRunItemStatus,
  getRunItemStatusLabel,
  type DisplayRunItemStatus,
  NOT_AGGREGATED_LABEL,
} from './historyDetailDisplay';
import {
  getValidationRunAdvancedScoringSummary,
  getValidationRunAggregateSummary,
} from './runDisplay';

const toFiniteNumber = (value?: number | null) => {
  if (value === null || value === undefined) return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  return parsed;
};

const normalizeText = (value?: string | null) => String(value || '').trim();

const getResponseTimeSec = (item: ValidationRunItem) => {
  const fromSec = toFiniteNumber(item.responseTimeSec);
  if (fromSec !== null) return fromSec;
  const fromMs = toFiniteNumber(item.latencyMs);
  if (fromMs === null) return null;
  return fromMs / 1000;
};

const normalizeLatencyClass = (
  value?: string | null,
): 'SINGLE' | 'MULTI' | 'UNCLASSIFIED' | null => {
  const normalized = String(value || '').trim().toUpperCase();
  if (normalized === 'SINGLE' || normalized === 'MULTI' || normalized === 'UNCLASSIFIED') {
    return normalized;
  }
  return null;
};

const parseJsonObject = (value: unknown) => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  if (typeof value !== 'string') return {};
  const text = value.trim();
  if (!text) return {};
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    return {};
  }
  return {};
};

const quantile = (values: number[], q: number): number | null => {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.round((sorted.length - 1) * q)));
  return sorted[idx];
};

const getMetricScore = (item: ValidationRunItem, key: string) => {
  const metrics = parseJsonObject(item.llmEvaluation?.metricScores);
  if (key in metrics) {
    const exact = toFiniteNumber(metrics[key] as number | null | undefined);
    if (exact !== null) return exact;
  }
  const aliasMap: Record<string, string[]> = {
    intent: ['의도충족'],
    accuracy: ['정확성'],
    consistency: [],
    latencySingle: [],
    latencyMulti: [],
    stability: ['안정성'],
  };
  for (const alias of aliasMap[key] || []) {
    const fallback = toFiniteNumber(metrics[alias] as number | null | undefined);
    if (fallback !== null) return fallback;
  }
  return null;
};

const getStabilityScore = (item: ValidationRunItem) => {
  const metricValue = getMetricScore(item, 'stability');
  if (metricValue !== null) return metricValue;
  return normalizeText(item.error) ? 0 : 5;
};

const formatCompactText = (value?: string | null, fallback = NOT_AGGREGATED_LABEL) => {
  const text = normalizeText(value);
  if (!text) return fallback;
  return text;
};

export type HistoryRowView = {
  key: string;
  item: ValidationRunItem;
  errorSummary: string;
  hasError: boolean;
  status: DisplayRunItemStatus;
  statusLabel: string;
  responseTimeSec: number | null;
  responseTimeText: string;
  executedAtText: string;
  executedAtTs: number;
};

export type HistoryStatusFilter = 'all' | DisplayRunItemStatus;

export type HistoryTableFilters = {
  onlyErrors: boolean;
  onlySlow: boolean;
  status: HistoryStatusFilter;
  dateRange: [Date | null, Date | null];
};

export type HistorySummary = {
  executionStatusText: string;
  executionTimeText: string;
  totalRowsText: string;
  errorRowsText: string;
  p50Text: string;
  p95Text: string;
};

export function buildHistoryRows(items: ValidationRunItem[]) {
  return items.map<HistoryRowView>((item) => {
    const responseTimeSec = getResponseTimeSec(item);
    const status = getRunItemStatus(item);
    const errorSummary = normalizeText(item.error);
    return {
      key: item.id,
      item,
      errorSummary: errorSummary || '정상',
      hasError: Boolean(errorSummary),
      status,
      statusLabel: getRunItemStatusLabel(status),
      responseTimeSec,
      responseTimeText: formatSecText(responseTimeSec),
      executedAtText: item.executedAt ? formatDateTime(item.executedAt) : NOT_AGGREGATED_LABEL,
      executedAtTs: toTimestamp(item.executedAt || null),
    };
  });
}

export function sortHistoryRows(rows: HistoryRowView[]) {
  return [...rows].sort((left, right) => {
    if (left.hasError !== right.hasError) {
      return left.hasError ? -1 : 1;
    }
    const leftLatency = left.responseTimeSec ?? -1;
    const rightLatency = right.responseTimeSec ?? -1;
    if (leftLatency !== rightLatency) {
      return rightLatency - leftLatency;
    }
    return right.executedAtTs - left.executedAtTs;
  });
}

export function filterHistoryRows(
  rows: HistoryRowView[],
  filters: HistoryTableFilters,
  slowThresholdSec = HISTORY_SLOW_THRESHOLD_SEC,
) {
  const [startDate, endDate] = filters.dateRange;
  const startBoundary = startDate
    ? new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate()).getTime()
    : null;
  const endBoundary = endDate
    ? new Date(endDate.getFullYear(), endDate.getMonth(), endDate.getDate(), 23, 59, 59, 999).getTime()
    : null;

  return rows.filter((row) => {
    if (filters.onlyErrors && !row.hasError) return false;
    if (filters.onlySlow && ((row.responseTimeSec ?? -1) < slowThresholdSec)) return false;
    if (filters.status !== 'all' && row.status !== filters.status) return false;
    if (startBoundary !== null || endBoundary !== null) {
      if (!row.executedAtTs) return false;
      if (startBoundary !== null && row.executedAtTs < startBoundary) return false;
      if (endBoundary !== null && row.executedAtTs > endBoundary) return false;
    }
    return true;
  });
}

export function buildHistorySummary(
  run: ValidationRun | null,
  rows: HistoryRowView[],
): HistorySummary {
  const allLatency = rows
    .map((row) => row.responseTimeSec)
    .filter((value): value is number => value !== null);
  const startedAt = run?.startedAt ? toTimestamp(run.startedAt) : 0;
  const finishedAt = run?.finishedAt ? toTimestamp(run.finishedAt) : 0;
  const isRunning = String(run?.status || '').toUpperCase() === 'RUNNING';
  const durationSec = startedAt > 0 && finishedAt >= startedAt ? (finishedAt - startedAt) / 1000 : null;

  const executionTimeText = isRunning
    ? '집계 중'
    : durationSec !== null
      ? `${durationSec.toFixed(3)}초`
      : NOT_AGGREGATED_LABEL;

  return {
    executionStatusText: isRunning ? '진행중' : run ? '완료' : NOT_AGGREGATED_LABEL,
    executionTimeText,
    totalRowsText: `${run?.totalItems ?? rows.length}건`,
    errorRowsText: `${rows.filter((row) => row.hasError).length}건`,
    p50Text: formatSecText(quantile(allLatency, 0.5)),
    p95Text: formatSecText(quantile(allLatency, 0.95)),
  };
}

export type ResultsRowView = {
  key: string;
  item: ValidationRunItem;
  queryKey: string;
  totalScore: number | null;
  totalScoreText: string;
  intentScore: number | null;
  intentScoreText: string;
  accuracyScore: number | null;
  accuracyScoreText: string;
  consistencyScore: number | null;
  consistencyScoreText: string;
  speedSec: number | null;
  speedText: string;
  latencyClass: 'SINGLE' | 'MULTI' | 'UNCLASSIFIED';
  latencyClassLabel: string;
  scoreBucket: number | null;
  stabilityScore: number | null;
  stabilityScoreText: string;
  abnormal: boolean;
};

export type ResultsTablePreset = 'default' | 'low' | 'abnormal' | 'slow';

export type ResultsFilters = {
  tablePreset: ResultsTablePreset;
  onlyLowScore: boolean;
  onlyAbnormal: boolean;
  onlySlow: boolean;
  onlyLatencyUnclassified: boolean;
  scoreBucketFilter: number | null;
  focusMetric: 'intent' | 'accuracy' | 'consistency' | 'speed' | 'stability' | null;
};

export function buildResultsRows(items: ValidationRunItem[]) {
  const baseRows = items.map((item) => {
    const intentScore = getMetricScore(item, 'intent');
    const accuracyScore = getMetricScore(item, 'accuracy');
    const consistencyScore = getMetricScore(item, 'consistency');
    const latencySingleScore = getMetricScore(item, 'latencySingle');
    const latencyMultiScore = getMetricScore(item, 'latencyMulti');
    const stabilityScore = getStabilityScore(item);
    const speedSec = getResponseTimeSec(item);
    const queryKey = normalizeText(item.queryId) || normalizeText(item.queryText) || item.id;
    const llmTotal = toFiniteNumber(item.llmEvaluation?.totalScore);
    const fallbackTotal = [intentScore, accuracyScore, stabilityScore]
      .filter((value): value is number => value !== null);
    const totalScore = llmTotal !== null
      ? llmTotal
      : (fallbackTotal.length ? fallbackTotal.reduce((acc, value) => acc + value, 0) / fallbackTotal.length : null);
    const abnormal = Boolean(normalizeText(item.error))
      || String(item.llmEvaluation?.status || '').toUpperCase().includes('ERROR')
      || String(item.llmEvaluation?.status || '').toUpperCase().includes('FAILED');
    const explicitLatencyClass = normalizeLatencyClass(item.latencyClass);
    const normalizedLatencyClass: 'SINGLE' | 'MULTI' | 'UNCLASSIFIED' =
      explicitLatencyClass
      ?? (latencySingleScore !== null && latencyMultiScore === null
        ? 'SINGLE'
        : latencyMultiScore !== null && latencySingleScore === null
          ? 'MULTI'
          : 'UNCLASSIFIED');
    return {
      item,
      queryKey,
      intentScore,
      accuracyScore,
      consistencyScore,
      stabilityScore,
      speedSec,
      totalScore,
      latencyClass: normalizedLatencyClass,
      abnormal,
    };
  });

  return baseRows.map<ResultsRowView>((row) => ({
    key: row.item.id,
    item: row.item,
    queryKey: row.queryKey,
    totalScore: row.totalScore,
    totalScoreText: formatScoreText(row.totalScore),
    intentScore: row.intentScore,
    intentScoreText: formatScoreText(row.intentScore),
    accuracyScore: row.accuracyScore,
    accuracyScoreText: formatScoreText(row.accuracyScore),
    consistencyScore: row.consistencyScore,
    consistencyScoreText: formatScoreText(row.consistencyScore),
    speedSec: row.speedSec,
    speedText: formatSecText(row.speedSec),
    latencyClass: row.latencyClass,
    latencyClassLabel: getLatencyClassLabel(row.latencyClass),
    scoreBucket:
      row.totalScore === null
        ? null
        : Math.max(0, Math.min(5, Math.round(row.totalScore))),
    stabilityScore: row.stabilityScore,
    stabilityScoreText: formatScoreText(row.stabilityScore),
    abnormal: row.abnormal,
  }));
}

export function sortResultsRows(rows: ResultsRowView[]) {
  return [...rows].sort((left, right) => {
    const leftScore = left.totalScore ?? Number.POSITIVE_INFINITY;
    const rightScore = right.totalScore ?? Number.POSITIVE_INFINITY;
    if (leftScore !== rightScore) {
      return leftScore - rightScore;
    }
    const leftSpeed = left.speedSec ?? -1;
    const rightSpeed = right.speedSec ?? -1;
    if (leftSpeed !== rightSpeed) {
      return rightSpeed - leftSpeed;
    }
    if (left.item.ordinal !== right.item.ordinal) {
      return left.item.ordinal - right.item.ordinal;
    }
    return left.item.id.localeCompare(right.item.id);
  });
}

export function filterResultsRows(
  rows: ResultsRowView[],
  filters: ResultsFilters,
  slowThresholdSec = HISTORY_SLOW_THRESHOLD_SEC,
  lowScoreThreshold = RESULT_LOW_SCORE_THRESHOLD,
) {
  const applyPreset = (row: ResultsRowView) => {
    if (filters.tablePreset === 'low') {
      return (row.totalScore ?? Number.POSITIVE_INFINITY) <= lowScoreThreshold;
    }
    if (filters.tablePreset === 'abnormal') {
      return row.abnormal;
    }
    if (filters.tablePreset === 'slow') {
      return (row.speedSec ?? -1) >= slowThresholdSec;
    }
    return true;
  };

  return rows.filter((row) => {
    if (!applyPreset(row)) return false;
    if (filters.onlyLowScore && ((row.totalScore ?? Number.POSITIVE_INFINITY) > lowScoreThreshold)) return false;
    if (filters.onlyAbnormal && !row.abnormal) return false;
    if (filters.onlySlow && ((row.speedSec ?? -1) < slowThresholdSec)) return false;
    if (filters.onlyLatencyUnclassified && row.latencyClass !== 'UNCLASSIFIED') return false;
    if (filters.focusMetric === 'intent' && ((row.intentScore ?? Number.POSITIVE_INFINITY) >= 3)) return false;
    if (filters.focusMetric === 'accuracy' && ((row.accuracyScore ?? Number.POSITIVE_INFINITY) >= 3)) return false;
    if (filters.focusMetric === 'consistency' && ((row.consistencyScore ?? Number.POSITIVE_INFINITY) >= 3)) return false;
    if (filters.focusMetric === 'speed' && ((row.speedSec ?? -1) < slowThresholdSec)) return false;
    if (filters.focusMetric === 'stability' && ((row.stabilityScore ?? Number.POSITIVE_INFINITY) >= 5)) return false;
    if (filters.scoreBucketFilter !== null && row.scoreBucket !== filters.scoreBucketFilter) return false;
    return true;
  });
}

export function buildResultsKpi(run: ValidationRun | null, items: ValidationRunItem[]) {
  const advanced = getValidationRunAdvancedScoringSummary(items);
  const aggregate = getValidationRunAggregateSummary(run, items);
  const intentSampleCount = items.filter((item) => getMetricScore(item, 'intent') !== null).length;
  const accuracySampleCount = items.filter((item) => getMetricScore(item, 'accuracy') !== null).length;
  const stabilitySampleCount = items.length;
  const lowScoreCount = buildResultsRows(items).filter(
    (row) => (row.totalScore ?? Number.POSITIVE_INFINITY) <= RESULT_LOW_SCORE_THRESHOLD,
  ).length;

  const noDataReason = '현재 Run은 해당 지표 계산 대상이 없어 집계되지 않았습니다.';
  return {
    intent: {
      score: advanced.intentScore,
      sampleCount: intentSampleCount,
      notAggregatedReason: intentSampleCount === 0 ? noDataReason : '',
    },
    accuracy: {
      score: advanced.accuracyScore,
      sampleCount: accuracySampleCount,
      fallbackCount: advanced.accuracyFallbackCount,
      fallbackRate: advanced.accuracyFallbackRate,
      notAggregatedReason: accuracySampleCount === 0 ? noDataReason : '',
    },
    consistency: {
      score: advanced.consistencyScore,
      status: advanced.consistencyStatus,
      sampleCount: advanced.consistencyEligibleQueryCount,
      notAggregatedReason:
        advanced.consistencyStatus === 'PENDING'
          ? '동일 질의의 반복 실행 수가 부족해 일관성을 집계할 수 없습니다.'
          : '',
    },
    speedSingle: {
      avgSec: advanced.latencySingleAvgSec,
      p50Sec: advanced.latencySingleP50Sec,
      p90Sec: advanced.latencySingleP90Sec,
      sampleCount: advanced.latencySingleCount,
      notAggregatedReason: advanced.latencySingleCount === 0 ? noDataReason : '',
    },
    speedMulti: {
      avgSec: advanced.latencyMultiAvgSec,
      p50Sec: advanced.latencyMultiP50Sec,
      p90Sec: advanced.latencyMultiP90Sec,
      sampleCount: advanced.latencyMultiCount,
      notAggregatedReason: advanced.latencyMultiCount === 0 ? noDataReason : '',
    },
    stability: {
      score: advanced.stabilityScore,
      errorRate: advanced.stabilityErrorRate,
      emptyRate: advanced.stabilityEmptyRate,
      sampleCount: stabilitySampleCount,
      notAggregatedReason: stabilitySampleCount === 0 ? noDataReason : '',
    },
    runMeta: {
      totalRows: run?.totalItems ?? items.length,
      doneRows: run?.doneItems ?? 0,
      errorRows: run?.errorItems ?? 0,
      llmDoneRows: run?.llmDoneItems ?? 0,
      averageResponseTimeText: aggregate.averageResponseTimeSecText,
      responseTimeP50Text: aggregate.responseTimeP50SecText,
      responseTimeP95Text: aggregate.responseTimeP95SecText,
      logicPassRateText: aggregate.logicPassRateText,
      llmDoneRateText: aggregate.llmDoneRateText,
      llmPassRateText: aggregate.llmPassRateText,
      llmTotalScoreAvgText: aggregate.llmTotalScoreAvgText,
    },
    scoreBuckets: advanced.scoreBuckets,
    lowScoreCount,
    latencyUnclassifiedCount: advanced.latencyUnclassifiedCount,
  };
}

export function buildDistributionRows(buckets: Record<string, number>) {
  return ['5', '4', '3', '2', '1', '0'].map((score) => ({
    key: score,
    score,
    count: Number(buckets[score] || 0),
  }));
}

export function getRequestText(item: ValidationRunItem) {
  return formatCompactText(item.queryText);
}

export function getResponseText(item: ValidationRunItem) {
  return formatCompactText(item.rawResponse);
}

export function getErrorText(item: ValidationRunItem) {
  return formatCompactText(item.error);
}
