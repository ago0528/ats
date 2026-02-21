import type { Environment } from '../../app/EnvironmentScope';

export type QueryCategory = 'Happy path' | 'Edge case' | 'Adversarial input' | string;
export type ValidationRunMode = 'REGISTERED' | 'AD_HOC';

export type QueryGroup = {
  id: string;
  groupName: string;
  description: string;
  llmEvalCriteriaDefault: Record<string, unknown> | string;
  defaultTargetAssistant: string;
  queryCount: number;
  createdAt?: string;
  updatedAt?: string;
};

export type ValidationQuery = {
  id: string;
  queryText: string;
  expectedResult: string;
  category: QueryCategory;
  groupId?: string | null;
  groupName?: string;
  llmEvalCriteria: Record<string, unknown> | string;
  logicFieldPath: string;
  logicExpectedValue: string;
  contextJson: string;
  targetAssistant: string;
  createdBy: string;
  createdAt?: string;
  updatedAt?: string;
  latestRunSummary?: {
    executedAt?: string;
    logicResult?: string;
    llmStatus?: string;
  };
  testSetUsage?: {
    count: number;
    testSetNames: string[];
  };
};

export type QueryBulkUpdatePreviewStatus =
  | 'planned-update'
  | 'unchanged'
  | 'unmapped-query-id'
  | 'missing-query-id'
  | 'duplicate-query-id';

export type QueryBulkUpdatePreviewRow = {
  rowNo: number;
  queryId: string;
  queryText: string;
  status: QueryBulkUpdatePreviewStatus | string;
  changedFields: string[];
};

export type QueryBulkUpdatePreviewResult = {
  totalRows: number;
  validRows: number;
  plannedUpdateCount: number;
  unchangedCount: number;
  unmappedQueryCount: number;
  missingQueryIdRows: number[];
  duplicateQueryIdRows?: number[];
  unmappedQueryRows: number[];
  unmappedQueryIds: string[];
  groupsToCreate: string[];
  groupsToCreateRows: number[];
  previewRows: QueryBulkUpdatePreviewRow[];
};

export type QueryBulkUpdateResult = {
  requestedRowCount: number;
  updatedCount: number;
  unchangedCount: number;
  skippedUnmappedCount: number;
  skippedMissingIdCount: number;
  skippedDuplicateQueryIdCount?: number;
  createdGroupNames: string[];
};

export type ValidationRun = {
  id: string;
  name?: string;
  mode: ValidationRunMode;
  environment: Environment;
  status: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED' | string;
  evalStatus?: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED' | string;
  baseRunId?: string | null;
  testSetId?: string | null;
  agentId: string;
  testModel: string;
  evalModel: string;
  repeatInConversation: number;
  conversationRoomCount: number;
  agentParallelCalls: number;
  timeoutMs: number;
  options?: Record<string, unknown>;
  totalItems: number;
  doneItems: number;
  errorItems: number;
  llmDoneItems: number;
  createdAt?: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  evalStartedAt?: string | null;
  evalFinishedAt?: string | null;
};

export type ValidationRunItem = {
  id: string;
  runId: string;
  queryId?: string | null;
  ordinal: number;
  queryText: string;
  expectedResult: string;
  category: QueryCategory;
  appliedCriteria: Record<string, unknown> | string;
  logicFieldPath: string;
  logicExpectedValue: string;
  contextJson?: string;
  targetAssistant?: string;
  conversationRoomIndex: number;
  repeatIndex: number;
  conversationId: string;
  rawResponse: string;
  latencyMs?: number | null;
  error: string;
  rawJson: string;
  executedAt?: string | null;
  logicEvaluation?: {
    result: string;
    evalItems: Record<string, unknown> | string;
    failReason: string;
    evaluatedAt?: string;
  } | null;
  llmEvaluation?: {
    status: string;
    evalModel: string;
    metricScores: Record<string, unknown> | string;
    totalScore?: number | null;
    comment: string;
    evaluatedAt?: string;
  } | null;
};

export type ValidationSettings = {
  environment: Environment;
  repeatInConversationDefault: number;
  conversationRoomCountDefault: number;
  agentParallelCallsDefault: number;
  timeoutMsDefault: number;
  testModelDefault: string;
  evalModelDefault: string;
  paginationPageSizeLimitDefault: number;
  updatedAt?: string;
};

export type ValidationRunCreateRequest = {
  mode: ValidationRunMode;
  environment: Environment;
  name?: string;
  testSetId?: string;
  agentId?: string;
  testModel?: string;
  evalModel?: string;
  repeatInConversation?: number;
  conversationRoomCount?: number;
  agentParallelCalls?: number;
  timeoutMs?: number;
  queryIds?: string[];
  adHocQuery?: {
    queryText: string;
    expectedResult?: string;
    category?: QueryCategory;
    llmEvalCriteria?: Record<string, unknown> | string;
    logicFieldPath?: string;
    logicExpectedValue?: string;
  };
};

export type ValidationTestSetConfig = {
  agentId?: string;
  testModel?: string;
  evalModel?: string;
  repeatInConversation?: number;
  conversationRoomCount?: number;
  agentParallelCalls?: number;
  timeoutMs?: number;
};

export type QuerySelectionFilter = {
  q?: string;
  category?: string[];
  groupId?: string[];
};

export type QuerySelectionPayload = {
  mode: 'ids' | 'filtered';
  queryIds?: string[];
  filter?: QuerySelectionFilter;
  excludedQueryIds?: string[];
};

export type ValidationTestSetItem = {
  id: string;
  queryId: string;
  ordinal: number;
  queryText?: string;
  category?: QueryCategory;
  groupId?: string | null;
  groupName?: string;
  targetAssistant?: string;
};

export type ValidationTestSet = {
  id: string;
  name: string;
  description: string;
  config: ValidationTestSetConfig;
  itemCount: number;
  createdAt?: string;
  updatedAt?: string;
  queryIds?: string[];
  items?: ValidationTestSetItem[];
};

export type ValidationTestSetAppendQueriesResult = {
  testSetId: string;
  requestedCount: number;
  addedCount: number;
  skippedCount: number;
  itemCount: number;
};
