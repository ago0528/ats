const KST_TIME_ZONE = 'Asia/Seoul';
const HAS_TIMEZONE_SUFFIX = /(Z|[+-]\d{2}:?\d{2})$/i;
const DATE_ONLY_VALUE = /^\d{4}-\d{2}-\d{2}$/;

const KST_DATE_TIME_FORMATTER = new Intl.DateTimeFormat('en-CA', {
  timeZone: KST_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

const KST_DATE_FORMATTER = new Intl.DateTimeFormat('en-CA', {
  timeZone: KST_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

function parseUtcLikeDate(value: string): Date | null {
  const trimmed = value.trim();
  if (!trimmed) return null;

  let normalized = trimmed.replace(' ', 'T');
  if (DATE_ONLY_VALUE.test(normalized)) {
    normalized = `${normalized}T00:00:00Z`;
  } else if (!HAS_TIMEZONE_SUFFIX.test(normalized)) {
    normalized = `${normalized}Z`;
  }

  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return null;
  return date;
}

function getDateParts(formatter: Intl.DateTimeFormat, date: Date) {
  return formatter.formatToParts(date).reduce<Record<string, string>>((acc, part) => {
    if (part.type !== 'literal') acc[part.type] = part.value;
    return acc;
  }, {});
}

export function formatDateTime(value?: string | null) {
  if (!value) return '-';
  const date = parseUtcLikeDate(value);
  if (!date) return value;
  const parts = getDateParts(KST_DATE_TIME_FORMATTER, date);
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`;
}

export function formatShortDate(value?: string | null) {
  if (!value) return '-';
  const date = parseUtcLikeDate(value);
  if (!date) return '-';
  const parts = getDateParts(KST_DATE_FORMATTER, date);
  return `${String(parts.year || '').slice(-2)}-${parts.month}-${parts.day}`;
}

export function toTimestamp(value?: string | null) {
  if (!value) return 0;
  const timestamp = parseUtcLikeDate(value)?.getTime() ?? Number.NaN;
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

export function formatLocaleDateTime(value?: string | null) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleString();
}

export function formatLocaleTime(value?: string | number | Date | null) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleTimeString();
}
