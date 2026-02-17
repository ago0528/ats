export const QUERY_CATEGORY_OPTIONS = [
  { label: 'Happy path', value: 'Happy path' },
  { label: 'Edge case', value: 'Edge case' },
  { label: 'Adversarial input', value: 'Adversarial input' },
] as const;

export const RUN_ITEM_INITIAL_COLUMN_WIDTHS = {
  ordinal: 72,
  queryText: 320,
  roomRepeat: 96,
  rawResponse: 260,
  error: 220,
  logic: 90,
  llm: 110,
  actions: 140,
};

export const HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS = {
  ordinal: 72,
  queryText: 320,
  roomRepeat: 96,
  executedAt: 160,
  rawResponse: 260,
  error: 220,
  logic: 90,
  llm: 110,
};

export const HISTORY_INITIAL_COLUMN_WIDTHS = {
  runId: 260,
  mode: 110,
  status: 120,
  agentId: 220,
  items: 180,
  createdAt: 160,
};
