import { App, Button, Descriptions, Empty, Form, Input, InputNumber, Select, Space } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useMemo, useState } from 'react';

import { buildValidationRunExportUrl } from '../../../api/validation';
import type {
  ValidationRun,
  ValidationRunItem,
  ValidationRunUpdateRequest,
} from '../../../api/types/validation';
import { StandardDataTable } from '../../../components/common/StandardDataTable';
import { StandardModal } from '../../../components/common/StandardModal';
import { AGENT_MODE_OPTIONS, DEFAULT_AGENT_MODE_VALUE, DEFAULT_EVAL_MODEL_VALUE, EVAL_MODEL_OPTIONS } from '../constants';
import { HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS } from '../constants';
import {
  getRunDisplayName,
  getRunExecutionConfigText,
  getValidationRunAggregateSummary,
} from '../utils/runDisplay';
import {
  getEvaluationStateLabel,
  getEvaluationProgressText,
} from '../utils/runProgress';
import { canDeleteRun, canUpdateRun } from '../utils/runWorkbench';
import { getExecutionStateLabel } from '../utils/runStatus';
import { DownloadOutlined, ExportOutlined } from '@ant-design/icons';

const CONTEXT_SAMPLE =
  '{\n  "recruitPlanId": 1234,\n  "채용명": "2026년 상반기 채용"\n}';

const parseContextJson = (raw?: string) => {
  const text = (raw || '').trim();
  if (!text) {
    return { parsedContext: undefined as Record<string, unknown> | undefined };
  }
  try {
    const parsed = JSON.parse(text);
    if (
      parsed === null ||
      typeof parsed !== 'object' ||
      Array.isArray(parsed)
    ) {
      return {
        parsedContext: undefined,
        parseError: 'context는 JSON 객체 형태여야 합니다.',
      };
    }
    return { parsedContext: parsed as Record<string, unknown> };
  } catch (error) {
    return {
      parsedContext: undefined,
      parseError:
        `context JSON 형식이 올바르지 않습니다. ${error instanceof Error ? error.message : ''}`.trim(),
    };
  }
};

const stringifyContext = (value?: unknown) => {
  if (value === undefined || value === null) {
    return '';
  }
  if (typeof value === 'string') {
    return value.trim();
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '';
  }
};

const normalizeAgentModeValue = (value?: string) => {
  const trimmed = (value || '').trim();
  if (!trimmed) {
    return DEFAULT_AGENT_MODE_VALUE;
  }
  if (trimmed === 'ORCHESTRATOR_WORKER_V3') {
    return DEFAULT_AGENT_MODE_VALUE;
  }
  return trimmed;
};

export function ValidationHistoryDetailSection({
  historyRunId,
  currentRun,
  isHistoryDetailMatched,
  runItems,
  runItemsCurrentPage,
  runItemsPageSize,
  setRunItemsCurrentPage,
  setRunItemsPageSize,
  onBackToHistory,
  onOpenInRunWorkspace,
  onUpdateRun,
  onDeleteRun,
  historyDetailItemColumns,
  testSetNameById = {},
}: {
  historyRunId?: string;
  currentRun: ValidationRun | null;
  isHistoryDetailMatched: boolean;
  runItems: ValidationRunItem[];
  runItemsCurrentPage: number;
  runItemsPageSize: number;
  setRunItemsCurrentPage: (value: number) => void;
  setRunItemsPageSize: (value: number) => void;
  onBackToHistory?: () => void;
  onOpenInRunWorkspace?: (payload: {
    runId: string;
    testSetId?: string | null;
  }) => void;
  onUpdateRun?: (
    runId: string,
    payload: ValidationRunUpdateRequest,
  ) => Promise<void>;
  onDeleteRun?: (runId: string) => Promise<void>;
  historyDetailItemColumns: ColumnsType<ValidationRunItem>;
  testSetNameById?: Record<string, string>;
}) {
  const [updateModalOpen, setUpdateModalOpen] = useState(false);
  const [updateSaving, setUpdateSaving] = useState(false);
  const [updateContextSnapshot, setUpdateContextSnapshot] = useState('');
  const [form] = Form.useForm<{
    name?: string;
    agentId?: string;
    evalModel?: string;
    repeatInConversation?: number;
    conversationRoomCount?: number;
    agentParallelCalls?: number;
    timeoutMs?: number;
    contextJson?: string;
  }>();

  const testSetName = useMemo(
    () =>
      currentRun?.testSetId
        ? testSetNameById?.[currentRun.testSetId] || currentRun.testSetId
        : '-',
    [currentRun, testSetNameById],
  );
  const aggregateSummary = useMemo(
    () => getValidationRunAggregateSummary(currentRun, runItems),
    [currentRun, runItems],
  );
  const executionStateLabel = useMemo(
    () => getExecutionStateLabel(currentRun),
    [currentRun],
  );
  const evaluationStateLabel = useMemo(
    () => getEvaluationStateLabel(currentRun, runItems),
    [currentRun, runItems],
  );
  const canEditCurrentRun = canUpdateRun(currentRun);
  const canDeleteCurrentRun = canDeleteRun(currentRun);
  const { modal } = App.useApp();

  const openUpdateRunModal = () => {
    if (!currentRun) return;
    const contextText = stringifyContext(currentRun.options?.context);
    setUpdateContextSnapshot(contextText);
    form.resetFields();
    form.setFieldsValue({
      name: currentRun.name || '',
      agentId: normalizeAgentModeValue(currentRun.agentId),
      evalModel: currentRun.evalModel || DEFAULT_EVAL_MODEL_VALUE,
      repeatInConversation: currentRun.repeatInConversation,
      conversationRoomCount: currentRun.conversationRoomCount,
      agentParallelCalls: currentRun.agentParallelCalls,
      timeoutMs: currentRun.timeoutMs,
      contextJson: contextText,
    });
    setUpdateModalOpen(true);
  };

  const submitUpdateRun = async () => {
    try {
      const values = await form.validateFields();
      const { contextJson, ...runConfig } = values;
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
      setUpdateSaving(true);
      const trimmedName = runConfig.name?.trim();
      const contextText = (contextJson || '').trim();
      const payload: ValidationRunUpdateRequest = {
        ...runConfig,
        ...(trimmedName ? { name: trimmedName } : {}),
      };
      if (!trimmedName) {
        delete payload.name;
      }
      if (contextText !== updateContextSnapshot) {
        payload.context = parsedContext.parsedContext ?? null;
      }
      if (!onUpdateRun || !currentRun) {
        return;
      }
      await onUpdateRun(currentRun.id, payload);
      setUpdateModalOpen(false);
    } finally {
      setUpdateSaving(false);
    }
  };

  const handleDeleteCurrentRun = () => {
    if (!currentRun || !onDeleteRun) return;
    modal.confirm({
      title: 'Run 삭제',
      content: '실행 기록이 없는 PENDING 상태의 Run만 삭제할 수 있습니다. 삭제하시겠습니까?',
      okText: '삭제',
      cancelText: '취소',
      okType: 'danger',
      onOk: async () => {
        await onDeleteRun(currentRun.id);
      },
    });
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <Space>
        <Button onClick={() => onBackToHistory?.()}>목록으로</Button>
        <Button
          onClick={() => void openUpdateRunModal()}
          disabled={!canEditCurrentRun || !isHistoryDetailMatched || !currentRun}
        >
          Run 수정
        </Button>
        <Button
          danger
          onClick={() => {
            void handleDeleteCurrentRun();
          }}
          disabled={!canDeleteCurrentRun || !isHistoryDetailMatched || !currentRun}
        >
          Run 삭제
        </Button>
        <Button
          icon={<ExportOutlined />}
          onClick={() => {
            if (!currentRun) return;
            onOpenInRunWorkspace?.({
              runId: currentRun.id,
              testSetId: currentRun.testSetId ?? undefined,
            });
          }}
          disabled={!currentRun || !isHistoryDetailMatched}
        >
          검증 실행에서 이 run 열기
        </Button>
        <Button
          type="primary"
          icon={<DownloadOutlined />}
          href={
            currentRun && isHistoryDetailMatched
              ? buildValidationRunExportUrl(currentRun.id)
              : undefined
          }
          disabled={
            !currentRun || !isHistoryDetailMatched || runItems.length === 0
          }
        >
          엑셀 다운로드
        </Button>
      </Space>

      {!historyRunId ? (
        <Empty description="선택된 Run ID가 없습니다." />
      ) : !isHistoryDetailMatched ? (
        <Empty description="Run 상세를 불러오는 중입니다." />
      ) : currentRun ? (
        <>
          <Descriptions size="small" bordered column={3}>
            <Descriptions.Item label="Run 이름">
              <span title={currentRun.id}>{getRunDisplayName(currentRun)}</span>
            </Descriptions.Item>
            <Descriptions.Item label="테스트 세트">
              {testSetName}
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
              {currentRun.agentId}
            </Descriptions.Item>
            <Descriptions.Item label="총/완료/오류">
              {currentRun.totalItems} / {currentRun.doneItems} /{' '}
              {currentRun.errorItems}
            </Descriptions.Item>
            <Descriptions.Item label="LLM 평가 진행">
              {getEvaluationProgressText(runItems)}
            </Descriptions.Item>
            <Descriptions.Item label="평가 모델">
              {currentRun.evalModel}
            </Descriptions.Item>
            <Descriptions.Item label="평균 응답시간(초)">
              {aggregateSummary.averageResponseTimeSecText}
            </Descriptions.Item>
            <Descriptions.Item label="응답시간 p50(초)">
              {aggregateSummary.responseTimeP50SecText}
            </Descriptions.Item>
            <Descriptions.Item label="응답시간 p95(초)">
              {aggregateSummary.responseTimeP95SecText}
            </Descriptions.Item>
            <Descriptions.Item label="Logic PASS율">
              {aggregateSummary.logicPassRateText}
            </Descriptions.Item>
            <Descriptions.Item label="LLM 평가율">
              {aggregateSummary.llmDoneRateText}
            </Descriptions.Item>
            <Descriptions.Item label="LLM PASS율">
              {aggregateSummary.llmPassRateText}
            </Descriptions.Item>
            <Descriptions.Item label="LLM 평균 점수">
              {aggregateSummary.llmTotalScoreAvgText}
            </Descriptions.Item>
          </Descriptions>

          <StandardDataTable
            tableId="validation-history-detail-items"
            initialColumnWidths={HISTORY_DETAIL_ITEM_INITIAL_COLUMN_WIDTHS}
            minColumnWidth={84}
            wrapperClassName="validation-history-detail-table-wrap"
            className="query-management-table validation-history-detail-table"
            rowKey="id"
            size="small"
            tableLayout="fixed"
            dataSource={runItems}
            locale={{ emptyText: <Empty description="실행 결과 없음" /> }}
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
            columns={historyDetailItemColumns}
          />
        </>
      ) : (
        <Empty description="런 상세를 찾을 수 없습니다." />
      )}
      <StandardModal
        open={updateModalOpen}
        title="Run 정보 수정"
        onCancel={() => setUpdateModalOpen(false)}
        onOk={() => {
          void submitUpdateRun();
        }}
        okText="저장"
        cancelText="취소"
        confirmLoading={updateSaving}
        width={760}
        destroyOnHidden
      >
        <Space direction="vertical" style={{ width: '100%' }} size={8}>
          <Form form={form} layout="vertical" className="standard-modal-field-stack">
            <Form.Item label="Run 이름" name="name" rules={[{ required: false }]}>
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
            <Form.Item label="Context" name="contextJson" extra="API 호출 context에 전달할 JSON">
              <Input.TextArea rows={5} placeholder={CONTEXT_SAMPLE} />
            </Form.Item>
          </Form>
        </Space>
      </StandardModal>
    </Space>
  );
}
