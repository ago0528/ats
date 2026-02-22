import type { ValidationRun } from '../../../api/types/validation';

export function canCreateRun(selectedTestSetId: string) {
  return Boolean(String(selectedTestSetId || '').trim());
}

export function canExecuteRun(currentRun: ValidationRun | null) {
  return currentRun?.status === 'PENDING';
}

export function canEvaluateRun(currentRun: ValidationRun | null) {
  if (!currentRun) return false;
  const evalStatus = String(currentRun.evalStatus || '').toUpperCase();
  if (currentRun.status === 'PENDING' || currentRun.status === 'RUNNING') {
    return false;
  }
  if (evalStatus === 'RUNNING') {
    return false;
  }
  return currentRun.doneItems + currentRun.errorItems > 0;
}

export function canUpdateRun(currentRun: ValidationRun | null) {
  return currentRun?.status === 'PENDING';
}

export function canDeleteRun(currentRun: ValidationRun | null) {
  if (!currentRun) return false;
  if (currentRun.status !== 'PENDING') return false;
  return (currentRun.doneItems || 0) + (currentRun.errorItems || 0) === 0;
}

export function canCompareRun(currentRun: ValidationRun | null, baseRunId: string) {
  return Boolean(currentRun && String(baseRunId || '').trim());
}
