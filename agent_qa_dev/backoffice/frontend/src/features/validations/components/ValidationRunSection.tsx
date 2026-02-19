import { useMemo, useState } from 'react';
import { Button, Card, Descriptions, Empty, Form, Input, InputNumber, Modal, Select, Space, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import type {
  ValidationRun,
  ValidationRunItem,
  ValidationTestSet,
} from '../../../api/types/validation';
import { StandardDataTable } from '../../../components/common/StandardDataTable';
import { RUN_ITEM_INITIAL_COLUMN_WIDTHS } from '../constants';
import { getEvaluationProgressText, getEvaluationStateLabel, getExecutionStateLabel } from '../utils/runProgress';
import { canCompareRun, canCreateRun, canEvaluateRun, canExecuteRun } from '../utils/runWorkbench';

export type RunCreateOverrides = {
  agentId?: string;
  testModel?: string;
  evalModel?: string;
  repeatInConversation?: number;
  conversationRoomCount?: number;
  agentParallelCalls?: number;
  timeoutMs?: number;
};

type OverrideFormValues = RunCreateOverrides;

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
  handleCreateRun: (overrides: RunCreateOverrides) => Promise<void>;
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
  const [overrideModalOpen, setOverrideModalOpen] = useState(false);
  const [overrideSaving, setOverrideSaving] = useState(false);
  const [form] = Form.useForm<OverrideFormValues>();

  const executionStateLabel = useMemo(() => getExecutionStateLabel(currentRun), [currentRun]);
  const evaluationStateLabel = useMemo(() => getEvaluationStateLabel(currentRun, runItems), [currentRun, runItems]);
  const evaluationProgressText = useMemo(() => getEvaluationProgressText(runItems), [runItems]);

  const runCreateEnabled = canCreateRun(selectedTestSetId);
  const runExecuteEnabled = canExecuteRun(currentRun);
  const runEvaluateEnabled = canEvaluateRun(currentRun);
  const runCompareEnabled = canCompareRun(currentRun, baseRunId);

  const runOptions = runs.map((run) => ({
    label: `${run.id} (${run.status})`,
    value: run.id,
  }));
  const baseRunOptions = runs
    .filter((run) => run.id !== selectedRunId)
    .map((run) => ({
      label: `${run.id} (${run.status})`,
      value: run.id,
    }));

  const openCreateRunModal = () => {
    form.setFieldsValue({
      agentId: undefined,
      testModel: undefined,
      evalModel: undefined,
      repeatInConversation: undefined,
      conversationRoomCount: undefined,
      agentParallelCalls: undefined,
      timeoutMs: undefined,
    });
    setOverrideModalOpen(true);
  };

  const submitCreateRun = async () => {
    try {
      const values = await form.validateFields();
      setOverrideSaving(true);
      await handleCreateRun(values);
      setOverrideModalOpen(false);
    } finally {
      setOverrideSaving(false);
    }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <Typography.Text type="secondary">
        테스트 세트를 선택한 뒤 Run을 생성하고, 실행/평가/비교를 run 단위로 독립 수행합니다.
      </Typography.Text>

      <Card size="small" title="테스트 세트 선택 / Run 생성">
        <Space wrap>
          <Select
            style={{ width: 360 }}
            placeholder="테스트 세트 선택"
            value={selectedTestSetId || undefined}
            options={testSets.map((testSet) => ({ label: `${testSet.name} (${testSet.itemCount}개 질의)`, value: testSet.id }))}
            onChange={(value) => {
              setSelectedTestSetId(value);
              setBaseRunId('');
            }}
          />
          <Button type="primary" onClick={openCreateRunModal} disabled={!runCreateEnabled}>
            Run 생성(PENDING)
          </Button>
          <Select
            style={{ width: 420 }}
            placeholder="기존 Run 선택"
            value={selectedRunId || undefined}
            options={runOptions}
            onChange={(value) => setSelectedRunId(value)}
          />
        </Space>
      </Card>

      {currentRun ? (
        <Descriptions size="small" bordered column={3}>
          <Descriptions.Item label="Run ID">{currentRun.id}</Descriptions.Item>
          <Descriptions.Item label="테스트 세트">{currentRun.testSetId || '-'}</Descriptions.Item>
          <Descriptions.Item label="Run 상태">{currentRun.status}</Descriptions.Item>
          <Descriptions.Item label="실행 상태">{executionStateLabel}</Descriptions.Item>
          <Descriptions.Item label="평가 상태">{evaluationStateLabel}</Descriptions.Item>
          <Descriptions.Item label="LLM 평가 진행">{evaluationProgressText}</Descriptions.Item>
          <Descriptions.Item label="총/완료/오류">
            {currentRun.totalItems} / {currentRun.doneItems} / {currentRun.errorItems}
          </Descriptions.Item>
          <Descriptions.Item label="Agent">{currentRun.agentId}</Descriptions.Item>
          <Descriptions.Item label="모델">
            {currentRun.testModel} / {currentRun.evalModel}
          </Descriptions.Item>
        </Descriptions>
      ) : (
        <Empty description="선택된 Run이 없습니다." />
      )}

      <Card size="small" title="Run 워크벤치">
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Space wrap>
            <Button loading={loading} onClick={() => { void handleExecute(); }} disabled={!runExecuteEnabled}>
              실행 시작
            </Button>
            <Button loading={loading} onClick={() => { void handleEvaluate(); }} disabled={!runEvaluateEnabled}>
              평가 시작
            </Button>
            <Select
              placeholder="비교 기준 Run 선택"
              style={{ width: 420 }}
              value={baseRunId || undefined}
              options={baseRunOptions}
              onChange={(value) => setBaseRunId(value)}
            />
            <Button loading={loading} onClick={() => { void handleCompare(); }} disabled={!runCompareEnabled}>
              결과 비교
            </Button>
          </Space>

          <StandardDataTable
            tableId="validation-run-items"
            initialColumnWidths={RUN_ITEM_INITIAL_COLUMN_WIDTHS}
            minColumnWidth={84}
            wrapperClassName="validation-results-table-wrap"
            className="query-management-table validation-results-table"
            rowKey="id"
            size="small"
            tableLayout="fixed"
            dataSource={runItems}
            locale={{ emptyText: <Empty description="Run 결과가 없습니다." /> }}
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

          <Card size="small" title="비교 결과">
            {compareResult ? (
              <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
                {JSON.stringify(compareResult, null, 2)}
              </Typography.Paragraph>
            ) : (
              <Typography.Text type="secondary">
                현재 run과 비교 기준 run을 선택한 뒤 비교를 실행하면 결과가 표시됩니다.
              </Typography.Text>
            )}
          </Card>
        </Space>
      </Card>

      <Modal
        open={overrideModalOpen}
        title="Run 생성 오버라이드"
        onCancel={() => setOverrideModalOpen(false)}
        onOk={() => { void submitCreateRun(); }}
        okText="Run 생성"
        confirmLoading={overrideSaving}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          <Form.Item label="Agent ID" name="agentId">
            <Input placeholder="기본값 사용 시 비워두세요." />
          </Form.Item>
          <Form.Item label="Test Model" name="testModel">
            <Input placeholder="기본값 사용 시 비워두세요." />
          </Form.Item>
          <Form.Item label="Eval Model" name="evalModel">
            <Input placeholder="기본값 사용 시 비워두세요." />
          </Form.Item>
          <Space style={{ width: '100%' }} wrap>
            <Form.Item label="반복 수" name="repeatInConversation">
              <InputNumber min={1} />
            </Form.Item>
            <Form.Item label="채팅방 수" name="conversationRoomCount">
              <InputNumber min={1} />
            </Form.Item>
            <Form.Item label="병렬 호출 수" name="agentParallelCalls">
              <InputNumber min={1} />
            </Form.Item>
            <Form.Item label="타임아웃(ms)" name="timeoutMs">
              <InputNumber min={1000} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </Space>
  );
}
