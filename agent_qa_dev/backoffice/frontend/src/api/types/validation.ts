import type { Environment } from '../../app/EnvironmentScope';

export type QueryCategory = 'Happy path' | 'Edge case' | 'Adversarial input' | string;

export type QueryGroup = {
  id: string;
  groupName: string;
  description: string;
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

export type ValidationRunExpectedBulkPreviewStatus =
  | 'planned-update'
  | 'unchanged'
  | 'unmapped-item-id'
  | 'missing-item-id'
  | 'duplicate-item-id';

export type ValidationRunExpectedBulkPreviewRow = {
  rowNo: number;
  itemId: string;
  status: ValidationRunExpectedBulkPreviewStatus | string;
  changedFields: string[];
};

export type ValidationRunExpectedBulkPreviewResult = {
  totalRows: number;
  validRows: number;
  plannedUpdateCount: number;
  unchangedCount: number;
  invalidRows: number[];
  missingItemIdRows: number[];
  duplicateItemIdRows: number[];
  unmappedItemRows: number[];
  previewRows: ValidationRunExpectedBulkPreviewRow[];
  remainingMissingExpectedCountAfterApply: number;
};

export type ValidationRunExpectedBulkUpdateResult = {
  requestedRowCount: number;
  updatedCount: number;
  unchangedCount: number;
  skippedMissingItemIdCount: number;
  skippedDuplicateItemIdCount: number;
  skippedUnmappedCount: number;
  evalReset: boolean;
  remainingMissingExpectedCount: number;
};

export type ValidationRun = {
  id: string;
  name?: string;
  environment: Environment;
  status: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED' | string;
  evalStatus?: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED' | string;
  baseRunId?: string | null;
  testSetId?: string | null;
  agentId: string;
  testModel: string;
  evalModel: string;
  // Room batch count. Rooms are processed sequentially (room1 -> room2 ...).
  repeatInConversation: number;
  conversationRoomCount: number;
  // Query-level parallel worker count per room batch.
  agentParallelCalls: number;
  timeoutMs: number;
  options?: Record<string, unknown>;
  totalItems: number;
  doneItems: number;
  errorItems: number;
  llmDoneItems: number;
  averageResponseTimeSec?: number | null;
  scoreSummary?: {
    totalItems: number;
    executedItems: number;
    errorItems: number;
    logicPassItems: number;
    logicPassRate: number;
    llmDoneItems: number;
    llmMetricAverages: Record<string, number>;
    llmTotalScoreAvg: number | null;
  } | null;
  createdAt?: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  evalStartedAt?: string | null;
  evalFinishedAt?: string | null;
};

export type ValidationRunUpdateRequest = {
  name?: string;
  agentId?: string;
  evalModel?: string;
  repeatInConversation?: number;
  conversationRoomCount?: number;
  agentParallelCalls?: number;
  timeoutMs?: number;
  context?: Record<string, unknown> | null;
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
  // Conversation ID from each executed item. Same room does not guarantee a shared ID.
  conversationId: string;
  rawResponse: string;
  latencyMs?: number | null;
  responseTimeSec?: number | null;
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

export type ValidationDashboardScoringMetric = {
  score?: number | null;
  sampleCount?: number;
};

export type ValidationDashboardConsistencyMetric = {
  status: 'READY' | 'PENDING' | string;
  score?: number | null;
  eligibleQueryCount: number;
  consistentQueryCount?: number;
};

export type ValidationDashboardLatencyMetric = {
  avgSec?: number | null;
  p50Sec?: number | null;
  p90Sec?: number | null;
  count: number;
};

export type ValidationDashboardStabilityMetric = {
  score?: number | null;
  errorRate: number;
  emptyRate: number;
};

export type ValidationDashboardScoring = {
  intent: ValidationDashboardScoringMetric;
  accuracy: ValidationDashboardScoringMetric & {
    legacyFallbackCount?: number;
    accuracyFallbackCount?: number;
    accuracyExtractFallbackCount?: number;
    accuracyFallbackRate?: number;
  };
  consistency: ValidationDashboardConsistencyMetric;
  latencySingle: ValidationDashboardLatencyMetric;
  latencyMulti: ValidationDashboardLatencyMetric;
  latencyUnclassifiedCount?: number;
  stability: ValidationDashboardStabilityMetric;
};

export type ValidationDashboardDistributions = {
  scoreBuckets: Record<string, number>;
};

export type ValidationRunCreateRequest = {
  environment: Environment;
  name?: string;
  testSetId?: string;
  context?: Record<string, unknown>;
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
  context?: Record<string, unknown>;
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

export type ValidationRunActivityItem = {
  runId: string;
  runName: string;
  testSetId?: string | null;
  status: ValidationRun['status'];
  evalStatus?: ValidationRun['evalStatus'];
  totalItems: number;
  doneItems: number;
  errorItems: number;
  llmDoneItems: number;
  createdAt?: string;
  startedAt?: string | null;
  evalStartedAt?: string | null;
  isRead: boolean;
};

export type ValidationRunActivityResponse = {
  items: ValidationRunActivityItem[];
  unreadCount: number;
};

export type ValidationRunActivityReadRequest = {
  environment: Environment;
  actorKey: string;
  runIds?: string[];
  markAll?: boolean;
};
