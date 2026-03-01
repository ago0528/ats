export type PromptSnapshotData = {
  before: string;
  after: string;
  currentPrompt: string;
  previousPrompt: string;
};

export type EvalPromptSnapshotData = {
  promptKey: string;
  currentPrompt: string;
  previousPrompt: string;
  currentVersionLabel: string;
  previousVersionLabel: string;
  updatedAt: string;
  updatedBy: string;
};

type ApiResponse = {
  before?: unknown;
  after?: unknown;
  currentPrompt?: unknown;
  previousPrompt?: unknown;
};

type EvalPromptApiResponse = {
  promptKey?: unknown;
  currentPrompt?: unknown;
  previousPrompt?: unknown;
  currentVersionLabel?: unknown;
  previousVersionLabel?: unknown;
  updatedAt?: unknown;
  updatedBy?: unknown;
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

export function normalizeEvalPromptSnapshot(data: EvalPromptApiResponse | null | undefined): EvalPromptSnapshotData {
  const promptKey = asString(data?.promptKey);
  const currentPrompt = asString(data?.currentPrompt);
  const previousPrompt = asString(data?.previousPrompt);
  const currentVersionLabel = asString(data?.currentVersionLabel);
  const previousVersionLabel = asString(data?.previousVersionLabel);
  const updatedAt = asString(data?.updatedAt);
  const updatedBy = asString(data?.updatedBy) || 'system';

  return {
    promptKey,
    currentPrompt,
    previousPrompt,
    currentVersionLabel,
    previousVersionLabel,
    updatedAt,
    updatedBy,
  };
}
