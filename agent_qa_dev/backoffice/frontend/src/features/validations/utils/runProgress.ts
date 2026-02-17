import type { ValidationRun, ValidationRunItem } from '../../../api/types/validation';

export type ValidationRunStage = 'TEST_SET' | 'EXECUTE' | 'EVALUATE' | 'RESULT';

function hasExecutionResults(runItems: ValidationRunItem[]) {
  return runItems.some((item) => {
    const hasExecutedAt = Boolean(item.executedAt);
    const hasError = Boolean(String(item.error || '').trim());
    const hasResponse = Boolean(String(item.rawResponse || '').trim());
    return hasExecutedAt || hasError || hasResponse;
  });
}

function countLlmEvaluated(runItems: ValidationRunItem[]) {
  return runItems.filter((item) => Boolean(item.llmEvaluation)).length;
}

export function getRunStageAvailability(currentRun: ValidationRun | null, runItems: ValidationRunItem[]) {
  if (!currentRun) {
    return {
      executeEnabled: false,
      evaluateEnabled: false,
      resultEnabled: false,
    };
  }

  const executed = hasExecutionResults(runItems) || currentRun.status === 'DONE' || currentRun.status === 'FAILED';
  const evaluated = countLlmEvaluated(runItems) > 0;
  return {
    executeEnabled: true,
    evaluateEnabled: executed,
    resultEnabled: executed || evaluated,
  };
}

export function getExecutionStateLabel(currentRun: ValidationRun | null) {
  if (!currentRun) return '미생성';
  const status = String(currentRun.status || '').toUpperCase();
  if (status === 'PENDING') return '생성됨';
  if (status === 'RUNNING') return '실행중';
  if (status === 'DONE') return '실행완료';
  if (status === 'FAILED') return '실행실패';
  return status || '-';
}

export function getEvaluationStateLabel(currentRun: ValidationRun | null, runItems: ValidationRunItem[]) {
  if (!currentRun) return '평가대기';
  if (runItems.length === 0) return '평가대기';

  const llmEvaluated = countLlmEvaluated(runItems);
  if (llmEvaluated === 0) return '평가대기';
  if (llmEvaluated < runItems.length) return '평가중';
  return '평가완료';
}

export function getEvaluationProgressText(runItems: ValidationRunItem[]) {
  const llmEvaluated = countLlmEvaluated(runItems);
  return `${llmEvaluated} / ${runItems.length}`;
}
