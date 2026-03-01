import { useEffect, useMemo, useState } from 'react';
import {
  App,
  Button,
  Dropdown,
  Descriptions,
  Empty,
  Form,
  Input,
  InputNumber,
  Select,
  Collapse,
  Space,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { MenuProps } from 'antd';
import {
  CheckCircleOutlined,
  EllipsisOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
} from '@ant-design/icons';

import type {
  ValidationRun,
  ValidationRunItem,
  ValidationTestSet,
  ValidationRunUpdateRequest,
} from '../../../api/types/validation';
import { StandardDataTable } from '../../../components/common/StandardDataTable';
import { StandardModal } from '../../../components/common/StandardModal';
import {
  AGENT_MODE_OPTIONS,
  DEFAULT_AGENT_MODE_VALUE,
  DEFAULT_EVAL_MODEL_VALUE,
  EVAL_MODEL_OPTIONS,
  RUN_ITEM_INITIAL_COLUMN_WIDTHS,
} from '../constants';
import {
  CONTEXT_SAMPLE,
  normalizeAgentModeValue,
  parseContextJson,
  stringifyContext,
} from '../../../shared/utils/validationConfig';
import {
  getEvaluationProgressText,
  getEvaluationStateLabel,
  getExecutionStateLabel,
} from '../utils/runProgress';
import {
  canEvaluateRun,
  canCancelEvaluationRun,
  canExecuteRun,
  canDeleteRun,
  canUpdateRun,
} from '../utils/runWorkbench';
import {
  getRunDisplayName,
  getRunExecutionConfigText,
} from '../utils/runDisplay';
import {
  getAgentModeLabel,
  getRunStatusColor,
  getRunStatusLabel,
} from '../utils/historyDetailDisplay';
import {
  buildHistoryRows,
  type HistoryRowView,
} from '../utils/historyDetailRows';
import { ValidationHistoryDetailRowDrawer } from './ValidationHistoryDetailRowDrawer';
import { LLMScoringCriteriaModal } from './LLMScoringCriteriaModal';

export type RunCreateOverrides = {
  name?: string;
  context?: Record<string, unknown>;
  agentId?: string;
  evalModel?: string;
  repeatInConversation?: number;
  conversationRoomCount?: number;
  agentParallelCalls?: number;
  timeoutMs?: number;
};

type OverrideFormValues = RunCreateOverrides & {
  testSetId?: string;
  contextJson?: string;
};

const getRunSelectLabel = (run: ValidationRun) => {
  const displayName = getRunDisplayName(run);
  const executionState = getExecutionStateLabel(run);
  const evaluationState = getEvaluationStateLabel(run);
  return `${displayName} (${executionState} / ${evaluationState})`;
};

export function ValidationRunSection({
  loading,
  testSets,
  selectedTestSetId,
  setSelectedTestSetId,
  runs,
  selectedRunId,
  setSelectedRunId,
  currentRun,
  runItems,
  handleCreateRun,
  handleExecute,
  handleEvaluate,
  handleCancelEvaluate,
  handleUpdateRun,
  handleDeleteRun,
  runItemsCurrentPage,
  runItemsPageSize,
  setRunItemsCurrentPage,
  setRunItemsPageSize,
  runItemColumns,
}: {
  loading: boolean;
  testSets: ValidationTestSet[];
  selectedTestSetId: string;
  setSelectedTestSetId: (value: string) => void;
  runs: ValidationRun[];
  selectedRunId: string;
  setSelectedRunId: (value: string) => void;
  currentRun: ValidationRun | null;
  runItems: ValidationRunItem[];
  handleCreateRun: (
    testSetId: string,
    overrides: RunCreateOverrides,
  ) => Promise<void>;
  handleUpdateRun: (
    runId: string,
    payload: ValidationRunUpdateRequest,
  ) => Promise<void>;
  handleExecute: (itemIds?: string[]) => Promise<void>;
  handleEvaluate: (itemIds?: string[]) => Promise<void>;
  handleCancelEvaluate: () => Promise<void>;
  handleDeleteRun: (runId: string) => Promise<void>;
  runItemsCurrentPage: number;
  runItemsPageSize: number;
  setRunItemsCurrentPage: (value: number) => void;
  setRunItemsPageSize: (value: number) => void;
  runItemColumns: ColumnsType<ValidationRunItem>;
}) {
  const [overrideModalOpen, setOverrideModalOpen] = useState(false);
  const [overrideSaving, setOverrideSaving] = useState(false);
  const [overrideModalMode, setOverrideModalMode] = useState<'create' | 'edit'>(
    'create',
  );
  const [overrideRunId, setOverrideRunId] = useState('');
  const [overrideContextSnapshot, setOverrideContextSnapshot] = useState('');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedHistoryRowId, setSelectedHistoryRowId] = useState('');
  const [criteriaModalOpen, setCriteriaModalOpen] = useState(false);
  const [form] = Form.useForm<OverrideFormValues>();

  const executionStateLabel = useMemo(
    () => getExecutionStateLabel(currentRun),
    [currentRun],
  );
  const evaluationStateLabel = useMemo(
    () => getEvaluationStateLabel(currentRun, runItems),
    [currentRun, runItems],
  );
  const evaluationProgressText = useMemo(
    () => getEvaluationProgressText(runItems),
    [runItems],
  );
  const { modal } = App.useApp();

  const runCreateEnabled = testSets.length > 0;
  const runExecuteEnabled = canExecuteRun(currentRun);
  const runEvaluateEnabled = canEvaluateRun(currentRun);
  const runCancelEvaluateEnabled = canCancelEvaluationRun(currentRun);
  const runUpdateEnabled = canUpdateRun(currentRun);
  const runDeleteEnabled = canDeleteRun(currentRun);

  const runOptions = runs.map((run) => ({
    label: getRunSelectLabel(run),
    value: run.id,
  }));
  const historyRows = useMemo(() => buildHistoryRows(runItems), [runItems]);
  const selectedHistoryRow = useMemo(
    () =>
      historyRows.find((entry) => entry.item.id === selectedHistoryRowId) ||
      null,
    [historyRows, selectedHistoryRowId],
  );

  useEffect(() => {
    if (!drawerOpen) return;
    if (!selectedHistoryRowId) return;
    if (selectedHistoryRow) return;
    setDrawerOpen(false);
    setSelectedHistoryRowId('');
  }, [drawerOpen, selectedHistoryRowId, selectedHistoryRow]);

  const currentRunTestSet = currentRun?.testSetId
    ? testSets.find((testSet) => testSet.id === currentRun.testSetId)
    : undefined;

  const applySelectedTestSetDefaults = (testSetId?: string) => {
    const normalizedTestSetId = String(testSetId || '').trim();
    const config = testSets.find(
      (testSet) => testSet.id === normalizedTestSetId,
    )?.config;
    const toNumber = (value: unknown, fallback?: number) => {
      if (value === null || value === undefined || value === '') {
        return fallback;
      }
      const parsed = typeof value === 'number' ? value : Number(value);
      if (!Number.isFinite(parsed)) {
        return fallback;
      }
      return parsed;
    };
    form.setFieldsValue({
      agentId: normalizeAgentModeValue(
        config?.agentId,
        DEFAULT_AGENT_MODE_VALUE,
      ),
      contextJson: stringifyContext(config?.context),
      evalModel: config?.evalModel || DEFAULT_EVAL_MODEL_VALUE,
      repeatInConversation: toNumber(config?.repeatInConversation),
      conversationRoomCount: toNumber(config?.conversationRoomCount),
      agentParallelCalls: toNumber(config?.agentParallelCalls),
      timeoutMs: toNumber(config?.timeoutMs),
    });
  };

  const openCreateRunModal = () => {
    setOverrideModalMode('create');
    setOverrideRunId('');
    setOverrideContextSnapshot('');
    form.resetFields();
    const initialTestSetId = selectedTestSetId || testSets[0]?.id || '';
    form.setFieldsValue({
      testSetId: initialTestSetId,
      name: '',
    });
    applySelectedTestSetDefaults(initialTestSetId);
    setOverrideModalOpen(true);
  };

  const openEditRunModal = () => {
    if (!currentRun) return;
    setOverrideModalMode('edit');
    setOverrideRunId(currentRun.id);
    const contextText = stringifyContext(currentRun.options?.context);
    setOverrideContextSnapshot(contextText);
    setOverrideModalOpen(true);
    form.resetFields();
    form.setFieldsValue({
      name: currentRun.name || '',
      agentId: normalizeAgentModeValue(
        currentRun.agentId,
        DEFAULT_AGENT_MODE_VALUE,
      ),
      evalModel: currentRun.evalModel || DEFAULT_EVAL_MODEL_VALUE,
      repeatInConversation: currentRun.repeatInConversation,
      conversationRoomCount: currentRun.conversationRoomCount,
      agentParallelCalls: currentRun.agentParallelCalls,
      timeoutMs: currentRun.timeoutMs,
      contextJson: contextText,
      testSetId: currentRun.testSetId || selectedTestSetId || '',
    });
  };

  const submitRunModal = async () => {
    try {
      const values = await form.validateFields();
      const parsedContext = parseContextJson(values.contextJson || '');
      if (parsedContext.parseError) {
        form.setFields([
          {
            name: 'contextJson',
            errors: [parsedContext.parseError],
          },
        ]);
        return;
      }
      form.setFields([{ name: 'contextJson', errors: [] }]);
      setOverrideSaving(true);
      const { testSetId, contextJson, ...overrides } = values;
      const baseOverrides = overrides as RunCreateOverrides & {
        name?: string;
      };
      const trimmedName = baseOverrides.name?.trim();
      if (!trimmedName) {
        baseOverrides.name = undefined;
      }
      const contextText = (contextJson || '').trim();
      const updatePayload: ValidationRunUpdateRequest = {
        ...baseOverrides,
        ...(trimmedName ? { name: trimmedName } : {}),
      };

      if (overrideModalMode === 'edit') {
        if (!overrideRunId) return;
        const shouldUpdateContext = contextText !== overrideContextSnapshot;
        const updatePayloadWithContext: ValidationRunUpdateRequest =
          shouldUpdateContext
            ? {
                ...updatePayload,
                context: parsedContext.parsedContext ?? null,
              }
            : updatePayload;
        await handleUpdateRun(overrideRunId, updatePayloadWithContext);
        setOverrideModalOpen(false);
        return;
      }

      if (!testSetId) {
        return;
      }
      if (parsedContext.parsedContext !== undefined) {
        (baseOverrides as RunCreateOverrides).context =
          parsedContext.parsedContext;
      }
      await handleCreateRun(testSetId, {
        ...baseOverrides,
        ...(trimmedName ? { name: trimmedName } : {}),
      });
      setOverrideModalOpen(false);
    } finally {
      setOverrideSaving(false);
    }
  };

  const handleDeleteCurrentRun = () => {
    if (!currentRun) return;
    modal.confirm({
      title: 'Run 삭제',
      content:
        '실행 기록이 없는 PENDING 상태의 Run만 삭제할 수 있습니다. 삭제하시겠습니까?',
      okText: '삭제',
      cancelText: '취소',
      okType: 'danger',
      onOk: async () => {
        await handleDeleteRun(currentRun.id);
      },
    });
  };

  const runStatusLabel = getRunStatusLabel(currentRun?.status);
  const runStatusColor = getRunStatusColor(currentRun?.status);
  const menuItems: MenuProps['items'] = [
    {
      key: 'llm-scoring-criteria',
      label: 'LLM 평가 기준표',
      disabled: !currentRun,
    },
    {
      type: 'divider',
    },
    {
      key: 'update-run',
      label: 'Run 수정',
      disabled: !runUpdateEnabled,
    },
    {
      key: 'delete-run',
      label: 'Run 삭제',
      disabled: !runDeleteEnabled,
      danger: true,
    },
  ];

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (key === 'llm-scoring-criteria') {
      setCriteriaModalOpen(true);
      return;
    }
    if (key === 'update-run') {
      void openEditRunModal();
      return;
    }
    if (key === 'delete-run') {
      void handleDeleteCurrentRun();
    }
  };

  const openHistoryRow = (row: ValidationRunItem) => {
    setSelectedHistoryRowId(row.id);
    setDrawerOpen(true);
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <div className="validation-history-detail-header-bar">
        <div className="validation-history-detail-header-row">
          <div className="validation-history-detail-run-meta">
            <Typography.Title level={5} style={{ margin: 0 }}>
              {currentRun ? getRunDisplayName(currentRun) : 'Run 미선택'}
            </Typography.Title>
            <Tag color={runStatusColor}>{runStatusLabel}</Tag>
          </div>
          <Space wrap>
            <Button
              icon={<PlayCircleOutlined />}
              loading={loading}
              onClick={() => {
                void handleExecute();
              }}
              disabled={!runExecuteEnabled}
            >
              실행 시작
            </Button>
            <Button
              icon={<CheckCircleOutlined />}
              loading={loading}
              onClick={() => {
                void handleEvaluate();
              }}
              disabled={!runEvaluateEnabled}
            >
              평가 시작
            </Button>
            <Button
              icon={<PauseCircleOutlined />}
              loading={loading}
              onClick={() => {
                modal.confirm({
                  title: '평가 중단',
                  content: '현재 진행 중인 LLM 평가를 중단 요청하시겠습니까?',
                  okText: '중단 요청',
                  cancelText: '취소',
                  onOk: async () => {
                    await handleCancelEvaluate();
                  },
                });
              }}
              disabled={!runCancelEvaluateEnabled}
            >
              평가 중단
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                void openCreateRunModal();
              }}
              disabled={!runCreateEnabled}
            >
              Run 생성
            </Button>
            <Select
              showSearch
              style={{ minWidth: 360, width: 360 }}
              placeholder="현재 Run 선택"
              value={selectedRunId || undefined}
              options={runOptions}
              onChange={(value) => setSelectedRunId(value)}
              filterOption={(input, option) =>
                String(option?.label || '')
                  .toLowerCase()
                  .includes(input.toLowerCase())
              }
            />
            <Dropdown
              menu={{ items: menuItems, onClick: handleMenuClick }}
              trigger={['click']}
            >
              <Button icon={<EllipsisOutlined />} disabled={!currentRun} />
            </Dropdown>
          </Space>
        </div>
      </div>

      <Collapse
        size="small"
        defaultActiveKey={[]}
        ghost
        items={[
          {
            key: 'current-run',
            label: 'Run 요약 정보',
            children: currentRun ? (
              <Descriptions size="small" bordered column={3}>
                <Descriptions.Item label="Run 이름">
                  <Tooltip title={currentRun.id}>
                    <span>{getRunDisplayName(currentRun)}</span>
                  </Tooltip>
                </Descriptions.Item>
                <Descriptions.Item label="테스트 세트">
                  {currentRun.testSetId
                    ? currentRunTestSet?.name || currentRun.testSetId
                    : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="실행 상태">
                  {executionStateLabel}
                </Descriptions.Item>
                <Descriptions.Item label="평가 상태">
                  {evaluationStateLabel}
                </Descriptions.Item>
                <Descriptions.Item label="실행 구성">
                  {getRunExecutionConfigText(currentRun)}
                </Descriptions.Item>
                <Descriptions.Item label="에이전트 모드">
                  {getAgentModeLabel(currentRun.agentId)}
                </Descriptions.Item>
                <Descriptions.Item label="총/완료/오류">
                  {currentRun.totalItems} / {currentRun.doneItems} /{' '}
                  {currentRun.errorItems}
                </Descriptions.Item>
                <Descriptions.Item label="LLM 평가 진행">
                  {evaluationProgressText}
                </Descriptions.Item>
                <Descriptions.Item label="평가 모델">
                  {currentRun.evalModel}
                </Descriptions.Item>
              </Descriptions>
            ) : (
              <Empty description="현재 Run이 선택되지 않았습니다. 먼저 Run을 생성하고 선택해 주세요." />
            ),
          },
        ]}
      />

      <StandardDataTable
        tableId="validation-run-items"
        initialColumnWidths={RUN_ITEM_INITIAL_COLUMN_WIDTHS}
        minColumnWidth={84}
        wrapperStyle={{ width: '100%', maxWidth: '100%' }}
        wrapperClassName="validation-results-table-wrap"
        className="query-management-table validation-results-table"
        rowKey="id"
        size="small"
        tableLayout="fixed"
        dataSource={runItems}
        locale={{
          emptyText: <Empty description="Run 결과가 없습니다." />,
        }}
        onRow={(row) => ({
          onClick: () => openHistoryRow(row),
          style: { cursor: 'pointer' },
        })}
        pagination={{
          current: runItemsCurrentPage,
          pageSize: runItemsPageSize,
          total: runItems.length,
          onChange: (page, nextPageSize) => {
            if (nextPageSize !== runItemsPageSize) {
              setRunItemsPageSize(nextPageSize);
              setRunItemsCurrentPage(1);
              return;
            }
            setRunItemsCurrentPage(page);
          },
        }}
        columns={runItemColumns}
      />

      <ValidationHistoryDetailRowDrawer
        open={drawerOpen}
        activeTab="history"
        historyRow={selectedHistoryRow}
        resultsRow={null}
        onClose={() => {
          setDrawerOpen(false);
          setSelectedHistoryRowId('');
        }}
      />
      <LLMScoringCriteriaModal
        open={criteriaModalOpen}
        onClose={() => setCriteriaModalOpen(false)}
      />

      <StandardModal
        open={overrideModalOpen}
        title={overrideModalMode === 'edit' ? 'Run 정보 수정' : 'Run 생성'}
        onCancel={() => setOverrideModalOpen(false)}
        onOk={() => {
          void submitRunModal();
        }}
        okText={overrideModalMode === 'edit' ? '저장' : '생성'}
        cancelText="취소"
        confirmLoading={overrideSaving}
        width={760}
        destroyOnHidden
      >
        <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
          {overrideModalMode === 'edit' ? (
            <>
              현재 Run의 실행 구성, 평가 모델 정보를 수정합니다. 실행 대기
              상태만 수정할 수 있습니다.
            </>
          ) : (
            <>
              테스트를 실행하기 위한 런(Run)을 생성합니다. <br />
              항목에는 선택한 테스트 세트의 기본값이 미리 입력되어 있어요.
            </>
          )}
        </Typography.Paragraph>

        <Form
          form={form}
          layout="vertical"
          className="standard-modal-field-stack"
        >
          {overrideModalMode === 'create' ? (
            <Form.Item
              label="테스트 세트"
              name="testSetId"
              rules={[{ required: true, message: '필수 항목입니다.' }]}
            >
              <Select
                options={testSets.map((testSet) => ({
                  label: `${testSet.name} (${testSet.itemCount}개 질의)`,
                  value: testSet.id,
                }))}
                onChange={(value) => applySelectedTestSetDefaults(value)}
              />
            </Form.Item>
          ) : null}

          <Form.Item
            label="Run 이름"
            name="name"
            rules={[{ required: false, message: '필수 항목입니다.' }]}
          >
            <Input placeholder="빈 값일 경우 기본 이름이 자동으로 생성돼요." />
          </Form.Item>

          <Form.Item
            label="에이전트 모드"
            name="agentId"
            rules={[{ required: true, message: '필수 항목입니다.' }]}
          >
            <Select options={AGENT_MODE_OPTIONS} />
          </Form.Item>
          <Form.Item
            label="평가 모델"
            name="evalModel"
            rules={[{ required: true, message: '필수 항목입니다.' }]}
          >
            <Select options={EVAL_MODEL_OPTIONS} />
          </Form.Item>
          <Space style={{ width: '100%' }} wrap>
            <Form.Item
              label="반복 수"
              name="repeatInConversation"
              rules={[{ required: true, message: '필수 항목입니다.' }]}
            >
              <InputNumber min={1} />
            </Form.Item>
            <Form.Item
              label="채팅방 수"
              name="conversationRoomCount"
              rules={[{ required: true, message: '필수 항목입니다.' }]}
            >
              <InputNumber min={1} />
            </Form.Item>
            <Form.Item
              label="동시 실행 수"
              name="agentParallelCalls"
              rules={[{ required: true, message: '필수 항목입니다.' }]}
            >
              <InputNumber min={1} />
            </Form.Item>
            <Form.Item
              label="타임아웃(ms)"
              name="timeoutMs"
              rules={[{ required: true, message: '필수 항목입니다.' }]}
            >
              <InputNumber min={1000} />
            </Form.Item>
          </Space>
          <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
            • 채팅방 수: 채팅방 단위로 순차 실행됩니다. A 방 완료 후 B 방이
            시작됩니다.
            <br />
            • 반복 수: 채팅방 내 질의를 반복 실행합니다.
            <br />
            • 동시 실행 수: 채팅방 내 질의를 동시에 실행합니다.
            <br />• 타임아웃(ms): 실행 타임아웃(ms)입니다.
          </Typography.Paragraph>
          <Form.Item
            label="Context"
            name="contextJson"
            extra="API 호출 context에 전달할 JSON"
          >
            <Input.TextArea rows={5} placeholder={CONTEXT_SAMPLE} />
          </Form.Item>
        </Form>
      </StandardModal>
    </Space>
  );
}
