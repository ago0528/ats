import { useMemo, useState } from 'react';
import {
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  Input,
  InputNumber,
  Select,
  Collapse,
  Space,
  Tabs,
  Tooltip,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';

import type {
  ValidationRun,
  ValidationRunItem,
  ValidationTestSet,
} from '../../../api/types/validation';
import { StandardDataTable } from '../../../components/common/StandardDataTable';
import { StandardModal } from '../../../components/common/StandardModal';
import { RUN_ITEM_INITIAL_COLUMN_WIDTHS } from '../constants';
import {
  getEvaluationProgressText,
  getCombinedRunStateLabel,
  getExecutionStateLabel,
} from '../utils/runProgress';
import {
  canCompareRun,
  canEvaluateRun,
  canExecuteRun,
} from '../utils/runWorkbench';

export type RunCreateOverrides = {
  name?: string;
  agentId?: string;
  evalModel?: string;
  repeatInConversation?: number;
  conversationRoomCount?: number;
  agentParallelCalls?: number;
  timeoutMs?: number;
};

type OverrideFormValues = RunCreateOverrides & {
  testSetId?: string;
};

const WORKBENCH_TAB_KEY = 'workbench';
const COMPARE_TAB_KEY = 'compare';

const trimRunId = (id: string) => {
  const normalized = String(id || '').trim();
  if (!normalized) return '';
  if (normalized.length <= 10) return normalized;
  return `${normalized.slice(0, 8)}...`;
};

const getRunDisplayName = (run: ValidationRun) => {
  const explicitName = run.name?.trim();
  if (explicitName) {
    return explicitName;
  }

  if (run.createdAt) {
    const parsed = new Date(run.createdAt);
    if (!Number.isNaN(parsed.getTime())) {
      const createdText = parsed.toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
      return `Run ${createdText}`;
    }
  }

  const shortId = trimRunId(run.id);
  return shortId ? `Run ${shortId}` : 'Run';
};

const getRunSelectLabel = (run: ValidationRun) => {
  const displayName = getRunDisplayName(run);
  return `${displayName} (${getExecutionStateLabel(run)})`;
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
  baseRunId,
  setBaseRunId,
  handleCreateRun,
  handleExecute,
  handleEvaluate,
  handleCompare,
  compareResult,
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
  baseRunId: string;
  setBaseRunId: (value: string) => void;
  handleCreateRun: (
    testSetId: string,
    overrides: RunCreateOverrides,
  ) => Promise<void>;
  handleExecute: () => Promise<void>;
  handleEvaluate: () => Promise<void>;
  handleCompare: () => Promise<void>;
  compareResult: Record<string, unknown> | null;
  runItemsCurrentPage: number;
  runItemsPageSize: number;
  setRunItemsCurrentPage: (value: number) => void;
  setRunItemsPageSize: (value: number) => void;
  runItemColumns: ColumnsType<ValidationRunItem>;
}) {
  const [activeTab, setActiveTab] = useState<string>(WORKBENCH_TAB_KEY);
  const [overrideModalOpen, setOverrideModalOpen] = useState(false);
  const [overrideSaving, setOverrideSaving] = useState(false);
  const [form] = Form.useForm<OverrideFormValues>();

  const runStateLabel = useMemo(
    () => getCombinedRunStateLabel(currentRun, runItems),
    [currentRun, runItems],
  );
  const evaluationProgressText = useMemo(
    () => getEvaluationProgressText(runItems),
    [runItems],
  );

  const runCreateEnabled = testSets.length > 0;
  const runExecuteEnabled = canExecuteRun(currentRun);
  const runEvaluateEnabled = canEvaluateRun(currentRun);
  const runCompareEnabled = canCompareRun(currentRun, baseRunId);

  const runOptions = runs.map((run) => ({
    label: (
      <Tooltip title={run.id}>
        <span>{getRunSelectLabel(run)}</span>
      </Tooltip>
    ),
    value: run.id,
  }));
  const baseRunOptions = runs
    .filter((run) => run.id !== selectedRunId)
    .map((run) => ({
      label: (
        <Tooltip title={run.id}>
          <span>{getRunSelectLabel(run)}</span>
        </Tooltip>
      ),
      value: run.id,
    }));

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
      agentId: config?.agentId || '',
      evalModel: config?.evalModel || '',
      repeatInConversation: toNumber(config?.repeatInConversation),
      conversationRoomCount: toNumber(config?.conversationRoomCount),
      agentParallelCalls: toNumber(config?.agentParallelCalls),
      timeoutMs: toNumber(config?.timeoutMs),
    });
  };

  const openCreateRunModal = () => {
    form.resetFields();
    const initialTestSetId = selectedTestSetId || testSets[0]?.id || '';
    form.setFieldsValue({
      testSetId: initialTestSetId,
      name: '',
    });
    applySelectedTestSetDefaults(initialTestSetId);
    setOverrideModalOpen(true);
  };

  const submitCreateRun = async () => {
    try {
      const values = await form.validateFields();
      setOverrideSaving(true);
      const { testSetId, ...overrides } = values;
      if (!testSetId) {
        return;
      }
      const trimmedName = overrides.name?.trim();
      await handleCreateRun(testSetId, {
        ...overrides,
        ...(trimmedName ? { name: trimmedName } : {}),
      });
      setOverrideModalOpen(false);
    } finally {
      setOverrideSaving(false);
    }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: WORKBENCH_TAB_KEY,
            label: '워크벤치',
            children: (
              <Space direction="vertical" style={{ width: '100%' }} size={12}>
                <Space wrap size={8} style={{ width: '100%' }}>
                  <Space wrap size={8} style={{ flex: 1, minWidth: 360 }}>
                    <Select
                      style={{ minWidth: 360, width: 360 }}
                      placeholder="현재 Run 선택"
                      value={selectedRunId || undefined}
                      options={runOptions}
                      onChange={(value) => setSelectedRunId(value)}
                    />
                  </Space>
                  <Space wrap size={8}>
                    <Button
                      type="primary"
                      onClick={() => {
                        void openCreateRunModal();
                      }}
                      disabled={!runCreateEnabled}
                    >
                      Run 생성
                    </Button>
                    <Button
                      loading={loading}
                      onClick={() => {
                        void handleExecute();
                      }}
                      disabled={!runExecuteEnabled}
                    >
                      실행 시작
                    </Button>
                    <Button
                      loading={loading}
                      onClick={() => {
                        void handleEvaluate();
                      }}
                      disabled={!runEvaluateEnabled}
                    >
                      평가 시작
                    </Button>
                  </Space>
                </Space>

                <Collapse
                  size="small"
                  defaultActiveKey={[]}
                  ghost
                  items={[
                    {
                      key: 'current-run',
                      label: '현재 Run',
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
                          <Descriptions.Item label="Run 상태">
                            {runStateLabel}
                          </Descriptions.Item>
                          <Descriptions.Item label="실행 구성">
                            반복 수: {currentRun.repeatInConversation}회 /
                            채팅방 수 {currentRun.conversationRoomCount}개 /
                            동시 실행 수: {currentRun.agentParallelCalls}번
                          </Descriptions.Item>
                          <Descriptions.Item label="에이전트 모드">
                            {currentRun.agentId}
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
              </Space>
            ),
          },
          {
            key: COMPARE_TAB_KEY,
            label: '결과 비교',
            children: (
              <Card size="small" title="결과 비교">
                <Space direction="vertical" style={{ width: '100%' }} size={12}>
                  <Space wrap size={8} style={{ width: '100%' }}>
                    <Select
                      placeholder="현재 Run 선택"
                      style={{ width: 360 }}
                      value={selectedRunId || undefined}
                      options={runOptions}
                      onChange={(value) => setSelectedRunId(value)}
                    />
                    <Select
                      placeholder="base Run 선택"
                      style={{ width: 420 }}
                      value={baseRunId || undefined}
                      options={baseRunOptions}
                      onChange={(value) => setBaseRunId(value)}
                    />
                    <Button
                      loading={loading}
                      onClick={() => {
                        void handleCompare();
                      }}
                      disabled={!runCompareEnabled}
                    >
                      비교 실행
                    </Button>
                  </Space>
                  {compareResult ? (
                    <Typography.Paragraph
                      style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}
                    >
                      {JSON.stringify(compareResult, null, 2)}
                    </Typography.Paragraph>
                  ) : (
                    <Typography.Text type="secondary">
                      base Run을 선택한 뒤 비교를 실행하면 결과가 표시됩니다.
                    </Typography.Text>
                  )}
                </Space>
              </Card>
            ),
          },
        ]}
      />

      <StandardModal
        open={overrideModalOpen}
        title="Run 생성"
        onCancel={() => setOverrideModalOpen(false)}
        onOk={() => {
          void submitCreateRun();
        }}
        okText="생성"
        cancelText="취소"
        confirmLoading={overrideSaving}
        destroyOnHidden
      >
        <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
          테스트를 실행하기 위한 런(Run)을 생성합니다. <br />
          항목에는 선택한 테스트 세트의 기본값이 미리 입력되어 있어요.
        </Typography.Paragraph>

        <Form form={form} layout="vertical">
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
            <Input />
          </Form.Item>
          <Form.Item
            label="평가 모델"
            name="evalModel"
            rules={[{ required: true, message: '필수 항목입니다.' }]}
          >
            <Input />
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
        </Form>
      </StandardModal>
    </Space>
  );
}
