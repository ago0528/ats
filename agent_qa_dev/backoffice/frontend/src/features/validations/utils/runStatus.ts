import type { ValidationRun, ValidationRunItem } from '../../../api/types/validation';

const toUpperState = (value?: string) => String(value || '').trim().toUpperCase();

const countLlmEvaluated = (runItems: ValidationRunItem[]) =>
  runItems.filter((item) => Boolean(item.llmEvaluation)).length;

export function getExecutionStateLabel(currentRun: ValidationRun | null) {
  if (!currentRun) return '미생성';
  const status = toUpperState(currentRun.status);
  if (status === 'PENDING') return '실행대기';
  if (status === 'RUNNING') return '실행중';
  if (status === 'DONE') return '실행완료';
  if (status === 'FAILED') return '실행실패';
  return status || '-';
}

export function getEvaluationStateLabel(
  currentRun: ValidationRun | null,
  runItems: ValidationRunItem[] = [],
) {
  if (!currentRun) return '평가대기';
  if (runItems.length === 0) {
    const status = toUpperState(currentRun.status);
    const evalStatus = toUpperState(currentRun.evalStatus);
    if (evalStatus === 'RUNNING') return '평가중';
    if (status !== 'DONE') return '평가대기';
    const totalItems = currentRun.totalItems || 0;
    const llmDoneItems = currentRun.llmDoneItems || 0;
    if (totalItems === 0) return evalStatus === 'DONE' ? '평가완료' : '평가대기';
    if (llmDoneItems === 0) return '평가대기';
    if (llmDoneItems < totalItems) return '평가중';
    return '평가완료';
  }

  const llmEvaluated = countLlmEvaluated(runItems);
  if (llmEvaluated === 0) return '평가대기';
  if (llmEvaluated < runItems.length) return '평가중';
  return '평가완료';
}

export function getHistoryRunStateText(currentRun: ValidationRun | null) {
  if (!currentRun) return '미생성';
  const executionState = getExecutionStateLabel(currentRun);
  if (executionState !== '실행완료') return executionState;
  return getEvaluationStateLabel(currentRun);
}

export function getCombinedRunStateLabel(
  currentRun: ValidationRun | null,
  runItems: ValidationRunItem[],
) {
  if (!currentRun) return '미생성';
  const executionState = getExecutionStateLabel(currentRun);
  if (executionState !== '실행완료') return executionState;
  return getEvaluationStateLabel(currentRun, runItems);
}

export const countLlmEvaluatedItems = countLlmEvaluated;

export const getEvaluationProgressText = (runItems: ValidationRunItem[]) =>
  `${countLlmEvaluated(runItems)} / ${runItems.length}`;
