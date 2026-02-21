export type PromptSnapshotData = {
  before: string;
  after: string;
  currentPrompt: string;
  previousPrompt: string;
};

type ApiResponse = {
  before?: unknown;
  after?: unknown;
  currentPrompt?: unknown;
  previousPrompt?: unknown;
};

const LINE_TERMINATOR_REGEX = /\r\n|\r|\u2028|\u2029/g;

export function normalizePromptText(text: string): string {
  return text.replace(LINE_TERMINATOR_REGEX, '\n');
}

function asString(value: unknown): string {
  return typeof value === 'string' ? normalizePromptText(value) : '';
}

export function normalizePromptSnapshot(data: ApiResponse | null | undefined): PromptSnapshotData {
  const before = asString(data?.before);
  const after = asString(data?.after);
  const hasCurrentPrompt = typeof data?.currentPrompt === 'string';
  const hasPreviousPrompt = typeof data?.previousPrompt === 'string';

  const currentPrompt = hasCurrentPrompt ? asString(data?.currentPrompt) : (after || before || '');
  const previousPrompt = hasPreviousPrompt ? asString(data?.previousPrompt) : before;

  return {
    before,
    after,
    currentPrompt,
    previousPrompt,
  };
}
