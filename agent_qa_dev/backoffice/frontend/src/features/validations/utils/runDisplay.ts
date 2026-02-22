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

const toFixedRate = (value?: number | null) => {
  if (!value && value !== 0) return null;
  const normalized = Number(value);
  if (!Number.isFinite(normalized)) return null;
  return `${normalized.toFixed(3)}%`;
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
  items.filter((item) => (item.llmEvaluation?.status || '').toUpperCase() === 'DONE').length;

export const getResponseTimeText = (responseTimeSec?: NullableNumber, latencyMs?: NullableNumber) => {
  const secFromMs = responseTimeSec ?? (latencyMs === null || latencyMs === undefined ? null : latencyMs / 1000);
  return toFixedSeconds(secFromMs) || '-';
};

type ValidationRunAggregateSummary = {
  averageResponseTimeSecText: string;
  totalResponseTimeSecText: string;
  responseTimeP50SecText: string;
  responseTimeP95SecText: string;
  logicPassRateText: string;
  llmDoneRateText: string;
  llmTotalScoreAvgText: string;
  llmPassRateText: string;
};

const toFiniteNumber = (value?: NullableNumber): number | null => {
  if (value === null || value === undefined) return null;
  const normalized = Number(value);
  return Number.isFinite(normalized) ? normalized : null;
};

const getResponseTimeSec = (row: ValidationRunItem): number | null => {
  const direct = toFiniteNumber(row.responseTimeSec);
  if (direct !== null) return direct;
  if (row.latencyMs === null || row.latencyMs === undefined) return null;
  const latency = toFiniteNumber(row.latencyMs);
  return latency === null ? null : latency / 1000;
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

  const logicPassRateText =
    toFixedRate(currentRun?.scoreSummary?.logicPassRate) || (() => {
      const total = totalItems;
      if (!total) return null;
      const passCount = runItems.filter(
        (item) => (item.logicEvaluation?.result || '').toUpperCase() === 'PASS',
      ).length;
      return toRatePercent(passCount, total);
    })() || '-';

  const llmDoneCount = Math.max(currentRun?.llmDoneItems ?? countLlmDone(runItems), 0);
  const llmDoneRateText = toRatePercent(llmDoneCount, totalItems) || '-';

  const llmPassRateText = (() => {
    const llmDone = runItems.filter(
      (item) => (item.llmEvaluation?.status || '').toUpperCase() === 'DONE',
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
          if (status !== 'DONE') return null;
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
    logicPassRateText: logicPassRateText || '-',
    llmDoneRateText: llmDoneRateText || '-',
    llmTotalScoreAvgText: llmTotalScoreAvgText || '-',
    llmPassRateText: llmPassRateText || '-',
  };
};
