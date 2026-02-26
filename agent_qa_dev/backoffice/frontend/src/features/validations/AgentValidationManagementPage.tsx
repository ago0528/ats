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
  compareValidationRun,
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
  const { message } = App.useApp();
  const location = useLocation();
  const navigate = useNavigate();
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
  const [compareResult, setCompareResult] = useState<Record<
    string,
    unknown
  > | null>(null);
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
      const runData = await listValidationRuns({
        environment,
        testSetId: options?.forceAll
          ? undefined
          : (options?.testSetId ?? selectedTestSetId) || undefined,
        status: options?.status || undefined,
        evaluationStatus: options?.evaluationStatus || undefined,
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
  }, [
    section,
    selectedTestSetId,
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
    if (
      baseRunId === selectedRunId ||
      !runs.some((run) => run.id === baseRunId)
    ) {
      setBaseRunId('');
    }
  }, [baseRunId, runs, selectedRunId, section]);

  useEffect(() => {
    if (section !== 'run') return;
    if (!currentRun) return;
    const isExecutionRunning = currentRun.status === 'RUNNING';
    const isEvaluationRunning =
      String(currentRun.evalStatus || '').toUpperCase() === 'RUNNING';
    if (!isExecutionRunning && !isEvaluationRunning) return;
    const timer = window.setInterval(() => {
      void loadRunDetail(currentRun.id);
      void loadRuns({ testSetId: selectedTestSetId });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [
    section,
    currentRun?.id,
    currentRun?.status,
    currentRun?.evalStatus,
    selectedTestSetId,
  ]);

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
      await evaluateValidationRun(currentRun.id, { maxChars: 15000 });
      message.success('평가를 시작했습니다.');
      await loadRunDetail(currentRun.id);
      await loadRuns({ testSetId: selectedTestSetId });
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
        await loadRuns({ testSetId: selectedTestSetId });
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
          testSetId: selectedTestSetId || undefined,
        });
        setCompareResult((prev) => (selectedRunId === runId ? null : prev));
        if (selectedRunId === runId) {
          setBaseRunId('');
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
        await loadRuns({ testSetId: selectedTestSetId });
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

  const { runItemColumns, historyColumns } =
    useValidationColumns({
      testSetNameById,
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
          baseRunId={baseRunId}
          setBaseRunId={setBaseRunId}
          handleCreateRun={handleCreateRunFromTestSet}
          handleExecute={handleExecute}
          handleEvaluate={handleEvaluate}
          handleCompare={handleCompare}
          handleUpdateRun={handleUpdateRun}
          handleDeleteRun={handleDeleteRun}
          compareResult={compareResult}
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
