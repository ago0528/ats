export function splitCsvLine(raw: string): string[] {
  const values: string[] = [];
  let cell = '';
  let inQuote = false;

  for (let index = 0; index < raw.length; index += 1) {
    const char = raw[index];

    if (char === '"') {
      if (inQuote && raw[index + 1] === '"') {
        cell += '"';
        index += 1;
      } else {
        inQuote = !inQuote;
      }
      continue;
    }

    if (char === ',' && !inQuote) {
      values.push(cell.trim());
      cell = '';
      continue;
    }

    cell += char;
  }

  values.push(cell.trim());
  return values;
}

export function normalizeCsvCell(value: string) {
  return value.replace(/^"|"$/g, '').trim();
}

export function resolveColumnIndex(headers: string[], candidates: string[]) {
  return headers.findIndex((header) => candidates.some((candidate) => candidate === header));
}

export function normalizeCsvText(raw: string) {
  return raw.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
}

export function toNormalizedCsvLines(raw: string) {
  return normalizeCsvText(raw)
    .split('\n')
    .map((line) => line.replace(/\uFEFF/g, ''))
    .filter((line) => line.trim().length > 0);
}
