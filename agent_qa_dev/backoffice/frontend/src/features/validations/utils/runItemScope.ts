import type { ValidationRunItem } from '../../../api/types/validation';

export function hasExecutionResult(item: ValidationRunItem): boolean {
  return (
    Boolean(item.executedAt)
    || Boolean(String(item.error || '').trim())
    || Boolean(String(item.rawResponse || '').trim())
  );
}

export function hasEvaluationResult(item: ValidationRunItem): boolean {
  return Boolean(item.logicEvaluation) || Boolean(item.llmEvaluation);
}

export function buildRunItemIdsByQueryId(
  runItems: ValidationRunItem[],
): Map<string, string[]> {
  const map = new Map<string, string[]>();
  runItems.forEach((item) => {
    const queryId = String(item.queryId || '').trim();
    if (!queryId) return;
    const currentIds = map.get(queryId) || [];
    currentIds.push(item.id);
    map.set(queryId, currentIds);
  });
  return map;
}

export function resolveScopedRunItemIds(
  item: ValidationRunItem,
  runItemIdsByQueryId: Map<string, string[]>,
): string[] {
  const queryId = String(item.queryId || '').trim();
  if (!queryId) return [item.id];

  const ids = runItemIdsByQueryId.get(queryId) || [];
  if (ids.length === 0) return [item.id];

  return Array.from(
    new Set(ids.map((id) => String(id || '').trim()).filter(Boolean)),
  );
}

export function needsRunItemActionConfirm(
  runItems: ValidationRunItem[],
  scopedItemIds: string[],
): boolean {
  const scopedSet = new Set(scopedItemIds);
  return runItems.some(
    (item) =>
      scopedSet.has(item.id)
      && (hasExecutionResult(item) || hasEvaluationResult(item)),
  );
}
