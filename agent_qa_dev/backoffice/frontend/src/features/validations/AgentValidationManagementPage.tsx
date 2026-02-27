import { useEffect, useMemo, useState } from 'react';
import {
  App,
  Button,
  Card,
  Col,
  DatePicker,
  Input,
  Row,
  Select,
  Space,
  Typography,
} from 'antd';
import { useLocation, useNavigate } from 'react-router-dom';

import {
  createRunFromValidationTestSet,
  deleteValidationRun,
  evaluateValidationRun,
  executeValidationRun,
  getValidationRun,
  getValidationTestSetDashboard,
  listValidationRunItems,
  listValidationRuns,
  listValidationTestSets,
  previewValidationRunExpectedResultsBulkUpdate,
  updateValidationRunItemSnapshot,
  updateValidationRun,
  updateValidationRunExpectedResultsBulk,
} from '../../api/validation';
import type {
  ValidationRun,
  ValidationRunItem,
  ValidationRunUpdateRequest,
  ValidationTestSet,
} from '../../api/types/validation';
import type { Environment } from '../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../app/types';
import { ValidationDashboardSection } from './components/ValidationDashboardSection';
import { ValidationHistoryDetailSection } from './components/ValidationHistoryDetailSection';
import { ValidationHistorySection } from './components/ValidationHistorySection';
import {
  ValidationRunSection,
  type RunCreateOverrides,
} from './components/ValidationRunSection';
import { useValidationColumns } from './hooks/useValidationColumns';
import { useValidationSectionMeta } from './hooks/useValidationSectionMeta';
import type { HistoryDetailTab, ValidationSection } from './types';
import { getEvaluationStateLabel } from './utils/runStatus';
import { resolveHistoryDetailTab } from '../../app/navigation/validationNavigation';

export type { ValidationSection } from './types';

export function AgentValidationManagementPage({
  environment,
  tokens,
  section = 'run',
  historyRunId,
  onOpenHistoryRunDetail,
  onBackToHistory,
  onOpenRunWorkspace,
}: {
  environment: Environment;
  tokens: RuntimeSecrets;
  section?: ValidationSection;
  historyRunId?: string;
  onOpenHistoryRunDetail?: (runId: string) => void;
  onBackToHistory?: () => void;
  onOpenRunWorkspace?: (payload: {
    runId: string;
    testSetId?: string | null;
  }) => void;
}) {
  const { message, modal } = App.useApp();
  const location = useLocation();
  const navigate = useNavigate();
  const [testSets, setTestSets] = useState<ValidationTestSet[]>([]);
  const [runs, setRuns] = useState<ValidationRun[]>([]);
  const [runItems, setRunItems] = useState<ValidationRunItem[]>([]);
  const [currentRun, setCurrentRun] = useState<ValidationRun | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string>('');
  const [selectedTestSetId, setSelectedTestSetId] = useState<string>('');
  const [runItemsCurrentPage, setRunItemsCurrentPage] = useState(1);
  const [runItemsPageSize, setRunItemsPageSize] = useState<number>(50);
  const [historyCurrentPage, setHistoryCurrentPage] = useState(1);
  const [historyPageSize, setHistoryPageSize] = useState<number>(50);
  const [historyExecutionStatusFilter, setHistoryExecutionStatusFilter] =
    useState<string>('');
  const [historyEvaluationStatusFilter, setHistoryEvaluationStatusFilter] =
    useState<string>('');
  const [historyTestSetFilter, setHistoryTestSetFilter] = useState<string>('');
  const [historyKeywordFilter, setHistoryKeywordFilter] = useState<string>('');
  const [historyCreatedAtFilter, setHistoryCreatedAtFilter] = useState<
    [Date | null, Date | null]
  >([null, null]);
  const [historySortOrder, setHistorySortOrder] = useState<
    'createdAt_desc' | 'createdAt_asc'
  >('createdAt_desc');
  const [loading, setLoading] = useState(false);
  const [forceRunRefreshUntil, setForceRunRefreshUntil] = useState(0);
  const [dashboardTestSetId, setDashboardTestSetId] = useState<string>('');
  const [dashboardData, setDashboardData] = useState<Record<
    string,
    unknown
  > | null>(null);

  const runQueryParams = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return {
      runId: params.get('runId') || '',
      testSetId: params.get('testSetId') || '',
    };
  }, [location.search]);

  const historyDetailTab = useMemo<HistoryDetailTab>(
    () => resolveHistoryDetailTab(location.search),
    [location.search],
  );

  const loadGroupsAndTestSets = async () => {
    try {
      const testSetData = await listValidationTestSets({
        limit: 500,
        environment,
      });
      setTestSets(testSetData.items);
      setDashboardTestSetId((prev) => prev || testSetData.items[0]?.id || '');
      setSelectedTestSetId((prev) => {
        if (runQueryParams.testSetId) return runQueryParams.testSetId;
        if (prev && testSetData.items.some((item) => item.id === prev))
          return prev;
        return testSetData.items[0]?.id || '';
      });
      setHistoryTestSetFilter((prev) => {
        if (prev && testSetData.items.some((item) => item.id === prev)) {
          return prev;
        }
        return '';
      });
    } catch (error) {
      console.error(error);
      message.error('검증 메타 데이터 조회에 실패했습니다.');
    }
  };

  const loadRuns = async (options?: {
    testSetId?: string;
    forceAll?: boolean;
    status?: string;
    evaluationStatus?: string;
  }) => {
    try {
      const shouldLoadAll = Boolean(options?.forceAll);
      const chunkSize = 300;
      const params = {
        environment,
        testSetId: shouldLoadAll
          ? undefined
          : (options?.testSetId ?? selectedTestSetId) || undefined,
        status: options?.status || undefined,
        evaluationStatus: options?.evaluationStatus || undefined,
      };

      if (!shouldLoadAll) {
        const runData = await listValidationRuns({
          ...params,
          limit: chunkSize,
        });
        setRuns(runData.items);
        return runData.items;
      }

      const loadedItems: ValidationRun[] = [];
      let offset = 0;
      while (true) {
        const runData = await listValidationRuns({
          ...params,
          offset,
          limit: chunkSize,
        });
        loadedItems.push(...runData.items);
        if (loadedItems.length >= runData.total || runData.items.length === 0) {
          break;
        }
        offset += chunkSize;
      }
      setRuns(loadedItems);
      return loadedItems;
    } catch (error) {
      console.error(error);
      message.error('질문 결과 조회에 실패했습니다.');
      return [];
    }
  };

  const loadRunDetail = async (runId: string) => {
    try {
      const [runData, itemData] = await Promise.all([
        getValidationRun(runId),
        listValidationRunItems(runId, { limit: 2000 }),
      ]);
      setCurrentRun(runData);
      setRunItems(itemData.items);
      setRunItemsCurrentPage(1);
      setSelectedRunId(runId);
      if (runData.testSetId) {
        setSelectedTestSetId(runData.testSetId);
      } else if (section === 'run') {
        setSelectedTestSetId('');
      }
    } catch (error) {
      console.error(error);
      message.error('런 상세 조회에 실패했습니다.');
    }
  };

  useEffect(() => {
    void loadGroupsAndTestSets();
  }, [environment]);

  useEffect(() => {
    if (section === 'history') {
      void loadRuns({
        forceAll: true,
        status: historyExecutionStatusFilter,
        evaluationStatus: historyEvaluationStatusFilter,
      });
      return;
    }
    if (section === 'history-detail' && historyRunId) {
      void loadRunDetail(historyRunId);
      return;
    }
    if (section !== 'run') return;
    void (async () => {
      const loadedRuns = await loadRuns({ forceAll: true });
      const runIdFromUrl = runQueryParams.runId;
      if (runIdFromUrl) {
        await loadRunDetail(runIdFromUrl);
        return;
      }
      const nextSelectedId =
        selectedRunId && loadedRuns.some((run) => run.id === selectedRunId)
          ? selectedRunId
          : loadedRuns[0]?.id;
      if (nextSelectedId) {
        await loadRunDetail(nextSelectedId);
      } else {
        setCurrentRun(null);
        setRunItems([]);
      }
    })();
  }, [
    section,
    environment,
    historyRunId,
    runQueryParams.runId,
    historyExecutionStatusFilter,
    historyEvaluationStatusFilter,
  ]);

  const historyTestSetFilterOptions = useMemo(() => {
    return [
      { label: '전체 테스트 세트', value: '' },
      ...testSets.map((testSet) => ({
        label: testSet.name,
        value: testSet.id,
      })),
    ];
  }, [testSets]);

  useEffect(() => {
    if (section !== 'run') return;
    if (!selectedRunId) return;
    if (!runs.some((run) => run.id === selectedRunId)) {
      return;
    }
    void loadRunDetail(selectedRunId);
  }, [selectedRunId]);

  useEffect(() => {
    if (section !== 'run') return;
    if (!currentRun) return;
    const isExecutionRunning = currentRun.status === 'RUNNING';
    const isEvaluationRunning =
      String(currentRun.evalStatus || '').toUpperCase() === 'RUNNING';
    const isInForcedRefreshWindow = forceRunRefreshUntil > Date.now();
    if (!isExecutionRunning && !isEvaluationRunning && !isInForcedRefreshWindow) return;
    const refreshIntervalMs = isExecutionRunning || isEvaluationRunning ? 2000 : 2500;
    const timer = window.setInterval(() => {
      void loadRunDetail(currentRun.id);
      void loadRuns({ forceAll: true });
    }, refreshIntervalMs);
    const timeout = isInForcedRefreshWindow
      ? window.setTimeout(
          () => setForceRunRefreshUntil(0),
          Math.max(0, forceRunRefreshUntil - Date.now()),
        )
      : null;
    return () => {
      window.clearInterval(timer);
      if (timeout) {
        window.clearTimeout(timeout);
      }
    };
  }, [
    section,
    currentRun?.id,
    currentRun?.status,
    currentRun?.evalStatus,
    forceRunRefreshUntil,
  ]);

  const triggerForceRunRefresh = () => {
    setForceRunRefreshUntil(Date.now() + 30_000);
  };

  useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(runItems.length / runItemsPageSize));
    if (runItemsCurrentPage > maxPage) {
      setRunItemsCurrentPage(maxPage);
    }
  }, [runItems.length, runItemsPageSize, runItemsCurrentPage]);

  useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(runs.length / historyPageSize));
    if (historyCurrentPage > maxPage) {
      setHistoryCurrentPage(maxPage);
    }
  }, [runs.length, historyPageSize, historyCurrentPage]);

  const handleCreateRunFromTestSet = async (
    testSetId: string,
    overrides: RunCreateOverrides,
  ) => {
    if (!testSetId) {
      message.warning('테스트 세트를 먼저 선택해 주세요.');
      return;
    }
    try {
      setLoading(true);
      const created = await createRunFromValidationTestSet(testSetId, {
        environment,
        ...overrides,
      });
      setSelectedTestSetId(testSetId);
      setCurrentRun(created);
      setSelectedRunId(created.id);
      await loadRuns({ forceAll: true });
      await loadRunDetail(created.id);
      message.success('Run을 생성했습니다.');
    } catch (error) {
      console.error(error);
      message.error('Run 생성에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async (itemIds?: string[]) => {
    if (!currentRun) return;
    const runId = currentRun.id;
    const scopedItemIds = (itemIds || [])
      .map((itemId) => String(itemId || '').trim())
      .filter(Boolean);
    if (itemIds && scopedItemIds.length === 0) {
      message.warning('재실행 대상 질의를 찾을 수 없습니다.');
      return;
    }
    const readErrorMessage = (error: unknown) => {
      if (typeof error === 'object' && error !== null) {
        const typed = error as {
          response?: {
            data?: {
              detail?: string;
              message?: string;
            } | string;
          };
          message?: string;
        };
        const responseData = typed.response?.data;
        if (responseData) {
          if (typeof responseData === 'string' && responseData) {
            return responseData;
          }
          if (responseData && typeof responseData === 'object') {
            if (typeof responseData.detail === 'string' && responseData.detail) {
              return responseData.detail;
            }
            if (typeof responseData.message === 'string' && responseData.message) {
              return responseData.message;
            }
          }
        }
        if (typed.message) {
          return typed.message;
        }
      }
      return '';
    };
    try {
      setLoading(true);
      await executeValidationRun(runId, {
        bearer: tokens.bearer,
        cms: tokens.cms,
        mrs: tokens.mrs,
        ...(scopedItemIds.length ? { itemIds: scopedItemIds } : {}),
      });
      triggerForceRunRefresh();
      message.success(
        scopedItemIds.length ? '선택한 질의를 재실행했습니다.' : '실행을 시작했습니다.',
      );
      await loadRunDetail(runId);
      await loadRuns({ forceAll: true });
    } catch (error) {
      console.error(error);
      const detail = readErrorMessage(error);
      if (
        scopedItemIds.length
        && detail === 'Only PENDING runs can be executed'
      ) {
        message.error(
          '질의별 재실행이 서버에 반영되지 않았습니다. 백엔드 배포 상태를 확인해 주세요. (Only PENDING runs can be executed)',
        );
      } else if (detail === 'Run is still executing') {
        message.error('현재 Run 실행이 진행 중이라 재실행할 수 없습니다.');
      } else if (detail === 'Evaluation is already running') {
        message.error('현재 Run 평가가 진행 중이라 재실행할 수 없습니다.');
      } else {
        message.error(
          detail
            ? `실행 요청에 실패했습니다. (${detail})`
            : '실행 요청에 실패했습니다.',
        );
      }
      await loadRunDetail(runId);
      await loadRuns({ forceAll: true });
    } finally {
      setLoading(false);
    }
  };

  const handleEvaluate = async (itemIds?: string[]) => {
    if (!currentRun) return;
    const readErrorMessage = (error: unknown) => {
      if (typeof error === 'object' && error !== null) {
        const typed = error as {
          response?: {
            data?: {
              detail?:
                | string
                | {
                  code?: string;
                  message?: string;
                  missingCount?: number;
                  sampleQueryIds?: string[];
                };
              message?: string;
            } | string;
          };
          message?: string;
        };
        const responseData = typed.response?.data;
        if (responseData) {
          if (typeof responseData === 'string' && responseData) {
            return responseData;
          }
          if (responseData && typeof responseData === 'object') {
            const nestedDetail = responseData.detail;
            if (typeof nestedDetail === 'object' && nestedDetail !== null) {
              if (nestedDetail.code === 'expected_result_missing') {
                const missingCount = Number(nestedDetail.missingCount || 0);
                const sampleQueryIds = Array.isArray(nestedDetail.sampleQueryIds)
                  ? nestedDetail.sampleQueryIds
                    .map((value) => String(value || '').trim())
                    .filter(Boolean)
                    .slice(0, 3)
                  : [];
                const sampleText = sampleQueryIds.length > 0
                  ? ` (예시 Query ID: ${sampleQueryIds.join(', ')})`
                  : '';
                return `평가를 시작할 수 없습니다. 기대 결과가 비어 있는 질의가 ${missingCount}건 있습니다.${sampleText}`;
              }
              if (nestedDetail.message) {
                return String(nestedDetail.message);
              }
            }
            if (typeof nestedDetail === 'string' && nestedDetail) {
              return nestedDetail;
            }
            if (responseData.message) {
              return String(responseData.message);
            }
          }
        }
        if (typed.message) {
          return typed.message;
        }
      }
      return '';
    };
    try {
      setLoading(true);
      await evaluateValidationRun(currentRun.id, {
        maxChars: 15000,
        ...(itemIds?.length ? { itemIds } : {}),
      });
      triggerForceRunRefresh();
      message.success(
        itemIds?.length ? '선택한 질의 재평가를 시작했습니다.' : '평가를 시작했습니다.',
      );
      await loadRunDetail(currentRun.id);
      await loadRuns({ forceAll: true });
    } catch (error) {
      console.error(error);
      const detail = readErrorMessage(error);
      message.error(
        detail
          ? `평가 요청에 실패했습니다. (${detail})`
          : '평가 요청에 실패했습니다.',
      );
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateRun = async (
    runId: string,
    payload: ValidationRunUpdateRequest,
  ) => {
    try {
      setLoading(true);
      await updateValidationRun(runId, payload);
      message.success('Run 정보를 수정했습니다.');
      if (section === 'run') {
        await loadRuns({ forceAll: true });
      } else {
        await loadRuns({ forceAll: true });
      }
      await loadRunDetail(runId);
    } catch (error) {
      console.error(error);
      message.error('Run 정보 수정에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteRun = async (runId: string) => {
    try {
      setLoading(true);
      await deleteValidationRun(runId);
      message.success('Run을 삭제했습니다.');

      if (section === 'run') {
        const refreshedRuns = await loadRuns({
          forceAll: true,
        });
        if (selectedRunId === runId) {
          if (refreshedRuns.length > 0) {
            setSelectedRunId(refreshedRuns[0].id);
            await loadRunDetail(refreshedRuns[0].id);
          } else {
            setCurrentRun(null);
            setRunItems([]);
            setSelectedRunId('');
            setRunItemsCurrentPage(1);
          }
        }
      } else {
        await loadRuns({ forceAll: true });
        onBackToHistory?.();
      }
    } catch (error) {
      console.error(error);
      message.error('Run 삭제에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handlePreviewExpectedResultsBulkUpdate = async (
    runId: string,
    file: File,
  ) => {
    try {
      setLoading(true);
      return await previewValidationRunExpectedResultsBulkUpdate(runId, file);
    } catch (error) {
      console.error(error);
      message.error('기대결과 일괄 업데이트 미리보기에 실패했습니다.');
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const handleApplyExpectedResultsBulkUpdate = async (
    runId: string,
    file: File,
  ) => {
    try {
      setLoading(true);
      const result = await updateValidationRunExpectedResultsBulk(runId, file);
      if (result.evalReset) {
        message.success('기대결과 일괄 업데이트 완료. 기존 평가결과가 초기화되었습니다.');
      } else {
        message.success('기대결과 일괄 업데이트가 완료되었습니다.');
      }
      if ((result.remainingMissingExpectedCount || 0) > 0) {
        message.warning(`남은 빈 기대결과 ${result.remainingMissingExpectedCount}건`);
      }
      await loadRunDetail(runId);
      if (section === 'run') {
        await loadRuns({ forceAll: true });
      } else {
        await loadRuns({ forceAll: true });
      }
      return result;
    } catch (error) {
      console.error(error);
      message.error('기대결과 일괄 업데이트에 실패했습니다.');
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateRunItemSnapshot = async (
    runId: string,
    itemId: string,
    payload: {
      expectedResult?: string;
      latencyClass?: 'SINGLE' | 'MULTI' | 'UNCLASSIFIED' | null;
    },
  ) => {
    const updated = await updateValidationRunItemSnapshot(runId, itemId, payload);
    if (payload.latencyClass !== undefined) {
      const expectedLatencyClass = payload.latencyClass || null;
      const returnedLatencyClass = updated.latencyClass || null;
      if (expectedLatencyClass !== returnedLatencyClass) {
        throw new Error('응답 속도 타입 저장이 반영되지 않았습니다. 백엔드 배포 상태를 확인해 주세요.');
      }
    }
    if (currentRun?.id === runId) {
      setRunItems((prev) =>
        prev.map((item) => {
          if (item.id !== itemId) return item;
          return {
            ...item,
            ...(updated.expectedResult !== undefined
              ? { expectedResult: updated.expectedResult }
              : {}),
            ...(updated.latencyClass !== undefined
              ? { latencyClass: updated.latencyClass }
              : {}),
          };
        }),
      );
    }
  };

  const handleLoadDashboard = async () => {
    if (!dashboardTestSetId) return;
    try {
      const data = await getValidationTestSetDashboard(dashboardTestSetId);
      setDashboardData(data as Record<string, unknown>);
    } catch (error) {
      console.error(error);
      message.error('대시보드 조회에 실패했습니다.');
    }
  };

  const testSetNameById = useMemo(
    () =>
      testSets.reduce<Record<string, string>>((acc, testSet) => {
        acc[testSet.id] = testSet.name;
        return acc;
      }, {}),
    [testSets],
  );

  const getHistoryEvaluationState = (run: ValidationRun) =>
    getEvaluationStateLabel(run);

  const filteredHistoryRuns = useMemo(() => {
    if (section !== 'history') return runs;

    const keyword = historyKeywordFilter.trim().toLowerCase();
    const [startAt, endAt] = historyCreatedAtFilter;
    const startBoundary = startAt
      ? new Date(startAt.getFullYear(), startAt.getMonth(), startAt.getDate())
      : null;
    const endBoundary = endAt
      ? new Date(
          endAt.getFullYear(),
          endAt.getMonth(),
          endAt.getDate(),
          23,
          59,
          59,
          999,
        )
      : null;

    const filtered = runs.filter((run) => {
      if (
        historyExecutionStatusFilter &&
        run.status !== historyExecutionStatusFilter
      ) {
        return false;
      }
      if (
        historyEvaluationStatusFilter &&
        getHistoryEvaluationState(run) !== historyEvaluationStatusFilter
      ) {
        return false;
      }
      if (historyTestSetFilter && run.testSetId !== historyTestSetFilter) {
        return false;
      }
      if (startBoundary || endBoundary) {
        const createdAt = run.createdAt ? new Date(run.createdAt) : null;
        if (!createdAt || Number.isNaN(createdAt.getTime())) return false;
        if (startBoundary && createdAt < startBoundary) return false;
        if (endBoundary && createdAt > endBoundary) return false;
      }
      if (!keyword) return true;

      const testSetName = run.testSetId
        ? testSetNameById[run.testSetId] || run.testSetId
        : '';
      const haystack = [run.id, run.name, testSetName]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(keyword);
    });

    return filtered.sort((a, b) => {
      const aCreated = a.createdAt ? new Date(a.createdAt).getTime() : 0;
      const bCreated = b.createdAt ? new Date(b.createdAt).getTime() : 0;

      if (historySortOrder === 'createdAt_asc') {
        return aCreated - bCreated;
      }
      return bCreated - aCreated;
    });
  }, [
    section,
    runs,
    historyKeywordFilter,
    historyEvaluationStatusFilter,
    historyExecutionStatusFilter,
    historyTestSetFilter,
    historyCreatedAtFilter,
    historySortOrder,
    testSetNameById,
  ]);

  useEffect(() => {
    if (section !== 'history') return;
    const maxPage = Math.max(
      1,
      Math.ceil(filteredHistoryRuns.length / historyPageSize),
    );
    if (historyCurrentPage > maxPage) {
      setHistoryCurrentPage(maxPage);
    }
  }, [
    filteredHistoryRuns.length,
    historyCurrentPage,
    historyPageSize,
    section,
  ]);

  useEffect(() => {
    if (section !== 'history') return;
    setHistoryCurrentPage(1);
  }, [
    historyEvaluationStatusFilter,
    historyExecutionStatusFilter,
    historyTestSetFilter,
    historyKeywordFilter,
    historyCreatedAtFilter,
    historySortOrder,
    section,
  ]);

  const handleResetHistoryFilters = () => {
    setHistoryExecutionStatusFilter('');
    setHistoryEvaluationStatusFilter('');
    setHistoryTestSetFilter('');
    setHistoryKeywordFilter('');
    setHistoryCreatedAtFilter([null, null]);
    setHistorySortOrder('createdAt_desc');
  };

  const hasExecutionResult = (item: ValidationRunItem) =>
    Boolean(item.executedAt)
    || Boolean(String(item.error || '').trim())
    || Boolean(String(item.rawResponse || '').trim());
  const hasEvaluationResult = (item: ValidationRunItem) =>
    Boolean(item.logicEvaluation)
    || Boolean(item.llmEvaluation);

  const runItemIdsByQueryId = useMemo(() => {
    const map = new Map<string, string[]>();
    runItems.forEach((item) => {
      const queryId = String(item.queryId || '').trim();
      if (!queryId) return;
      const currentIds = map.get(queryId) || [];
      currentIds.push(item.id);
      map.set(queryId, currentIds);
    });
    return map;
  }, [runItems]);

  const resolveScopedItemIds = (item: ValidationRunItem) => {
    const queryId = String(item.queryId || '').trim();
    if (!queryId) return [item.id];
    const ids = runItemIdsByQueryId.get(queryId) || [];
    if (ids.length === 0) return [item.id];
    return Array.from(new Set(ids.map((id) => String(id || '').trim()).filter(Boolean)));
  };

  const isRunBusy = useMemo(() => {
    if (!currentRun) return false;
    return currentRun.status === 'RUNNING'
      || String(currentRun.evalStatus || '').toUpperCase() === 'RUNNING';
  }, [currentRun]);

  const canReexecuteRunItem = (item: ValidationRunItem) => {
    if (!currentRun) return false;
    const scopedItemIds = resolveScopedItemIds(item);
    return !isRunBusy && scopedItemIds.length > 0;
  };

  const canReevaluateRunItem = (item: ValidationRunItem) => {
    if (!currentRun || isRunBusy) return false;
    const scopedItemIds = new Set(resolveScopedItemIds(item));
    return runItems.some((row) => scopedItemIds.has(row.id) && hasExecutionResult(row));
  };

  const handleReexecuteRunItem = (item: ValidationRunItem) => {
    const scopedItemIds = resolveScopedItemIds(item);
    const scopedItemSet = new Set(scopedItemIds);
    const needsConfirm = runItems.some(
      (row) =>
        scopedItemSet.has(row.id)
        && (hasExecutionResult(row) || hasEvaluationResult(row)),
    );
    const executeAction = async () => {
      await handleExecute(scopedItemIds);
    };
    if (!needsConfirm) {
      void executeAction();
      return;
    }
    modal.confirm({
      title: '해당 질의를 재실행 하시겠어요?',
      content: '실행, 평가 결과가 있는 경우 모든 데이터가 초기화돼요.',
      okText: '확인',
      cancelText: '취소',
      onOk: executeAction,
    });
  };

  const handleReevaluateRunItem = (item: ValidationRunItem) => {
    const scopedItemIds = resolveScopedItemIds(item);
    const scopedItemSet = new Set(scopedItemIds);
    const needsConfirm = runItems.some(
      (row) =>
        scopedItemSet.has(row.id)
        && (hasExecutionResult(row) || hasEvaluationResult(row)),
    );
    const evaluateAction = async () => {
      await handleEvaluate(scopedItemIds);
    };
    if (!needsConfirm) {
      void evaluateAction();
      return;
    }
    modal.confirm({
      title: '해당 질의를 재평가 하시겠어요?',
      content: '실행, 평가 결과가 있는 경우 모든 데이터가 초기화돼요.',
      okText: '확인',
      cancelText: '취소',
      onOk: evaluateAction,
    });
  };

  const { runItemColumns, historyColumns } =
    useValidationColumns({
      testSetNameById,
      canReexecuteRunItem,
      canReevaluateRunItem,
      onReexecuteRunItem: handleReexecuteRunItem,
      onReevaluateRunItem: handleReevaluateRunItem,
    });

  const { isHistoryDetailMatched } = useValidationSectionMeta({
    section,
    historyDetailTab,
    historyRunId,
    currentRun,
  });

  const handleChangeHistoryDetailTab = (nextTab: HistoryDetailTab) => {
    if (!historyRunId) return;
    const params = new URLSearchParams(location.search);
    params.set('tab', nextTab);
    navigate(`/validation/history/${encodeURIComponent(historyRunId)}?${params.toString()}`);
  };

  return (
    <Card className="backoffice-content-card">
      {section === 'run' ? (
        <ValidationRunSection
          loading={loading}
          testSets={testSets}
          selectedTestSetId={selectedTestSetId}
          setSelectedTestSetId={setSelectedTestSetId}
          runs={runs}
          selectedRunId={selectedRunId}
          setSelectedRunId={setSelectedRunId}
          currentRun={currentRun}
          runItems={runItems}
          handleCreateRun={handleCreateRunFromTestSet}
          handleExecute={handleExecute}
          handleEvaluate={handleEvaluate}
          handleUpdateRun={handleUpdateRun}
          handleDeleteRun={handleDeleteRun}
          runItemsCurrentPage={runItemsCurrentPage}
          runItemsPageSize={runItemsPageSize}
          setRunItemsCurrentPage={setRunItemsCurrentPage}
          setRunItemsPageSize={setRunItemsPageSize}
          runItemColumns={runItemColumns}
        />
      ) : null}

      {section === 'history' ? (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Space direction="horizontal" size={8} wrap>
            <Button onClick={handleResetHistoryFilters}>필터 초기화</Button>
            <Typography.Text type="secondary">
              전체 {runs.length}건 / 조회 {filteredHistoryRuns.length}건
            </Typography.Text>
          </Space>
          <Row gutter={[8, 8]} align="middle">
            <Col xs={24} sm={24} md={10} lg={9}>
              <Input.Search
                allowClear
                value={historyKeywordFilter}
                onChange={(event) =>
                  setHistoryKeywordFilter(event.target.value)
                }
                onSearch={(value) => setHistoryKeywordFilter(value)}
                placeholder="Run ID / Run 이름 / 테스트 세트"
              />
            </Col>
            <Col xs={24} sm={12} md={7} lg={6}>
              <Select
                style={{ width: '100%' }}
                value={historyTestSetFilter}
                onChange={setHistoryTestSetFilter}
                options={historyTestSetFilterOptions}
              />
            </Col>
            <Col xs={24} sm={12} md={7} lg={5}>
              <Select
                style={{ width: '100%' }}
                value={historyExecutionStatusFilter}
                onChange={setHistoryExecutionStatusFilter}
                options={[
                  { label: '전체 실행 상태', value: '' },
                  { label: '실행대기', value: 'PENDING' },
                  { label: '실행중', value: 'RUNNING' },
                  { label: '완료', value: 'DONE' },
                  { label: '실패', value: 'FAILED' },
                ]}
              />
            </Col>
            <Col xs={24} sm={12} md={7} lg={5}>
              <Select
                style={{ width: '100%' }}
                value={historyEvaluationStatusFilter}
                onChange={setHistoryEvaluationStatusFilter}
                options={[
                  { label: '전체 평가 상태', value: '' },
                  { label: '평가대기', value: '평가대기' },
                  { label: '평가중', value: '평가중' },
                  { label: '평가완료', value: '평가완료' },
                ]}
              />
            </Col>
            <Col xs={24} sm={12} md={7} lg={6}>
              <DatePicker.RangePicker
                style={{ width: '100%' }}
                value={historyCreatedAtFilter as any}
                onChange={(value) =>
                  setHistoryCreatedAtFilter(
                    value
                      ? [
                          value[0]
                            ? new Date(
                                (
                                  value[0] as { valueOf: () => number }
                                ).valueOf(),
                              )
                            : null,
                          value[1]
                            ? new Date(
                                (
                                  value[1] as { valueOf: () => number }
                                ).valueOf(),
                              )
                            : null,
                        ]
                      : [null, null],
                  )
                }
                format="YYYY-MM-DD"
              />
            </Col>
            <Col xs={24} sm={12} md={5} lg={4}>
              <Select
                style={{ width: '100%' }}
                value={historySortOrder}
                onChange={(value) =>
                  setHistorySortOrder(
                    value === 'createdAt_asc'
                      ? 'createdAt_asc'
                      : 'createdAt_desc',
                  )
                }
                options={[
                  { label: '최신순', value: 'createdAt_desc' },
                  { label: '오래된순', value: 'createdAt_asc' },
                ]}
              />
            </Col>
          </Row>
          <ValidationHistorySection
            runs={filteredHistoryRuns}
            historyCurrentPage={historyCurrentPage}
            historyPageSize={historyPageSize}
            setHistoryCurrentPage={setHistoryCurrentPage}
            setHistoryPageSize={setHistoryPageSize}
            onOpenHistoryRunDetail={onOpenHistoryRunDetail}
            historyColumns={historyColumns}
          />
        </Space>
      ) : null}

      {section === 'history-detail' ? (
        <ValidationHistoryDetailSection
          historyRunId={historyRunId}
          historyDetailTab={historyDetailTab}
          currentRun={currentRun}
          isHistoryDetailMatched={isHistoryDetailMatched}
          runItems={runItems}
          runItemsCurrentPage={runItemsCurrentPage}
          runItemsPageSize={runItemsPageSize}
          setRunItemsCurrentPage={setRunItemsCurrentPage}
          setRunItemsPageSize={setRunItemsPageSize}
          onOpenInRunWorkspace={onOpenRunWorkspace}
          onChangeHistoryDetailTab={handleChangeHistoryDetailTab}
          onDeleteRun={handleDeleteRun}
          testSetNameById={testSetNameById}
          onUpdateRun={handleUpdateRun}
          onUpdateRunItemSnapshot={handleUpdateRunItemSnapshot}
          onPreviewExpectedResultsBulkUpdate={
            handlePreviewExpectedResultsBulkUpdate
          }
          onApplyExpectedResultsBulkUpdate={
            handleApplyExpectedResultsBulkUpdate
          }
        />
      ) : null}

      {section === 'dashboard' ? (
        <ValidationDashboardSection
          testSets={testSets}
          dashboardTestSetId={dashboardTestSetId}
          setDashboardTestSetId={setDashboardTestSetId}
          handleLoadDashboard={() => {
            void handleLoadDashboard();
          }}
          dashboardData={dashboardData}
        />
      ) : null}
    </Card>
  );
}
