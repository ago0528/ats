import { api } from './client';
import type {
  QueryGroup,
  ValidationTestSet,
  ValidationTestSetConfig,
  ValidationQuery,
  ValidationRun,
  ValidationRunCreateRequest,
  ValidationRunItem,
  ValidationSettings,
} from './types/validation';
import type { Environment } from '../app/EnvironmentScope';

export async function listQueryGroups(params?: { q?: string; offset?: number; limit?: number }) {
  const { data } = await api.get<{ items: QueryGroup[]; total: number }>('/query-groups', { params });
  return data;
}

export async function createQueryGroup(payload: {
  groupName: string;
  description?: string;
  llmEvalCriteriaDefault?: Record<string, unknown> | string;
  defaultTargetAssistant?: string;
}) {
  const { data } = await api.post<QueryGroup>('/query-groups', payload);
  return data;
}

export async function updateQueryGroup(
  groupId: string,
  payload: Partial<{ groupName: string; description: string; llmEvalCriteriaDefault: Record<string, unknown> | string; defaultTargetAssistant: string }>,
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
  llmEvalCriteria?: Record<string, unknown> | string;
  logicFieldPath?: string;
  logicExpectedValue?: string;
  contextJson?: string;
  targetAssistant?: string;
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
    llmEvalCriteria: Record<string, unknown> | string;
    logicFieldPath: string;
    logicExpectedValue: string;
    contextJson: string;
    targetAssistant: string;
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
  }>(
    '/queries/bulk-upload/preview',
    formData,
  );
  return data;
}

export async function listValidationRuns(params?: {
  environment?: Environment;
  testSetId?: string;
  status?: string;
  offset?: number;
  limit?: number;
}) {
  const { data } = await api.get<{ items: ValidationRun[]; total: number }>('/validation-runs', { params });
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

export async function listValidationRunItems(runId: string, params?: { offset?: number; limit?: number }) {
  const { data } = await api.get<{ items: ValidationRunItem[]; total: number }>(`/validation-runs/${runId}/items`, { params });
  return data;
}

export async function executeValidationRun(runId: string, payload: { bearer: string; cms: string; mrs: string; idempotencyKey?: string }) {
  const { data } = await api.post<{ jobId: string; status: string }>(`/validation-runs/${runId}/execute`, payload);
  return data;
}

export async function evaluateValidationRun(
  runId: string,
  payload: { openaiModel?: string; maxChars?: number; maxParallel?: number },
) {
  const { data } = await api.post<{ jobId: string; status: string }>(`/validation-runs/${runId}/evaluate`, payload);
  return data;
}

export async function rerunValidationRun(runId: string) {
  const { data } = await api.post<ValidationRun>(`/validation-runs/${runId}/rerun`);
  return data;
}

export function buildValidationRunExportUrl(runId: string) {
  return `${api.defaults.baseURL}/validation-runs/${encodeURIComponent(runId)}/export.xlsx`;
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
    llmEvalCriteria?: Record<string, unknown> | string;
    logicFieldPath?: string;
    logicExpectedValue?: string;
  },
) {
  const { data } = await api.post<{ queryId: string }>(`/validation-runs/${runId}/items/${itemId}/save-query`, payload);
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

export async function listValidationTestSets(params?: { q?: string; offset?: number; limit?: number }) {
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

export async function createRunFromValidationTestSet(
  testSetId: string,
  payload: {
    environment: Environment;
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
    logicPassRate: number;
    llmMetricAverages: Record<string, number>;
    failurePatterns: Array<{ category: string; count: number }>;
  }>(`/validation-dashboard/groups/${groupId}`);
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
