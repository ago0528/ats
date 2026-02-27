import type { ValidationRun, ValidationRunItem } from '../../../api/types/validation';
import { formatDateTime } from '../../../shared/utils/dateTime';
import { AGENT_MODE_OPTIONS } from '../constants';

export const UNKNOWN_LABEL = '알 수 없음';
export const UNCLASSIFIED_LABEL = '미분류';
export const NOT_AGGREGATED_LABEL = '집계 없음';
export const AGGREGATING_LABEL = '집계 중';

const RUN_STATUS_LABELS: Record<string, string> = {
  PENDING: '대기',
  RUNNING: '진행중',
  DONE: '완료',
  FAILED: '실패',
  CANCELLED: '중단',
  CANCELED: '중단',
  ABORTED: '중단',
  STOPPED: '중단',
};

const MODEL_LABELS: Record<string, string> = {
  'gpt-5.2': 'GPT-5.2',
  'gpt-5-mini': 'GPT-5 Mini',
};

const AGENT_MODE_LABELS: Record<string, string> = AGENT_MODE_OPTIONS.reduce<Record<string, string>>(
  (acc, option) => {
    acc[option.value] = option.label;
    return acc;
  },
  {},
);

const normalizeStatus = (value?: string | null) => String(value || '').trim().toUpperCase();

const normalizeAgentMode = (value?: string | null) => {
  const normalized = String(value || '').trim();
  if (!normalized || normalized === 'ORCHESTRATOR_WORKER_V3') {
    return 'ORCHESTRATOR_ASSISTANT';
  }
  return normalized;
};

export type DisplayRunItemStatus = 'success' | 'failed' | 'stopped' | 'pending';

export function getRunStatusLabel(rawStatus?: string | null) {
  const status = normalizeStatus(rawStatus);
  if (!status) return UNKNOWN_LABEL;
  return RUN_STATUS_LABELS[status] || UNKNOWN_LABEL;
}

export function getRunStatusColor(rawStatus?: string | null) {
  const status = normalizeStatus(rawStatus);
  if (status === 'RUNNING') return 'processing';
  if (status === 'DONE') return 'success';
  if (status === 'FAILED') return 'error';
  if (status === 'PENDING') return 'warning';
  if (status === 'CANCELLED' || status === 'CANCELED' || status === 'ABORTED' || status === 'STOPPED') {
    return 'default';
  }
  return 'default';
}

export function getAgentModeLabel(rawAgentMode?: string | null) {
  const normalized = normalizeAgentMode(rawAgentMode);
  return AGENT_MODE_LABELS[normalized] || UNKNOWN_LABEL;
}

export function getModelLabel(rawModel?: string | null) {
  const normalized = String(rawModel || '').trim().toLowerCase();
  if (!normalized) return UNKNOWN_LABEL;
  return MODEL_LABELS[normalized] || UNKNOWN_LABEL;
}

export function getLatencyClassLabel(rawLatencyClass?: string | null) {
  const normalized = String(rawLatencyClass || '').trim().toUpperCase();
  if (normalized === 'SINGLE') return '싱글';
  if (normalized === 'MULTI') return '멀티';
  return UNCLASSIFIED_LABEL;
}

export function getLastUpdatedText(run: ValidationRun | null) {
  const lastUpdatedAt = getLastUpdatedAt(run);
  if (!lastUpdatedAt) return NOT_AGGREGATED_LABEL;
  return formatDateTime(lastUpdatedAt);
}

export function getLastUpdatedAt(run: ValidationRun | null) {
  if (!run) return null;
  const lastUpdatedAt =
    run.evalFinishedAt ||
    run.finishedAt ||
    run.evalStartedAt ||
    run.startedAt ||
    run.createdAt ||
    null;
  if (!lastUpdatedAt) return null;
  return String(lastUpdatedAt);
}

export function formatScoreText(value?: number | null, fallback = NOT_AGGREGATED_LABEL) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return fallback;
  }
  return Number(value).toFixed(2);
}

export function formatSecText(value?: number | null, fallback = NOT_AGGREGATED_LABEL) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return fallback;
  }
  return `${Number(value).toFixed(3)}초`;
}

export function formatPercentText(value?: number | null, fallback = NOT_AGGREGATED_LABEL) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return fallback;
  }
  return `${(Number(value) * 100).toFixed(2)}%`;
}

export function getRunItemStatus(item: ValidationRunItem): DisplayRunItemStatus {
  const errorText = String(item.error || '').trim();
  if (errorText) return 'failed';

  const hasExecutedAt = Boolean(item.executedAt);
  const hasResponse = Boolean(String(item.rawResponse || '').trim());
  if (hasExecutedAt || hasResponse) {
    return 'success';
  }

  const llmStatus = String(item.llmEvaluation?.status || '').trim().toUpperCase();
  const logicStatus = String(item.logicEvaluation?.result || '').trim().toUpperCase();
  if (llmStatus.startsWith('SKIPPED') || logicStatus.startsWith('SKIPPED')) {
    return 'stopped';
  }

  return 'pending';
}

export function getRunItemStatusLabel(status: DisplayRunItemStatus) {
  if (status === 'success') return '성공';
  if (status === 'failed') return '실패';
  if (status === 'stopped') return '중단';
  return '대기';
}

export function getRunItemStatusColor(status: DisplayRunItemStatus) {
  if (status === 'success') return 'success';
  if (status === 'failed') return 'error';
  if (status === 'stopped') return 'default';
  return 'warning';
}
