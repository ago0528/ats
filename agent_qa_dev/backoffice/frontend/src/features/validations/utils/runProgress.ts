import type {
  ValidationRun,
  ValidationRunItem,
} from '../../../api/types/validation';
import {
  countLlmEvaluatedItems,
  getCombinedRunStateLabel as getCombinedRunStateLabelFromStatus,
  getEvaluationStateLabel as getEvaluationStateLabelFromStatus,
  getEvaluationProgressText as getEvaluationProgressTextFromItems,
  getExecutionStateLabel as getExecutionStateLabelFromStatus,
} from './runStatus';

export type ValidationRunStage = 'TEST_SET' | 'EXECUTE' | 'EVALUATE' | 'RESULT';

function hasExecutionResults(runItems: ValidationRunItem[]) {
  return runItems.some((item) => {
    const hasExecutedAt = Boolean(item.executedAt);
    const hasError = Boolean(String(item.error || '').trim());
    const hasResponse = Boolean(String(item.rawResponse || '').trim());
    return hasExecutedAt || hasError || hasResponse;
  });
}

export function getRunStageAvailability(
  currentRun: ValidationRun | null,
  runItems: ValidationRunItem[],
) {
  if (!currentRun) {
    return {
      executeEnabled: false,
      evaluateEnabled: false,
      resultEnabled: false,
    };
  }

  const executed =
    hasExecutionResults(runItems) ||
    currentRun.status === 'DONE' ||
    currentRun.status === 'FAILED';
  const evaluated = countLlmEvaluatedItems(runItems) > 0;
  return {
    executeEnabled: true,
    evaluateEnabled: executed,
    resultEnabled: executed || evaluated,
  };
}

export function getExecutionStateLabel(currentRun: ValidationRun | null) {
  return getExecutionStateLabelFromStatus(currentRun);
}

export function getEvaluationStateLabel(
  currentRun: ValidationRun | null,
  runItems: ValidationRunItem[] = [],
) {
  return getEvaluationStateLabelFromStatus(currentRun, runItems);
}

export function getEvaluationProgressText(runItems: ValidationRunItem[]) {
  return getEvaluationProgressTextFromItems(runItems);
}

export function getCombinedRunStateLabel(
  currentRun: ValidationRun | null,
  runItems: ValidationRunItem[],
) {
  return getCombinedRunStateLabelFromStatus(currentRun, runItems);
}
