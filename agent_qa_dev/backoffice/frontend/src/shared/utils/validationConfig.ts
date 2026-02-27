export const CONTEXT_SAMPLE =
  '{\n  "recruitPlanId": 1234,\n  "채용명": "2026년 상반기 채용"\n}';

export function normalizeAgentModeValue(
  value?: string,
  defaultValue = 'AUTO',
): string {
  const trimmed = String(value || '').trim();
  if (!trimmed || trimmed === 'ORCHESTRATOR_WORKER_V3') {
    return defaultValue;
  }
  return trimmed;
}

export function parseContextJson(raw?: string): {
  parsedContext?: Record<string, unknown>;
  parseError?: string;
} {
  const text = String(raw || '').trim();
  if (!text) {
    return { parsedContext: undefined };
  }

  try {
    const parsed = JSON.parse(text);
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return {
        parsedContext: undefined,
        parseError: 'context는 JSON 객체 형태여야 합니다.',
      };
    }

    return { parsedContext: parsed as Record<string, unknown> };
  } catch (error) {
    return {
      parsedContext: undefined,
      parseError: `context JSON 형식이 올바르지 않습니다. ${error instanceof Error ? error.message : ''}`.trim(),
    };
  }
}

export function stringifyContext(value?: unknown): string {
  if (value === undefined || value === null) {
    return '';
  }
  if (typeof value === 'string') {
    return value.trim();
  }

  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '';
  }
}
