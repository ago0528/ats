import { useMemo } from 'react';
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

import type { Environment } from '../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../app/types';
import { resolveHistoryDetailTab } from '../../app/navigation/validationNavigation';
import { ValidationDashboardSection } from './components/ValidationDashboardSection';
import { ValidationHistoryDetailSection } from './components/ValidationHistoryDetailSection';
import { ValidationHistorySection } from './components/ValidationHistorySection';
import {
  ValidationRunSection,
} from './components/ValidationRunSection';
import { useValidationColumns } from './hooks/useValidationColumns';
import { useValidationSectionMeta } from './hooks/useValidationSectionMeta';
import { useValidationHistoryState } from './hooks/useValidationHistoryState';
import { useValidationManagementData } from './hooks/useValidationManagementData';
import type { HistoryDetailTab, ValidationSection } from './types';
import type { ValidationRunItem } from '../../api/types/validation';
import {
  buildRunItemIdsByQueryId,
  hasExecutionResult,
  needsRunItemActionConfirm,
  resolveScopedRunItemIds,
} from './utils/runItemScope';

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

  const {
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
  } = useValidationManagementData({
    environment,
    tokens,
    section,
    historyRunId,
    runIdFromUrl: runQueryParams.runId,
    testSetIdFromUrl: runQueryParams.testSetId,
    onBackToHistory,
    message,
  });

  const {
    historyCurrentPage,
    historyPageSize,
    setHistoryCurrentPage,
    setHistoryPageSize,
    historyExecutionStatusFilter,
    setHistoryExecutionStatusFilter,
    historyEvaluationStatusFilter,
    setHistoryEvaluationStatusFilter,
    historyTestSetFilter,
    setHistoryTestSetFilter,
    historyKeywordFilter,
    setHistoryKeywordFilter,
    historyCreatedAtFilter,
    setHistoryCreatedAtFilter,
    historySortOrder,
    setHistorySortOrder,
    historyTestSetFilterOptions,
    filteredHistoryRuns,
    resetHistoryFilters,
    testSetNameById,
  } = useValidationHistoryState({
    section,
    runs,
    testSets,
  });

  const runItemIdsByQueryId = useMemo(
    () => buildRunItemIdsByQueryId(runItems),
    [runItems],
  );

  const canReexecuteRunItem = (item: ValidationRunItem) => {
    if (!currentRun || isRunBusy) return false;
    const scopedItemIds = resolveScopedRunItemIds(item, runItemIdsByQueryId);
    return scopedItemIds.length > 0;
  };

  const canReevaluateRunItem = (item: ValidationRunItem) => {
    if (!currentRun || isRunBusy) return false;
    const scopedItemIds = new Set(
      resolveScopedRunItemIds(item, runItemIdsByQueryId),
    );
    return runItems.some(
      (row) => scopedItemIds.has(row.id) && hasExecutionResult(row),
    );
  };

  const handleReexecuteRunItem = (item: ValidationRunItem) => {
    const scopedItemIds = resolveScopedRunItemIds(item, runItemIdsByQueryId);
    const executeAction = async () => {
      await handleExecute(scopedItemIds);
    };

    if (!needsRunItemActionConfirm(runItems, scopedItemIds)) {
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
    const scopedItemIds = resolveScopedRunItemIds(item, runItemIdsByQueryId);
    const evaluateAction = async () => {
      await handleEvaluate(scopedItemIds);
    };

    if (!needsRunItemActionConfirm(runItems, scopedItemIds)) {
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
    navigate(
      `/validation/history/${encodeURIComponent(historyRunId)}?${params.toString()}`,
    );
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
            <Button onClick={resetHistoryFilters}>필터 초기화</Button>
            <Typography.Text type="secondary">
              전체 {runs.length}건 / 조회 {filteredHistoryRuns.length}건
            </Typography.Text>
          </Space>
          <Row gutter={[8, 8]} align="middle">
            <Col xs={24} sm={24} md={10} lg={9}>
              <Input.Search
                allowClear
                value={historyKeywordFilter}
                onChange={(event) => setHistoryKeywordFilter(event.target.value)}
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
                          ? new Date((value[0] as { valueOf: () => number }).valueOf())
                          : null,
                        value[1]
                          ? new Date((value[1] as { valueOf: () => number }).valueOf())
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
                    value === 'createdAt_asc' ? 'createdAt_asc' : 'createdAt_desc',
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
