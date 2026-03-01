import { api } from './client';
import type {
  QueryBulkUpdatePreviewResult,
  QueryBulkUpdateResult,
  QuerySelectionPayload,
  QueryGroup,
  ValidationTestSet,
  ValidationTestSetAppendQueriesResult,
  ValidationTestSetConfig,
  ValidationQuery,
  ValidationRun,
  ValidationRunActivityReadRequest,
  ValidationRunActivityResponse,
  ValidationRunCreateRequest,
  ValidationRunUpdateRequest,
  ValidationRunItem,
  ValidationRunExpectedBulkPreviewResult,
  ValidationRunExpectedBulkUpdateResult,
  ValidationSettings,
  ValidationDashboardScoring,
  ValidationDashboardDistributions,
} from './types/validation';
import type { Environment } from '../app/EnvironmentScope';

export async function listQueryGroups(params?: { q?: string; offset?: number; limit?: number }) {
  const { data } = await api.get<{ items: QueryGroup[]; total: number }>('/query-groups', { params });
  return data;
}

export async function createQueryGroup(payload: {
  groupName: string;
  description?: string;
}) {
  const { data } = await api.post<QueryGroup>('/query-groups', payload);
  return data;
}

export async function updateQueryGroup(
  groupId: string,
  payload: Partial<{ groupName: string; description: string }>,
) {
  const { data } = await api.patch<QueryGroup>(`/query-groups/${groupId}`, payload);
  return data;
}

export async function deleteQueryGroup(groupId: string) {
  const { data } = await api.delete<{ ok: boolean }>(`/query-groups/${groupId}`);
  return data;
}

export async function listQueries(params?: {
  q?: string;
  category?: string | string[];
  groupId?: string | string[];
  queryIds?: string[];
  offset?: number;
  limit?: number;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}) {
  const normalizedParams = params
    ? {
      ...params,
      category: Array.isArray(params.category) ? params.category.join(',') : params.category,
      groupId: Array.isArray(params.groupId) ? params.groupId.join(',') : params.groupId,
      queryIds: params.queryIds?.join(','),
    }
    : undefined;
  const { data } = await api.get<{ items: ValidationQuery[]; total: number }>('/queries', { params: normalizedParams });
  return data;
}

export async function createQuery(payload: {
  queryText: string;
  expectedResult?: string;
  category?: string;
  groupId?: string;
  createdBy?: string;
}) {
  const { data } = await api.post<ValidationQuery>('/queries', payload);
  return data;
}

export async function updateQuery(
  queryId: string,
  payload: Partial<{
    queryText: string;
    expectedResult: string;
    category: string;
    groupId: string | null;
  }>,
) {
  const { data } = await api.patch<ValidationQuery>(`/queries/${queryId}`, payload);
  return data;
}

export async function deleteQuery(queryId: string) {
  const { data } = await api.delete<{ ok: boolean }>(`/queries/${queryId}`);
  return data;
}

export async function uploadQueriesBulk(file: File, groupId?: string, createdBy = 'unknown') {
  const formData = new FormData();
  formData.append('file', file);
  if (groupId) {
    formData.append('groupId', groupId);
  }
  formData.append('createdBy', createdBy);
  const { data } = await api.post<{
    createdCount: number;
    invalidRows: number[];
    queryIds: string[];
    unmappedGroupRows?: number[];
    unmappedGroupValues?: string[];
    createdGroupNames?: string[];
    invalidLatencyClassRows?: number[];
  }>(
    '/queries/bulk-upload',
    formData,
  );
  return data;
}

export async function previewQueriesBulkUpload(file: File, groupId?: string) {
  const formData = new FormData();
  formData.append('file', file);
  if (groupId) {
    formData.append('groupId', groupId);
  }
  const { data } = await api.post<{
    totalRows: number;
    validRows: number;
    invalidRows: number[];
    missingQueryRows: number[];
    groupsToCreate: string[];
    groupsToCreateRows: number[];
    invalidLatencyClassRows?: number[];
  }>(
    '/queries/bulk-upload/preview',
    formData,
  );
  return data;
}

export async function previewQueriesBulkUpdate(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post<QueryBulkUpdatePreviewResult>(
    '/queries/bulk-update/preview',
    formData,
  );
  return data;
}

export async function updateQueriesBulk(file: File, options?: { allowCreateGroups?: boolean; skipUnmappedQueryIds?: boolean }) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('allowCreateGroups', String(Boolean(options?.allowCreateGroups)));
  formData.append('skipUnmappedQueryIds', String(Boolean(options?.skipUnmappedQueryIds)));
  const { data } = await api.post<QueryBulkUpdateResult>(
    '/queries/bulk-update',
    formData,
  );
  return data;
}

export async function listValidationRuns(params?: {
  environment?: Environment;
  testSetId?: string;
  status?: string;
  evaluationStatus?: string;
  offset?: number;
  limit?: number;
}) {
  const { data } = await api.get<{ items: ValidationRun[]; total: number }>('/validation-runs', { params });
  return data;
}

export async function listValidationRunActivity(params: {
  environment: Environment;
  actorKey: string;
  limit?: number;
}) {
  const { data } = await api.get<ValidationRunActivityResponse>('/validation-run-activity', { params });
  return data;
}

export async function markValidationRunActivityRead(payload: ValidationRunActivityReadRequest) {
  const { data } = await api.post<{ updatedCount: number }>('/validation-run-activity/read', payload);
  return data;
}

export async function createValidationRun(payload: ValidationRunCreateRequest) {
  const { data } = await api.post<ValidationRun>('/validation-runs', payload);
  return data;
}

export async function getValidationRun(runId: string) {
  const { data } = await api.get<ValidationRun>(`/validation-runs/${runId}`);
  return data;
}

export async function updateValidationRun(runId: string, payload: ValidationRunUpdateRequest) {
  const { data } = await api.patch<ValidationRun>(`/validation-runs/${runId}`, payload);
  return data;
}

export async function deleteValidationRun(runId: string) {
  const { data } = await api.delete<{ ok: boolean }>(`/validation-runs/${runId}`);
  return data;
}

export async function listValidationRunItems(runId: string, params?: { offset?: number; limit?: number }) {
  const { data } = await api.get<{ items: ValidationRunItem[]; total: number }>(`/validation-runs/${runId}/items`, { params });
  return data;
}

export async function executeValidationRun(
  runId: string,
  payload: { bearer: string; cms: string; mrs: string; idempotencyKey?: string; itemIds?: string[] },
) {
  const { data } = await api.post<{ jobId: string; status: string }>(`/validation-runs/${runId}/execute`, payload);
  return data;
}

export async function evaluateValidationRun(
  runId: string,
  payload: { openaiModel?: string; maxChars?: number; maxParallel?: number; itemIds?: string[] },
) {
  const { data } = await api.post<{ jobId: string; status: string }>(`/validation-runs/${runId}/evaluate`, payload);
  return data;
}

export async function cancelValidationRunEvaluation(runId: string) {
  const { data } = await api.post<{
    ok: boolean;
    action: 'CANCEL_REQUESTED' | 'ALREADY_REQUESTED' | 'RECOVERED_STALE' | string;
    evalStatus: 'RUNNING' | 'PENDING' | string;
    evalCancelRequested: boolean;
  }>(`/validation-runs/${runId}/evaluate/cancel`);
  return data;
}

export async function rerunValidationRun(runId: string) {
  const { data } = await api.post<ValidationRun>(`/validation-runs/${runId}/rerun`);
  return data;
}

export function buildValidationRunExportUrl(runId: string, options?: { includeDebug?: boolean }) {
  const includeDebug = options?.includeDebug ? '?includeDebug=1' : '';
  return `${api.defaults.baseURL}/validation-runs/${encodeURIComponent(runId)}/export.xlsx${includeDebug}`;
}

export function buildValidationRunExpectedResultsTemplateUrl(runId: string) {
  return `${api.defaults.baseURL}/validation-runs/${encodeURIComponent(runId)}/expected-results/template.csv`;
}

export async function previewValidationRunExpectedResultsBulkUpdate(runId: string, file: File) {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post<ValidationRunExpectedBulkPreviewResult>(
    `/validation-runs/${runId}/expected-results/bulk-update/preview`,
    formData,
  );
  return data;
}

export async function updateValidationRunExpectedResultsBulk(runId: string, file: File) {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post<ValidationRunExpectedBulkUpdateResult>(
    `/validation-runs/${runId}/expected-results/bulk-update`,
    formData,
  );
  return data;
}

export async function saveValidationRunItemAsQuery(
  runId: string,
  itemId: string,
  payload: {
    groupId: string;
    category?: string;
    createdBy?: string;
    queryText?: string;
    expectedResult?: string;
  },
) {
  const { data } = await api.post<{ queryId: string }>(`/validation-runs/${runId}/items/${itemId}/save-query`, payload);
  return data;
}

export async function updateValidationRunItemSnapshot(
  runId: string,
  itemId: string,
  payload: {
    expectedResult?: string;
    latencyClass?: 'SINGLE' | 'MULTI' | 'UNCLASSIFIED' | null;
  },
) {
  const { data } = await api.patch<{ id: string; runId: string; expectedResult: string; latencyClass?: 'SINGLE' | 'MULTI' | 'UNCLASSIFIED' | null }>(
    `/validation-runs/${runId}/items/${itemId}`,
    payload,
  );
  return data;
}

export async function compareValidationRun(runId: string, baseRunId?: string) {
  const { data } = await api.get<{
    baseRunId?: string | null;
    delta: Record<string, unknown>;
    changedRows: Array<Record<string, unknown>>;
  }>(`/validation-runs/${runId}/compare`, { params: baseRunId ? { baseRunId } : undefined });
  return data;
}

export async function listValidationTestSets(params?: {
  q?: string;
  environment?: Environment;
  offset?: number;
  limit?: number;
}) {
  const { data } = await api.get<{ items: ValidationTestSet[]; total: number }>('/validation-test-sets', { params });
  return data;
}

export async function getValidationTestSet(testSetId: string) {
  const { data } = await api.get<ValidationTestSet>(`/validation-test-sets/${testSetId}`);
  return data;
}

export async function createValidationTestSet(payload: {
  name: string;
  description?: string;
  queryIds?: string[];
  querySelection?: QuerySelectionPayload;
  config?: ValidationTestSetConfig;
}) {
  const { data } = await api.post<ValidationTestSet>('/validation-test-sets', payload);
  return data;
}

export async function updateValidationTestSet(
  testSetId: string,
  payload: Partial<{ name: string; description: string; queryIds: string[]; config: ValidationTestSetConfig }>,
) {
  const { data } = await api.patch<ValidationTestSet>(`/validation-test-sets/${testSetId}`, payload);
  return data;
}

export async function deleteValidationTestSet(testSetId: string) {
  const { data } = await api.delete<{ ok: boolean }>(`/validation-test-sets/${testSetId}`);
  return data;
}

export async function cloneValidationTestSet(testSetId: string, payload?: { name?: string }) {
  const { data } = await api.post<ValidationTestSet>(`/validation-test-sets/${testSetId}/clone`, payload ?? {});
  return data;
}

export async function appendQueriesToValidationTestSet(
  testSetId: string,
  payload: {
    queryIds?: string[];
    querySelection?: QuerySelectionPayload;
  },
) {
  const { data } = await api.post<ValidationTestSetAppendQueriesResult>(
    `/validation-test-sets/${testSetId}/append-queries`,
    payload,
  );
  return data;
}

export async function createRunFromValidationTestSet(
  testSetId: string,
  payload: {
    name?: string;
    environment: Environment;
    context?: Record<string, unknown>;
    agentId?: string;
    testModel?: string;
    evalModel?: string;
    repeatInConversation?: number;
    conversationRoomCount?: number;
    agentParallelCalls?: number;
    timeoutMs?: number;
  },
) {
  const { data } = await api.post<ValidationRun>(`/validation-test-sets/${testSetId}/runs`, payload);
  return data;
}

export async function getValidationGroupDashboard(groupId: string) {
  const { data } = await api.get<{
    groupId: string;
    totalItems: number;
    llmMetricAverages: Record<string, number>;
    failurePatterns: Array<{ category: string; count: number }>;
  }>(`/validation-dashboard/groups/${groupId}`);
  return data;
}

export async function getValidationTestSetDashboard(
  testSetId: string,
  params?: { runId?: string; dateFrom?: string; dateTo?: string },
) {
  const { data } = await api.get<{
    testSetId: string;
    runCount: number;
    totalItems: number;
    executedItems: number;
    errorItems: number;
    llmMetricAverages: Record<string, number>;
    llmTotalScoreAverage: number | null;
    failurePatterns: Array<{ category: string; count: number }>;
    runSummaries: Array<{
      runId: string;
      status: string;
      evalStatus: string;
      createdAt?: string;
      finishedAt?: string | null;
      totalItems: number;
      executedItems: number;
      errorItems: number;
      llmDoneItems: number;
    }>;
    scoring?: ValidationDashboardScoring;
    distributions?: ValidationDashboardDistributions;
  }>(`/validation-dashboard/test-sets/${testSetId}`, { params });
  return data;
}

export async function getValidationSettings(environment: Environment) {
  const { data } = await api.get<ValidationSettings>(`/validation-settings/${environment}`);
  return data;
}

export async function updateValidationSettings(
  environment: Environment,
  payload: Partial<{
    repeatInConversationDefault: number;
    conversationRoomCountDefault: number;
    agentParallelCallsDefault: number;
    timeoutMsDefault: number;
    testModelDefault: string;
    evalModelDefault: string;
    paginationPageSizeLimitDefault: number;
  }>,
) {
  const { data } = await api.patch<ValidationSettings>(`/validation-settings/${environment}`, payload);
  return data;
}
