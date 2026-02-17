import type { ValidationRun } from '../../../api/types/validation';

export function canCreateRun(selectedTestSetId: string) {
  return Boolean(String(selectedTestSetId || '').trim());
}

export function canExecuteRun(currentRun: ValidationRun | null) {
  return currentRun?.status === 'PENDING';
}

export function canEvaluateRun(currentRun: ValidationRun | null) {
  if (!currentRun) return false;
  return currentRun.doneItems + currentRun.errorItems > 0;
}

export function canCompareRun(currentRun: ValidationRun | null, baseRunId: string) {
  return Boolean(currentRun && String(baseRunId || '').trim());
}
