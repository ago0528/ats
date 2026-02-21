import { useEffect, useMemo, useState } from 'react';
import { App, Card } from 'antd';
import { useLocation } from 'react-router-dom';

import {
  compareValidationRun,
  createRunFromValidationTestSet,
  evaluateValidationRun,
  executeValidationRun,
  getValidationTestSetDashboard,
  getValidationRun,
  listValidationRunItems,
  listValidationRuns,
  listValidationTestSets,
} from '../../api/validation';
import type {
  ValidationRun,
  ValidationRunItem,
  ValidationTestSet,
} from '../../api/types/validation';
import type { Environment } from '../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../app/types';
import { ValidationDashboardSection } from './components/ValidationDashboardSection';
import { ValidationHistoryDetailSection } from './components/ValidationHistoryDetailSection';
import { ValidationHistorySection } from './components/ValidationHistorySection';
import { ValidationRunSection, type RunCreateOverrides } from './components/ValidationRunSection';
import { useValidationColumns } from './hooks/useValidationColumns';
import { useValidationSectionMeta } from './hooks/useValidationSectionMeta';
import type { ValidationSection } from './types';

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
  onOpenRunWorkspace?: (payload: { runId: string; testSetId?: string | null }) => void;
}) {
  const { message } = App.useApp();
  const location = useLocation();
  const [testSets, setTestSets] = useState<ValidationTestSet[]>([]);
  const [runs, setRuns] = useState<ValidationRun[]>([]);
  const [runItems, setRunItems] = useState<ValidationRunItem[]>([]);
  const [currentRun, setCurrentRun] = useState<ValidationRun | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string>('');
  const [selectedTestSetId, setSelectedTestSetId] = useState<string>('');
  const [baseRunId, setBaseRunId] = useState<string>('');
  const [runItemsCurrentPage, setRunItemsCurrentPage] = useState(1);
  const [runItemsPageSize, setRunItemsPageSize] = useState<number>(50);
  const [historyCurrentPage, setHistoryCurrentPage] = useState(1);
  const [historyPageSize, setHistoryPageSize] = useState<number>(50);
  const [loading, setLoading] = useState(false);
  const [compareResult, setCompareResult] = useState<Record<string, unknown> | null>(null);
  const [dashboardTestSetId, setDashboardTestSetId] = useState<string>('');
  const [dashboardData, setDashboardData] = useState<Record<string, unknown> | null>(null);

  const runQueryParams = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return {
      runId: params.get('runId') || '',
      testSetId: params.get('testSetId') || '',
    };
  }, [location.search]);

  const loadGroupsAndTestSets = async () => {
    try {
      const testSetData = await listValidationTestSets({ limit: 500, environment });
      setTestSets(testSetData.items);
      setDashboardTestSetId((prev) => prev || testSetData.items[0]?.id || '');
      setSelectedTestSetId((prev) => {
        if (runQueryParams.testSetId) return runQueryParams.testSetId;
        if (prev && testSetData.items.some((item) => item.id === prev)) return prev;
        return testSetData.items[0]?.id || '';
      });
    } catch (error) {
      console.error(error);
      message.error('검증 메타 데이터 조회에 실패했습니다.');
    }
  };

  const loadRuns = async (options?: { testSetId?: string; forceAll?: boolean }) => {
    try {
      const runData = await listValidationRuns({
        environment,
        testSetId: options?.forceAll ? undefined : (options?.testSetId ?? selectedTestSetId) || undefined,
        limit: 300,
      });
      setRuns(runData.items);
      return runData.items;
    } catch (error) {
      console.error(error);
      message.error('검증 이력 조회에 실패했습니다.');
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
      void loadRuns({ forceAll: true });
      return;
    }
    if (section === 'history-detail' && historyRunId) {
      void loadRunDetail(historyRunId);
      return;
    }
    if (section !== 'run') return;
    if (!selectedTestSetId) {
      setRuns([]);
      setCurrentRun(null);
      setSelectedRunId('');
      setRunItems([]);
      return;
    }
    void (async () => {
      const loadedRuns = await loadRuns({ testSetId: selectedTestSetId });
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
  }, [section, selectedTestSetId, environment, historyRunId, runQueryParams.runId]);

  useEffect(() => {
    if (section !== 'run') return;
    if (!selectedRunId) {
      setCompareResult(null);
      return;
    }
    if (!runs.some((run) => run.id === selectedRunId)) {
      setCompareResult(null);
      return;
    }
    setCompareResult(null);
    void loadRunDetail(selectedRunId);
  }, [selectedRunId]);

  useEffect(() => {
    if (section !== 'run') return;
    if (!baseRunId) return;
    if (baseRunId === selectedRunId || !runs.some((run) => run.id === baseRunId)) {
      setBaseRunId('');
    }
  }, [baseRunId, runs, selectedRunId, section]);

  useEffect(() => {
    if (currentRun?.status !== 'RUNNING') return;
    const timer = window.setInterval(() => {
      void loadRunDetail(currentRun.id);
      void loadRuns({ testSetId: selectedTestSetId });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [currentRun?.id, currentRun?.status, selectedTestSetId]);

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

  const handleCreateRunFromTestSet = async (testSetId: string, overrides: RunCreateOverrides) => {
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
      setBaseRunId('');
      setCompareResult(null);
      await loadRuns({ testSetId });
      await loadRunDetail(created.id);
      message.success('Run을 생성했습니다.');
    } catch (error) {
      console.error(error);
      message.error('Run 생성에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async () => {
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
      await loadRuns({ testSetId: selectedTestSetId });
    } catch (error) {
      console.error(error);
      message.error('실행 요청에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleEvaluate = async () => {
    if (!currentRun) return;
    const readErrorMessage = (error: unknown) => {
      if (typeof error === 'object' && error !== null) {
        const typed = error as {
          response?: { data?: { detail?: string; message?: string } | string };
          message?: string;
        };
        if (typed.response?.data) {
          const detail = typed.response.data;
          if (typeof detail === 'string' && detail) {
            return detail;
          }
          if (detail && typeof detail === 'object' && (detail.detail || detail.message)) {
            return String(detail.detail || detail.message);
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
      await evaluateValidationRun(currentRun.id, { maxChars: 15000 });
      message.success('평가를 시작했습니다.');
      await loadRunDetail(currentRun.id);
      await loadRuns({ testSetId: selectedTestSetId });
    } catch (error) {
      console.error(error);
      const detail = readErrorMessage(error);
      message.error(
        detail ? `평가 요청에 실패했습니다. (${detail})` : '평가 요청에 실패했습니다.',
      );
    } finally {
      setLoading(false);
    }
  };

  const handleCompare = async () => {
    if (!currentRun || !baseRunId) {
      message.warning('비교 기준 run을 선택해 주세요.');
      return;
    }
    try {
      setLoading(true);
      const result = await compareValidationRun(currentRun.id, baseRunId);
      setCompareResult(result as Record<string, unknown>);
    } catch (error) {
      console.error(error);
      message.error('결과 비교에 실패했습니다.');
    } finally {
      setLoading(false);
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

  const { runItemColumns, historyDetailItemColumns, historyColumns } = useValidationColumns();

  const { sectionTitle, isHistoryDetailMatched } = useValidationSectionMeta({
    section,
    historyRunId,
    currentRun,
  });

  return (
    <Card className="backoffice-content-card" title={`에이전트 검증 관리 · ${sectionTitle}`}>
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
          baseRunId={baseRunId}
          setBaseRunId={setBaseRunId}
          handleCreateRun={handleCreateRunFromTestSet}
          handleExecute={handleExecute}
          handleEvaluate={handleEvaluate}
          handleCompare={handleCompare}
          compareResult={compareResult}
          runItemsCurrentPage={runItemsCurrentPage}
          runItemsPageSize={runItemsPageSize}
          setRunItemsCurrentPage={setRunItemsCurrentPage}
          setRunItemsPageSize={setRunItemsPageSize}
          runItemColumns={runItemColumns}
        />
      ) : null}

      {section === 'history' ? (
        <ValidationHistorySection
          runs={runs}
          historyCurrentPage={historyCurrentPage}
          historyPageSize={historyPageSize}
          setHistoryCurrentPage={setHistoryCurrentPage}
          setHistoryPageSize={setHistoryPageSize}
          onOpenHistoryRunDetail={onOpenHistoryRunDetail}
          historyColumns={historyColumns}
        />
      ) : null}

      {section === 'history-detail' ? (
        <ValidationHistoryDetailSection
          historyRunId={historyRunId}
          currentRun={currentRun}
          isHistoryDetailMatched={isHistoryDetailMatched}
          runItems={runItems}
          runItemsCurrentPage={runItemsCurrentPage}
          runItemsPageSize={runItemsPageSize}
          setRunItemsCurrentPage={setRunItemsCurrentPage}
          setRunItemsPageSize={setRunItemsPageSize}
          onBackToHistory={onBackToHistory}
          onOpenInRunWorkspace={onOpenRunWorkspace}
          historyDetailItemColumns={historyDetailItemColumns}
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
