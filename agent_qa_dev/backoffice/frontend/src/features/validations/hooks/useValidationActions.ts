import { useCallback } from 'react';
import type { MessageInstance } from 'antd/es/message/interface';

import {
  compareValidationRun,
  createValidationRun,
  evaluateValidationRun,
  executeValidationRun,
  getValidationGroupDashboard,
  rerunValidationRun,
} from '../../../api/validation';
import type { ValidationRun, ValidationRunCreateRequest } from '../../../api/types/validation';
import type { Environment } from '../../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../../app/types';
import type { RunMode } from '../types';

type RunCreateOverrides = Partial<Pick<
  ValidationRunCreateRequest,
  'agentId' | 'testModel' | 'evalModel' | 'repeatInConversation' | 'conversationRoomCount' | 'agentParallelCalls' | 'timeoutMs'
>>;

export function useValidationActions({
  message,
  environment,
  tokens,
  runMode,
  selectedQueryIds,
  adHocQueryText,
  adHocExpected,
  adHocCriteria,
  adHocLogicFieldPath,
  adHocLogicExpected,
  createRunOverrides,
  setCreateRunOverrides,
  currentRun,
  setCurrentRun,
  setSelectedRunId,
  setLoading,
  setCompareResult,
  dashboardGroupId,
  setDashboardData,
  loadRuns,
  loadRunDetail,
}: {
  message: MessageInstance;
  environment: Environment;
  tokens: RuntimeSecrets;
  runMode: RunMode;
  selectedQueryIds: string[];
  adHocQueryText: string;
  adHocExpected: string;
  adHocCriteria: string;
  adHocLogicFieldPath: string;
  adHocLogicExpected: string;
  createRunOverrides: RunCreateOverrides;
  setCreateRunOverrides: (next: RunCreateOverrides) => void;
  currentRun: ValidationRun | null;
  setCurrentRun: (run: ValidationRun | null) => void;
  setSelectedRunId: (runId: string) => void;
  setLoading: (value: boolean) => void;
  setCompareResult: (value: Record<string, unknown> | null) => void;
  dashboardGroupId: string;
  setDashboardData: (value: Record<string, unknown> | null) => void;
  loadRuns: () => Promise<void>;
  loadRunDetail: (runId: string) => Promise<void>;
}) {
  const handleCreateRun = useCallback(async () => {
    if (runMode === 'REGISTERED' && selectedQueryIds.length === 0) {
      message.warning('불러올 질의를 먼저 선택해 주세요.');
      return;
    }
    if (runMode === 'AD_HOC' && !adHocQueryText.trim()) {
      message.warning('직접 입력 질의를 입력해 주세요.');
      return;
    }

    try {
      setLoading(true);
      const overridePayload: RunCreateOverrides = { ...createRunOverrides };
      const payload =
        runMode === 'REGISTERED'
          ? {
            environment,
            queryIds: selectedQueryIds,
            ...overridePayload,
          }
          : {
            environment,
            adHocQuery: {
              queryText: adHocQueryText,
              expectedResult: adHocExpected,
              category: 'Happy path',
              llmEvalCriteria: adHocCriteria,
              logicFieldPath: adHocLogicFieldPath,
              logicExpectedValue: adHocLogicExpected,
            },
            ...overridePayload,
          };

      const created = await createValidationRun(payload);
      setCurrentRun(created);
      setSelectedRunId(created.id);
      await loadRuns();
      await loadRunDetail(created.id);
      setCreateRunOverrides({});
      message.success('검증 런을 생성했습니다.');
    } catch (error) {
      console.error(error);
      message.error('검증 런 생성에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [
    runMode,
    selectedQueryIds,
    adHocQueryText,
    adHocExpected,
    adHocCriteria,
    adHocLogicFieldPath,
    adHocLogicExpected,
    message,
    setLoading,
    createRunOverrides,
    environment,
    setCurrentRun,
    setSelectedRunId,
    loadRuns,
    loadRunDetail,
    setCreateRunOverrides,
  ]);

  const handleExecute = useCallback(async () => {
    if (!currentRun) return;
    try {
      setLoading(true);
      await executeValidationRun(currentRun.id, {
        bearer: tokens.bearer,
        cms: tokens.cms,
        mrs: tokens.mrs,
      });
      message.success('실행을 시작했습니다.');
      await loadRunDetail(currentRun.id);
      await loadRuns();
    } catch (error) {
      console.error(error);
      message.error('실행 요청에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [currentRun, loadRunDetail, loadRuns, message, setLoading, tokens.bearer, tokens.cms, tokens.mrs]);

  const handleEvaluate = useCallback(async () => {
    if (!currentRun) return;
    try {
      setLoading(true);
      await evaluateValidationRun(currentRun.id, {
        maxChars: 15000,
      });
      message.success('평가를 시작했습니다.');
      await loadRunDetail(currentRun.id);
      await loadRuns();
    } catch (error) {
      console.error(error);
      const detail = (error as any)?.response?.data?.detail;
      if (detail && typeof detail === 'object' && detail.code === 'expected_result_missing') {
        const missingCount = Number(detail.missingCount || 0);
        const sampleQueryIds = Array.isArray(detail.sampleQueryIds) ? detail.sampleQueryIds.filter(Boolean) : [];
        const sampleText = sampleQueryIds.length > 0 ? ` 예시: ${sampleQueryIds.slice(0, 3).join(', ')}` : '';
        message.error(`평가를 시작할 수 없어요. 기대 결과 미입력 ${missingCount}건.${sampleText}`);
      } else {
        message.error('평가 요청에 실패했습니다.');
      }
    } finally {
      setLoading(false);
    }
  }, [currentRun, loadRunDetail, loadRuns, message, setLoading]);

  const handleRerun = useCallback(async () => {
    if (!currentRun) return;
    try {
      setLoading(true);
      const rerun = await rerunValidationRun(currentRun.id);
      setCurrentRun(rerun);
      setSelectedRunId(rerun.id);
      await loadRuns();
      await loadRunDetail(rerun.id);
      message.success('재실행 런을 생성했습니다.');
    } catch (error) {
      console.error(error);
      message.error('재실행 생성에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [currentRun, loadRunDetail, loadRuns, message, setCurrentRun, setLoading, setSelectedRunId]);

  const handleCompare = useCallback(async () => {
    if (!currentRun) return;
    try {
      const result = await compareValidationRun(currentRun.id);
      setCompareResult(result as Record<string, unknown>);
    } catch (error) {
      console.error(error);
      message.error('이력 비교에 실패했습니다.');
    }
  }, [currentRun, message, setCompareResult]);

  const handleLoadDashboard = useCallback(async () => {
    if (!dashboardGroupId) return;
    try {
      const data = await getValidationGroupDashboard(dashboardGroupId);
      setDashboardData(data as Record<string, unknown>);
    } catch (error) {
      console.error(error);
      message.error('대시보드 조회에 실패했습니다.');
    }
  }, [dashboardGroupId, message, setDashboardData]);

  return {
    handleCreateRun,
    handleExecute,
    handleEvaluate,
    handleRerun,
    handleCompare,
    handleLoadDashboard,
  };
}

export type { RunCreateOverrides };
