import type { ValidationRun, ValidationRunItem } from '../../../api/types/validation';
import { getHistoryRunStateText, getEvaluationProgressText } from './runStatus';

type NullableNumber = number | null | undefined;

export const getRunDisplayName = (run: ValidationRun) => {
  const explicitName = run.name?.trim();
  if (explicitName) {
    return explicitName;
  }

  if (run.createdAt) {
    const parsed = new Date(run.createdAt);
    if (!Number.isNaN(parsed.getTime())) {
      const createdText = parsed.toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
      return `Run ${createdText}`;
    }
  }

  const fallback = String(run.id || '').trim();
  if (!fallback) return 'Run';
  if (fallback.length <= 10) return fallback;
  return `${fallback.slice(0, 8)}...`;
};

export const getRunExecutionConfigText = (run: ValidationRun) =>
  `반복 수: ${run.repeatInConversation}회 / 채팅방 수 ${run.conversationRoomCount}개 / 동시 실행 수: ${run.agentParallelCalls}번`;

export const getRunEvaluationProgressText = (run: ValidationRun) =>
  `${run.llmDoneItems || 0} / ${run.totalItems || 0}`;

export { getHistoryRunStateText, getEvaluationProgressText };

const toFixedSeconds = (value?: number | null) => {
  if (!value && value !== 0) return null;
  const normalized = Number(value);
  if (!Number.isFinite(normalized)) return null;
  return `${normalized.toFixed(3)}초`;
};

const toFixedScore = (value?: number | null) => {
  if (!value && value !== 0) return null;
  const normalized = Number(value);
  if (!Number.isFinite(normalized)) return null;
  return normalized.toFixed(3);
};

const toRatePercent = (value?: number | null, denominator?: number | null) => {
  if (value === null || value === undefined) {
    return null;
  }
  if (denominator === null || denominator === undefined) {
    return null;
  }
  const denom = Number(denominator);
  if (!Number.isFinite(denom) || denom <= 0) return null;
  return `${((Number(value) / denom) * 100).toFixed(1)}%`;
};

const countLlmDone = (items: ValidationRunItem[]) =>
  items.filter((item) => (item.llmEvaluation?.status || '').toUpperCase().startsWith('DONE')).length;

export const getResponseTimeText = (responseTimeSec?: NullableNumber, latencyMs?: NullableNumber) => {
  const secFromMs = responseTimeSec ?? (latencyMs === null || latencyMs === undefined ? null : latencyMs / 1000);
  return toFixedSeconds(secFromMs) || '-';
};

type ValidationRunAggregateSummary = {
  averageResponseTimeSecText: string;
  totalResponseTimeSecText: string;
  responseTimeP50SecText: string;
  responseTimeP95SecText: string;
  llmDoneRateText: string;
  llmTotalScoreAvgText: string;
  llmPassRateText: string;
};

type AdvancedBucket = Record<string, number>;

export type ValidationRunAdvancedScoringSummary = {
  intentScore: number | null;
  accuracyScore: number | null;
  accuracyFallbackCount: number;
  accuracyFallbackRate: number;
  consistencyScore: number | null;
  consistencyStatus: 'READY' | 'PENDING';
  consistencyEligibleQueryCount: number;
  latencySingleAvgSec: number | null;
  latencySingleP50Sec: number | null;
  latencySingleP90Sec: number | null;
  latencySingleCount: number;
  latencyMultiAvgSec: number | null;
  latencyMultiP50Sec: number | null;
  latencyMultiP90Sec: number | null;
  latencyMultiCount: number;
  latencyUnclassifiedCount: number;
  stabilityScore: number | null;
  stabilityErrorRate: number;
  stabilityEmptyRate: number;
  scoreBuckets: AdvancedBucket;
};

const toFiniteNumber = (value?: NullableNumber): number | null => {
  if (value === null || value === undefined) return null;
  const normalized = Number(value);
  return Number.isFinite(normalized) ? normalized : null;
};

const initBuckets = (): AdvancedBucket => ({
  '0': 0,
  '1': 0,
  '2': 0,
  '3': 0,
  '4': 0,
  '5': 0,
});

const parseMetricScores = (value: unknown): Record<string, unknown> => {
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

const getMetricByAliases = (metricScores: Record<string, unknown>, aliases: string[]) => {
  for (const key of aliases) {
    if (!(key in metricScores)) continue;
    const parsed = toFiniteNumber(metricScores[key] as NullableNumber);
    if (parsed !== null) return parsed;
  }
  return null;
};

const parseRawPayload = (value: string): { payload: Record<string, unknown>; parseOk: boolean } => {
  const text = String(value || '').trim();
  if (!text) return { payload: {}, parseOk: false };
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return { payload: parsed as Record<string, unknown>, parseOk: true };
    }
  } catch {
    return { payload: {}, parseOk: false };
  }
  return { payload: {}, parseOk: false };
};

const hasResponseContent = (payload: Record<string, unknown>) => {
  const assistantMessage = String(payload['assistantMessage'] || '').trim();
  if (assistantMessage) return true;
  const dataUIList = payload['dataUIList'];
  return Array.isArray(dataUIList) && dataUIList.length > 0;
};

const averageNumber = (values: number[]) =>
  values.length ? values.reduce((acc, value) => acc + value, 0) / values.length : null;

const getResponseTimeSec = (row: ValidationRunItem): number | null => {
  const direct = toFiniteNumber(row.responseTimeSec);
  if (direct !== null) return direct;
  if (row.latencyMs === null || row.latencyMs === undefined) return null;
  const latency = toFiniteNumber(row.latencyMs);
  return latency === null ? null : latency / 1000;
};

const normalizeLatencyClass = (
  value: unknown,
): 'SINGLE' | 'MULTI' | 'UNCLASSIFIED' | null => {
  const normalized = String(value || '').trim().toUpperCase();
  if (normalized === 'SINGLE' || normalized === 'MULTI' || normalized === 'UNCLASSIFIED') {
    return normalized;
  }
  return null;
};

const inferLatencyClass = (
  latencySingleScore: number | null,
  latencyMultiScore: number | null,
): 'SINGLE' | 'MULTI' | 'UNCLASSIFIED' => {
  if (latencySingleScore !== null && latencyMultiScore === null) return 'SINGLE';
  if (latencyMultiScore !== null && latencySingleScore === null) return 'MULTI';
  return 'UNCLASSIFIED';
};

const quantile = (values: number[], q: number): number | null => {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.round((sorted.length - 1) * q)));
  return sorted[idx];
};

export const getValidationRunAggregateSummary = (
  currentRun: ValidationRun | null,
  runItems: ValidationRunItem[],
): ValidationRunAggregateSummary => {
  const totalItems = Math.max(currentRun?.totalItems ?? runItems.length, 0);
  const responseTimes = runItems
    .map(getResponseTimeSec)
    .filter((value): value is number => value !== null);

  const averageResponseTimeSec = (() => {
    if (
      currentRun?.averageResponseTimeSec !== null &&
      currentRun?.averageResponseTimeSec !== undefined
    ) {
      return toFixedSeconds(currentRun.averageResponseTimeSec);
    }
    if (!responseTimes.length) return null;
    const sum = responseTimes.reduce((acc, value) => acc + value, 0);
    return toFixedSeconds(sum / responseTimes.length);
  })();

  const totalResponseTimeSec = (() => {
    if (!responseTimes.length) return null;
    return toFixedSeconds(responseTimes.reduce((acc, value) => acc + value, 0));
  })();

  const responseTimeP50SecText = responseTimes.length ? toFixedSeconds(quantile(responseTimes, 0.5)) : null;
  const responseTimeP95SecText = responseTimes.length ? toFixedSeconds(quantile(responseTimes, 0.95)) : null;

  const llmDoneCount = Math.max(currentRun?.llmDoneItems ?? countLlmDone(runItems), 0);
  const llmDoneRateText = toRatePercent(llmDoneCount, totalItems) || '-';

  const llmPassRateText = (() => {
    const llmDone = runItems.filter(
      (item) => (item.llmEvaluation?.status || '').toUpperCase().startsWith('DONE'),
    );
    if (!llmDone.length) return null;
    const pass = llmDone.filter((row) => {
      const score = row.llmEvaluation?.totalScore;
      if (typeof score !== 'number' || !Number.isFinite(score)) return false;
      return score >= 3.0;
    }).length;
    return toRatePercent(pass, llmDone.length);
  })();

  const llmTotalScoreAvgText =
    toFixedScore(currentRun?.scoreSummary?.llmTotalScoreAvg) ||
    (() => {
      const scored = runItems
        .map((row) => {
          const status = (row.llmEvaluation?.status || '').toUpperCase();
          if (!status.startsWith('DONE')) return null;
          return row.llmEvaluation?.totalScore;
        })
        .filter((value): value is number => value !== null && value !== undefined && Number.isFinite(Number(value)));
      if (!scored.length) return null;
      return toFixedScore(scored.reduce((acc, value) => acc + Number(value), 0) / scored.length);
    })() ||
    '-';

  return {
    averageResponseTimeSecText: averageResponseTimeSec || '-',
    totalResponseTimeSecText: totalResponseTimeSec || '-',
    responseTimeP50SecText: responseTimeP50SecText || '-',
    responseTimeP95SecText: responseTimeP95SecText || '-',
    llmDoneRateText: llmDoneRateText || '-',
    llmTotalScoreAvgText: llmTotalScoreAvgText || '-',
    llmPassRateText: llmPassRateText || '-',
  };
};

export const getValidationRunAdvancedScoringSummary = (
  runItems: ValidationRunItem[],
): ValidationRunAdvancedScoringSummary => {
  const scoreBuckets = initBuckets();
  const intentScores: number[] = [];
  const accuracyScores: number[] = [];
  const stabilityScores: number[] = [];
  const latencySingleSecs: number[] = [];
  const latencyMultiSecs: number[] = [];
  const consistencyByQuery = new Map<string, number>();
  let emptyCount = 0;
  let errorCount = 0;
  let latencyUnclassifiedCount = 0;
  const accuracyFallbackCount = 0;
  let accuracySampleCount = 0;

  runItems.forEach((row) => {
    const metricScores = parseMetricScores(row.llmEvaluation?.metricScores);
    const intentScore = getMetricByAliases(metricScores, ['intent', '의도충족']);
    const accuracyScore = getMetricByAliases(metricScores, ['accuracy', '정확성']);
    const consistencyScore = getMetricByAliases(metricScores, ['consistency']);
    const latencySingleScore = getMetricByAliases(metricScores, ['latencySingle']);
    const latencyMultiScore = getMetricByAliases(metricScores, ['latencyMulti']);
    const stabilityMetric = getMetricByAliases(metricScores, ['stability', '안정성']);
    if (intentScore !== null) intentScores.push(intentScore);
    if (accuracyScore !== null) {
      accuracyScores.push(accuracyScore);
      accuracySampleCount += 1;
    }
    if (consistencyScore !== null) {
      const queryKey = String(row.queryId || row.queryText || row.id || '').trim();
      if (queryKey && !consistencyByQuery.has(queryKey)) {
        consistencyByQuery.set(queryKey, consistencyScore);
      }
    }

    const { payload: rawPayload, parseOk } = parseRawPayload(String(row.rawJson || ''));
    const rowError = String(row.error || '').trim();
    if (rowError) errorCount += 1;
    const stabilityScore = stabilityMetric ?? (rowError || !parseOk || !hasResponseContent(rawPayload) ? 0 : 5);
    if (!rowError && stabilityScore < 5) emptyCount += 1;
    stabilityScores.push(stabilityScore);

    const rawResponseSec = toFiniteNumber((rawPayload['responseTimeSec'] ?? null) as NullableNumber);
    const latencySec = (() => {
      const latency = toFiniteNumber(row.latencyMs);
      return latency === null ? null : latency / 1000;
    })();
    const responseSec = toFiniteNumber(row.responseTimeSec) ?? rawResponseSec ?? latencySec;
    const latencyClass = normalizeLatencyClass(row.latencyClass)
      ?? inferLatencyClass(latencySingleScore, latencyMultiScore);
    if (responseSec !== null) {
      if (latencyClass === 'SINGLE') {
        latencySingleSecs.push(responseSec);
      } else if (latencyClass === 'MULTI') {
        latencyMultiSecs.push(responseSec);
      } else {
        latencyUnclassifiedCount += 1;
      }
    }

    const quality = averageNumber([
      intentScore ?? 0,
      accuracyScore ?? 0,
      stabilityScore,
    ]);
    if (quality !== null) {
      scoreBuckets[String(Math.max(0, Math.min(5, Math.round(quality))))] += 1;
    }

  });

  const consistencyValues = [...consistencyByQuery.values()];
  const consistencyEligibleQueryCount = consistencyValues.length;
  const consistencyStatus = consistencyEligibleQueryCount > 0 ? 'READY' : 'PENDING';
  const consistencyScore = consistencyEligibleQueryCount > 0
    ? averageNumber(consistencyValues)
    : null;

  const total = runItems.length;
  return {
    intentScore: averageNumber(intentScores),
    accuracyScore: averageNumber(accuracyScores),
    accuracyFallbackCount,
    accuracyFallbackRate: accuracySampleCount > 0 ? accuracyFallbackCount / accuracySampleCount : 0,
    consistencyScore,
    consistencyStatus,
    consistencyEligibleQueryCount,
    latencySingleAvgSec: averageNumber(latencySingleSecs),
    latencySingleP50Sec: quantile(latencySingleSecs, 0.5),
    latencySingleP90Sec: quantile(latencySingleSecs, 0.9),
    latencySingleCount: latencySingleSecs.length,
    latencyMultiAvgSec: averageNumber(latencyMultiSecs),
    latencyMultiP50Sec: quantile(latencyMultiSecs, 0.5),
    latencyMultiP90Sec: quantile(latencyMultiSecs, 0.9),
    latencyMultiCount: latencyMultiSecs.length,
    latencyUnclassifiedCount,
    stabilityScore: averageNumber(stabilityScores),
    stabilityErrorRate: total > 0 ? errorCount / total : 0,
    stabilityEmptyRate: total > 0 ? emptyCount / total : 0,
    scoreBuckets,
  };
};
