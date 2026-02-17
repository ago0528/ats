export type DiffSummary = {
  added: number;
  removed: number;
  modified: number;
  diffText: string;
};

function normalizeLines(text: string): string[] {
  if (!text) return [];
  return text.replace(/\r\n/g, '\n').split('\n');
}

export function calculateLineDiff(before: string, after: string): DiffSummary {
  const beforeLines = normalizeLines(before);
  const afterLines = normalizeLines(after);

  const dp = Array.from({ length: beforeLines.length + 1 }, () => new Array(afterLines.length + 1).fill(0));

  for (let i = 1; i <= beforeLines.length; i++) {
    for (let j = 1; j <= afterLines.length; j++) {
      if (beforeLines[i - 1] === afterLines[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  const operations: ('equal' | 'add' | 'remove')[] = [];
  let i = beforeLines.length;
  let j = afterLines.length;

  while (i > 0 || j > 0) {
    if (
      i > 0
      && j > 0
      && beforeLines[i - 1] === afterLines[j - 1]
      && dp[i][j] === dp[i - 1][j - 1] + 1
    ) {
      operations.push('equal');
      i -= 1;
      j -= 1;
      continue;
    }

    if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      operations.push('add');
      j -= 1;
      continue;
    }

    if (i > 0) {
      operations.push('remove');
      i -= 1;
      continue;
    }

    operations.push('add');
    j -= 1;
  }

  operations.reverse();

  let added = 0;
  let removed = 0;
  let modified = 0;
  let cursor = 0;
  while (cursor < operations.length) {
    if (operations[cursor] === 'equal') {
      cursor += 1;
      continue;
    }

    let removeCount = 0;
    let addCount = 0;

    while (operations[cursor] === 'remove') {
      removeCount += 1;
      cursor += 1;
    }

    while (operations[cursor] === 'add') {
      addCount += 1;
      cursor += 1;
    }

    const pairCount = Math.min(removeCount, addCount);
    modified += pairCount;
    removed += removeCount - pairCount;
    added += addCount - pairCount;
  }

  const diffLines: string[] = [];
  let oldPointer = 0;
  let newPointer = 0;
  for (const op of operations) {
    if (op === 'equal') {
      diffLines.push(` ${beforeLines[oldPointer] ?? ''}`);
      oldPointer += 1;
      newPointer += 1;
      continue;
    }

    if (op === 'remove') {
      diffLines.push(`- ${beforeLines[oldPointer] ?? ''}`);
      oldPointer += 1;
      continue;
    }

    diffLines.push(`+ ${afterLines[newPointer] ?? ''}`);
    newPointer += 1;
  }

  return {
    added,
    removed,
    modified,
    diffText: diffLines.join('\n'),
  };
}

export function getLengthDelta(before: string, after: string) {
  const delta = after.length - before.length;
  if (delta === 0) return '0';
  if (delta > 0) return `+${delta}`;
  return `${delta}`;
}
