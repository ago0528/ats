import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MessageInstance } from 'antd/es/message/interface';

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
  updateValidationRun,
  updateValidationRunExpectedResultsBulk,
  updateValidationRunItemSnapshot,
} from '../../../api/validation';
import type {
  ValidationRun,
  ValidationRunExpectedBulkPreviewResult,
  ValidationRunExpectedBulkUpdateResult,
  ValidationRunItem,
  ValidationRunUpdateRequest,
  ValidationTestSet,
} from '../../../api/types/validation';
import type { Environment } from '../../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../../app/types';
import type { RunCreateOverrides } from '../components/ValidationRunSection';
import type { ValidationSection } from '../types';

export function useValidationManagementData({
  environment,
  tokens,
  section,
  historyRunId,
  runIdFromUrl,
  testSetIdFromUrl,
  onBackToHistory,
  message,
}: {
  environment: Environment;
  tokens: RuntimeSecrets;
  section: ValidationSection;
  historyRunId?: string;
  runIdFromUrl?: string;
  testSetIdFromUrl?: string;
  onBackToHistory?: () => void;
  message: MessageInstance;
}) {
  const [testSets, setTestSets] = useState<ValidationTestSet[]>([]);
  const [runs, setRuns] = useState<ValidationRun[]>([]);
  const [runItems, setRunItems] = useState<ValidationRunItem[]>([]);
  const [currentRun, setCurrentRun] = useState<ValidationRun | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string>('');
  const [selectedTestSetId, setSelectedTestSetId] = useState<string>('');
  const [runItemsCurrentPage, setRunItemsCurrentPage] = useState(1);
  const [runItemsPageSize, setRunItemsPageSize] = useState<number>(50);
  const [loading, setLoading] = useState(false);
  const [forceRunRefreshUntil, setForceRunRefreshUntil] = useState(0);
  const [dashboardTestSetId, setDashboardTestSetId] = useState<string>('');
  const [dashboardData, setDashboardData] = useState<Record<string, unknown> | null>(null);
  const selectedRunIdRef = useRef('');

  useEffect(() => {
    selectedRunIdRef.current = selectedRunId;
  }, [selectedRunId]);

  const loadTestSets = useCallback(async () => {
    try {
      const testSetData = await listValidationTestSets({
        limit: 500,
        environment,
      });
      setTestSets(testSetData.items);
      setDashboardTestSetId((prev) => prev || testSetData.items[0]?.id || '');
      setSelectedTestSetId((prev) => {
        if (testSetIdFromUrl) return testSetIdFromUrl;
        if (prev && testSetData.items.some((item) => item.id === prev)) {
          return prev;
        }
        return testSetData.items[0]?.id || '';
      });
    } catch (error) {
      console.error(error);
      message.error('검증 메타 데이터 조회에 실패했습니다.');
    }
  }, [environment, message, testSetIdFromUrl]);

  const loadRuns = useCallback(async (options?: {
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
  }, [environment, message, selectedTestSetId]);

  const loadRunDetail = useCallback(async (runId: string) => {
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
  }, [message, section]);

  useEffect(() => {
    void loadTestSets();
  }, [loadTestSets]);

  useEffect(() => {
    if (section === 'history') {
      void loadRuns({ forceAll: true });
      return;
    }

    if (section === 'history-detail' && historyRunId) {
      void loadRunDetail(historyRunId);
      return;
    }

    if (section !== 'run') return;

    void (async () => {
      const loadedRuns = await loadRuns({ forceAll: true });
      if (runIdFromUrl) {
        await loadRunDetail(runIdFromUrl);
        return;
      }
      const nextSelectedId =
        selectedRunIdRef.current
        && loadedRuns.some((run) => run.id === selectedRunIdRef.current)
          ? selectedRunIdRef.current
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
    historyRunId,
    runIdFromUrl,
    loadRuns,
    loadRunDetail,
  ]);

  useEffect(() => {
    if (section !== 'run') return;
    if (!selectedRunId) return;
    if (!runs.some((run) => run.id === selectedRunId)) return;
    void loadRunDetail(selectedRunId);
  }, [section, selectedRunId, runs, loadRunDetail]);

  useEffect(() => {
    if (section !== 'run') return;
    if (!currentRun) return;

    const isExecutionRunning = currentRun.status === 'RUNNING';
    const isEvaluationRunning =
      String(currentRun.evalStatus || '').toUpperCase() === 'RUNNING';
    const isInForcedRefreshWindow = forceRunRefreshUntil > Date.now();
    if (!isExecutionRunning && !isEvaluationRunning && !isInForcedRefreshWindow) {
      return;
    }

    const refreshIntervalMs =
      isExecutionRunning || isEvaluationRunning ? 2000 : 2500;
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
    currentRun,
    forceRunRefreshUntil,
    loadRunDetail,
    loadRuns,
  ]);

  useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(runItems.length / runItemsPageSize));
    if (runItemsCurrentPage > maxPage) {
      setRunItemsCurrentPage(maxPage);
    }
  }, [runItems.length, runItemsPageSize, runItemsCurrentPage]);

  const triggerForceRunRefresh = () => {
    setForceRunRefreshUntil(Date.now() + 30_000);
  };

  const handleCreateRunFromTestSet = useCallback(async (
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
  }, [environment, loadRunDetail, loadRuns, message]);

  const handleExecute = useCallback(async (itemIds?: string[]) => {
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
        scopedItemIds.length
          ? '선택한 질의를 재실행했습니다.'
          : '실행을 시작했습니다.',
      );
      await loadRunDetail(runId);
      await loadRuns({ forceAll: true });
    } catch (error) {
      console.error(error);
      const detail = readErrorMessage(error);
      if (scopedItemIds.length && detail === 'Only PENDING runs can be executed') {
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
  }, [
    currentRun,
    loadRunDetail,
    loadRuns,
    message,
    tokens.bearer,
    tokens.cms,
    tokens.mrs,
  ]);

  const handleEvaluate = useCallback(async (itemIds?: string[]) => {
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
        itemIds?.length
          ? '선택한 질의 재평가를 시작했습니다.'
          : '평가를 시작했습니다.',
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
  }, [currentRun, loadRunDetail, loadRuns, message]);

  const handleUpdateRun = useCallback(async (
    runId: string,
    payload: ValidationRunUpdateRequest,
  ) => {
    try {
      setLoading(true);
      await updateValidationRun(runId, payload);
      message.success('Run 정보를 수정했습니다.');
      await loadRuns({ forceAll: true });
      await loadRunDetail(runId);
    } catch (error) {
      console.error(error);
      message.error('Run 정보 수정에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [loadRunDetail, loadRuns, message]);

  const handleDeleteRun = useCallback(async (runId: string) => {
    try {
      setLoading(true);
      await deleteValidationRun(runId);
      message.success('Run을 삭제했습니다.');

      if (section === 'run') {
        const refreshedRuns = await loadRuns({ forceAll: true });
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
  }, [
    loadRunDetail,
    loadRuns,
    message,
    onBackToHistory,
    section,
    selectedRunId,
  ]);

  const handlePreviewExpectedResultsBulkUpdate = useCallback(async (
    runId: string,
    file: File,
  ): Promise<ValidationRunExpectedBulkPreviewResult> => {
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
  }, [message]);

  const handleApplyExpectedResultsBulkUpdate = useCallback(async (
    runId: string,
    file: File,
  ): Promise<ValidationRunExpectedBulkUpdateResult> => {
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
      await loadRuns({ forceAll: true });
      return result;
    } catch (error) {
      console.error(error);
      message.error('기대결과 일괄 업데이트에 실패했습니다.');
      throw error;
    } finally {
      setLoading(false);
    }
  }, [loadRunDetail, loadRuns, message]);

  const handleUpdateRunItemSnapshot = useCallback(async (
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
  }, [currentRun?.id]);

  const handleLoadDashboard = useCallback(async () => {
    if (!dashboardTestSetId) return;
    try {
      const data = await getValidationTestSetDashboard(dashboardTestSetId);
      setDashboardData(data as Record<string, unknown>);
    } catch (error) {
      console.error(error);
      message.error('대시보드 조회에 실패했습니다.');
    }
  }, [dashboardTestSetId, message]);

  const isRunBusy = useMemo(() => {
    if (!currentRun) return false;
    return currentRun.status === 'RUNNING'
      || String(currentRun.evalStatus || '').toUpperCase() === 'RUNNING';
  }, [currentRun]);

  return {
    testSets,
    runs,
    runItems,
    currentRun,
    selectedRunId,
    selectedTestSetId,
    runItemsCurrentPage,
    runItemsPageSize,
    loading,
    dashboardTestSetId,
    dashboardData,
    isRunBusy,
    setSelectedRunId,
    setSelectedTestSetId,
    setRunItemsCurrentPage,
    setRunItemsPageSize,
    setDashboardTestSetId,
    handleCreateRunFromTestSet,
    handleExecute,
    handleEvaluate,
    handleUpdateRun,
    handleDeleteRun,
    handlePreviewExpectedResultsBulkUpdate,
    handleApplyExpectedResultsBulkUpdate,
    handleUpdateRunItemSnapshot,
    handleLoadDashboard,
  };
}
