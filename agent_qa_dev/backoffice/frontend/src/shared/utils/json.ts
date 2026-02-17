export function parseJsonOrOriginal<T = unknown>(value?: string | null): T | string | undefined {
  const normalized = String(value ?? '').trim();
  if (!normalized) return undefined;

  try {
    return JSON.parse(normalized) as T;
  } catch {
    return normalized;
  }
}

export function stringifyPretty(value: unknown, fallback = '') {
  if (value === null || value === undefined) return fallback;
  if (typeof value === 'string') return value;

  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function tryPrettyJson(value?: string | null, fallback = '-') {
  if (!value) return fallback;

  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
}
