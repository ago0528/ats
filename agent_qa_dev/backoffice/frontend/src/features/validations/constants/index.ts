export const QUERY_CATEGORY_OPTIONS = [
  { label: 'Happy path', value: 'Happy path' },
  { label: 'Edge case', value: 'Edge case' },
  { label: 'Adversarial input', value: 'Adversarial input' },
] as const;

export const AGENT_MODE_OPTIONS: { label: string; value: string }[] = [
  { label: 'AUTO', value: 'ORCHESTRATOR_ASSISTANT' },
  { label: '실행 에이전트', value: 'RECRUIT_PLAN_ASSISTANT' },
  { label: '채용 생성 에이전트', value: 'RECRUIT_PLAN_CREATE_ASSISTANT' },
  { label: '지원자 관리 에이전트', value: 'RESUME_ASSISTANT' },
  { label: '위키 에이전트', value: 'RECRUIT_WIKI_ASSISTANT' },
];

export const DEFAULT_AGENT_MODE_VALUE = 'ORCHESTRATOR_ASSISTANT';

export const EVAL_MODEL_OPTIONS: { label: string; value: string }[] = [
  { label: 'gpt-5.2', value: 'gpt-5.2' },
  { label: 'gpt-5-mini', value: 'gpt-5-mini' },
];

export const DEFAULT_EVAL_MODEL_VALUE = 'gpt-5.2';

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
  responseTimeSec: 140,
  error: 220,
  logic: 90,
  llm: 110,
};

export const HISTORY_INITIAL_COLUMN_WIDTHS = {
  runId: 260,
  runName: 220,
  testSet: 240,
  executionStatus: 130,
  evaluationStatus: 130,
  executionConfig: 240,
  agentMode: 220,
  items: 180,
  llmEvalProgress: 140,
  evalModel: 120,
};
