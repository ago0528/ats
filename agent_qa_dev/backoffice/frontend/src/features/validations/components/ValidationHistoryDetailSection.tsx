import {
  App,
  Button,
  Empty,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Table,
  Tag,
  Tabs,
  Typography,
  Upload,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { UploadFile } from 'antd/es/upload/interface';
import { DownloadOutlined } from '@ant-design/icons';
import { useEffect, useMemo, useState } from 'react';

import { buildValidationRunExpectedResultsTemplateUrl } from '../../../api/validation';
import type {
  ValidationRun,
  ValidationRunItem,
  ValidationRunExpectedBulkPreviewResult,
  ValidationRunExpectedBulkUpdateResult,
  ValidationRunUpdateRequest,
} from '../../../api/types/validation';
import { StandardModal } from '../../../components/common/StandardModal';
import {
  AGENT_MODE_OPTIONS,
  DEFAULT_AGENT_MODE_VALUE,
  DEFAULT_EVAL_MODEL_VALUE,
  EVAL_MODEL_OPTIONS,
} from '../constants';
import type { HistoryDetailTab } from '../types';
import { canDeleteRun, canUpdateRun } from '../utils/runWorkbench';
import { ValidationHistoryDetailHeaderBar } from './ValidationHistoryDetailHeaderBar';
import { ValidationHistoryDetailHistoryTab } from './ValidationHistoryDetailHistoryTab';
import { ValidationHistoryDetailResultsTab } from './ValidationHistoryDetailResultsTab';
import { ValidationHistoryDetailRowDrawer } from './ValidationHistoryDetailRowDrawer';
import { ValidationHistoryDetailContextMeta } from './ValidationHistoryDetailContextMeta';
import {
  buildHistoryRows,
  buildResultsRows,
  type HistoryRowView,
  type HistoryTableFilters,
  type ResultsFilters,
  type ResultsRowView,
} from '../utils/historyDetailRows';
import { formatDateTime, toTimestamp } from '../../../shared/utils/dateTime';
import { getAgentModeLabel, getLastUpdatedAt, getModelLabel, NOT_AGGREGATED_LABEL } from '../utils/historyDetailDisplay';

const CONTEXT_SAMPLE =
  '{\n  "recruitPlanId": 1234,\n  "채용명": "2026년 상반기 채용"\n}';

const parseContextJson = (raw?: string) => {
  const text = (raw || '').trim();
  if (!text) {
    return { parsedContext: undefined as Record<string, unknown> | undefined };
  }
  try {
    const parsed = JSON.parse(text);
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
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

const formatRelativeUpdatedTime = (updatedAt?: string | null) => {
  const ts = toTimestamp(updatedAt || null);
  if (!ts) return NOT_AGGREGATED_LABEL;
  const diffSec = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (diffSec < 60) return '방금 전';
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}분 전`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}시간 전`;
  if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}일 전`;
  if (diffSec < 2592000) return `${Math.floor(diffSec / 604800)}주 전`;
  if (diffSec < 31536000) return `${Math.floor(diffSec / 2592000)}개월 전`;
  return `${Math.floor(diffSec / 31536000)}년 전`;
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

const EXPECTED_BULK_STATUS_LABEL: Record<string, string> = {
  'planned-update': '업데이트 예정',
  unchanged: '변경 없음',
  'unmapped-item-id': 'Item ID 미매핑',
  'missing-item-id': 'Item ID 누락',
  'duplicate-item-id': 'Item ID 중복',
};

const EXPECTED_BULK_STATUS_COLOR: Record<string, string> = {
  'planned-update': 'blue',
  unchanged: 'default',
  'unmapped-item-id': 'orange',
  'missing-item-id': 'red',
  'duplicate-item-id': 'red',
};

type ExpectedBulkPreviewRow = {
  key: string;
  rowNo: number;
  itemId: string;
  status: string;
  changedFields: string[];
};

const INITIAL_HISTORY_FILTERS: HistoryTableFilters = {
  onlyErrors: false,
  onlySlow: false,
  status: 'all',
  dateRange: [null, null],
};

const INITIAL_RESULTS_FILTERS: ResultsFilters = {
  tablePreset: 'default',
  onlyLowScore: false,
  onlyAbnormal: false,
  onlySlow: false,
  onlyLatencyUnclassified: false,
  scoreBucketFilter: null,
  focusMetric: null,
};

export function ValidationHistoryDetailSection({
  historyRunId,
  historyDetailTab,
  currentRun,
  isHistoryDetailMatched,
  runItems,
  runItemsCurrentPage,
  runItemsPageSize,
  setRunItemsCurrentPage,
  setRunItemsPageSize,
  onOpenInRunWorkspace,
  onChangeHistoryDetailTab,
  onUpdateRun,
  onDeleteRun,
  onPreviewExpectedResultsBulkUpdate,
  onApplyExpectedResultsBulkUpdate,
  testSetNameById = {},
}: {
  historyRunId?: string;
  historyDetailTab: HistoryDetailTab;
  currentRun: ValidationRun | null;
  isHistoryDetailMatched: boolean;
  runItems: ValidationRunItem[];
  runItemsCurrentPage: number;
  runItemsPageSize: number;
  setRunItemsCurrentPage: (value: number) => void;
  setRunItemsPageSize: (value: number) => void;
  onOpenInRunWorkspace?: (payload: { runId: string; testSetId?: string | null }) => void;
  onChangeHistoryDetailTab?: (tab: HistoryDetailTab) => void;
  onUpdateRun?: (runId: string, payload: ValidationRunUpdateRequest) => Promise<void>;
  onDeleteRun?: (runId: string) => Promise<void>;
  onPreviewExpectedResultsBulkUpdate?: (
    runId: string,
    file: File,
  ) => Promise<ValidationRunExpectedBulkPreviewResult>;
  onApplyExpectedResultsBulkUpdate?: (
    runId: string,
    file: File,
  ) => Promise<ValidationRunExpectedBulkUpdateResult>;
  testSetNameById?: Record<string, string>;
}) {
  const [updateModalOpen, setUpdateModalOpen] = useState(false);
  const [updateSaving, setUpdateSaving] = useState(false);
  const [expectedBulkModalOpen, setExpectedBulkModalOpen] = useState(false);
  const [expectedBulkUploading, setExpectedBulkUploading] = useState(false);
  const [expectedBulkFiles, setExpectedBulkFiles] = useState<UploadFile[]>([]);
  const [expectedBulkPreviewRows, setExpectedBulkPreviewRows] = useState<ExpectedBulkPreviewRow[]>([]);
  const [expectedBulkSummary, setExpectedBulkSummary] = useState<ValidationRunExpectedBulkPreviewResult | null>(null);
  const [expectedBulkPreviewEmptyText, setExpectedBulkPreviewEmptyText] = useState('파일을 업로드하면 미리보기가 표시됩니다.');
  const [updateContextSnapshot, setUpdateContextSnapshot] = useState('');
  const [historyFilters, setHistoryFilters] = useState<HistoryTableFilters>(INITIAL_HISTORY_FILTERS);
  const [resultsFilters, setResultsFilters] = useState<ResultsFilters>(INITIAL_RESULTS_FILTERS);
  const [resultsCurrentPage, setResultsCurrentPage] = useState(1);
  const [resultsPageSize, setResultsPageSize] = useState(50);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [historySelectedRow, setHistorySelectedRow] = useState<HistoryRowView | null>(null);
  const [resultsSelectedRow, setResultsSelectedRow] = useState<ResultsRowView | null>(null);
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
  const { modal, message } = App.useApp();

  const testSetName = useMemo(
    () =>
      currentRun?.testSetId
        ? testSetNameById?.[currentRun.testSetId] || currentRun.testSetId
        : '-',
    [currentRun, testSetNameById],
  );
  const historyRows = useMemo(() => buildHistoryRows(runItems), [runItems]);
  const resultsRows = useMemo(() => buildResultsRows(runItems), [runItems]);
  const canEditCurrentRun = canUpdateRun(currentRun);
  const canDeleteCurrentRun = canDeleteRun(currentRun);
  const canOpenExpectedBulkUpdate = Boolean(onPreviewExpectedResultsBulkUpdate && onApplyExpectedResultsBulkUpdate);

  useEffect(() => {
    setHistoryFilters(INITIAL_HISTORY_FILTERS);
    setResultsFilters(INITIAL_RESULTS_FILTERS);
    setResultsCurrentPage(1);
    setDrawerOpen(false);
    setHistorySelectedRow(null);
    setResultsSelectedRow(null);
  }, [currentRun?.id]);

  useEffect(() => {
    setRunItemsCurrentPage(1);
  }, [historyFilters, setRunItemsCurrentPage]);

  useEffect(() => {
    setResultsCurrentPage(1);
  }, [resultsFilters]);

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

  const openExpectedBulkModal = () => {
    setExpectedBulkModalOpen(true);
    setExpectedBulkFiles([]);
    setExpectedBulkPreviewRows([]);
    setExpectedBulkSummary(null);
    setExpectedBulkPreviewEmptyText('파일을 업로드하면 미리보기가 표시됩니다.');
  };

  const closeExpectedBulkModal = () => {
    setExpectedBulkModalOpen(false);
    setExpectedBulkFiles([]);
    setExpectedBulkPreviewRows([]);
    setExpectedBulkSummary(null);
    setExpectedBulkPreviewEmptyText('파일을 업로드하면 미리보기가 표시됩니다.');
  };

  const toExpectedBulkPreviewRows = (
    rows: ValidationRunExpectedBulkPreviewResult['previewRows'],
  ): ExpectedBulkPreviewRow[] =>
    rows.map((row) => ({
      key: `${row.rowNo}:${row.itemId || ''}`,
      rowNo: row.rowNo,
      itemId: row.itemId || '-',
      status: row.status,
      changedFields: Array.isArray(row.changedFields) ? row.changedFields : [],
    }));

  const handleExpectedBulkFileChange = async (nextFiles: UploadFile[]) => {
    setExpectedBulkFiles(nextFiles.slice(-1));
    const origin = nextFiles[0]?.originFileObj;
    if (!origin || !currentRun || !onPreviewExpectedResultsBulkUpdate) {
      setExpectedBulkPreviewRows([]);
      setExpectedBulkSummary(null);
      setExpectedBulkPreviewEmptyText('파일을 업로드하면 미리보기가 표시됩니다.');
      return;
    }

    try {
      setExpectedBulkUploading(true);
      const preview = await onPreviewExpectedResultsBulkUpdate(currentRun.id, origin);
      setExpectedBulkSummary(preview);
      setExpectedBulkPreviewRows(toExpectedBulkPreviewRows(preview.previewRows || []));
      setExpectedBulkPreviewEmptyText('미리보기 데이터가 없습니다.');
    } catch (error) {
      console.error(error);
      setExpectedBulkSummary(null);
      setExpectedBulkPreviewRows([]);
      setExpectedBulkPreviewEmptyText('미리보기에 실패했습니다.');
    } finally {
      setExpectedBulkUploading(false);
    }
  };

  const submitExpectedBulkUpdate = async () => {
    const file = expectedBulkFiles[0]?.originFileObj;
    if (!currentRun || !onApplyExpectedResultsBulkUpdate) {
      return;
    }
    if (!file) {
      message.warning('업로드할 파일을 선택해 주세요.');
      return;
    }
    try {
      setExpectedBulkUploading(true);
      await onApplyExpectedResultsBulkUpdate(currentRun.id, file);
      closeExpectedBulkModal();
    } finally {
      setExpectedBulkUploading(false);
    }
  };

  const expectedBulkPreviewColumns = useMemo<ColumnsType<ExpectedBulkPreviewRow>>(
    () => [
      { key: 'rowNo', title: '행', dataIndex: 'rowNo', width: 80 },
      { key: 'itemId', title: 'Item ID', dataIndex: 'itemId', width: 220, ellipsis: true },
      {
        key: 'status',
        title: '상태',
        dataIndex: 'status',
        width: 140,
        render: (value: string) => (
          <Tag color={EXPECTED_BULK_STATUS_COLOR[value] || 'default'}>
            {EXPECTED_BULK_STATUS_LABEL[value] || value}
          </Tag>
        ),
      },
      {
        key: 'changedFields',
        title: '변경 필드',
        dataIndex: 'changedFields',
        width: 240,
        ellipsis: true,
        render: (value: string[]) => (value.length > 0 ? value.join(', ') : '-'),
      },
    ],
    [],
  );

  const openHistoryRow = (row: HistoryRowView) => {
    setHistorySelectedRow(row);
    setResultsSelectedRow(null);
    setDrawerOpen(true);
  };

  const openResultsRow = (row: ResultsRowView) => {
    setResultsSelectedRow(row);
    setHistorySelectedRow(null);
    setDrawerOpen(true);
  };

  if (!historyRunId) {
    return <Empty description="선택된 Run ID가 없습니다." />;
  }
  if (!isHistoryDetailMatched) {
    return <Empty description="Run 상세를 불러오는 중입니다." />;
  }
  if (!currentRun) {
    return <Empty description="런 상세를 찾을 수 없습니다." />;
  }

  const lastUpdatedAt = getLastUpdatedAt(currentRun);
  const lastUpdatedAbsolute = lastUpdatedAt ? formatDateTime(lastUpdatedAt) : NOT_AGGREGATED_LABEL;
  const lastUpdatedRelative = formatRelativeUpdatedTime(lastUpdatedAt);

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <ValidationHistoryDetailHeaderBar
        currentRun={currentRun}
        onOpenInRunWorkspace={onOpenInRunWorkspace}
        onOpenUpdateRun={openUpdateRunModal}
        onOpenExpectedBulkUpdate={openExpectedBulkModal}
        onDeleteRun={handleDeleteCurrentRun}
        canEditCurrentRun={canEditCurrentRun}
        canDeleteCurrentRun={canDeleteCurrentRun}
        canOpenExpectedBulkUpdate={canOpenExpectedBulkUpdate}
        hasItems={runItems.length > 0}
      />

      <ValidationHistoryDetailContextMeta
        items={[
          { key: 'testSet', label: '테스트 세트', value: testSetName },
          { key: 'agent', label: '에이전트', value: getAgentModeLabel(currentRun.agentId) },
          { key: 'evalModel', label: '평가 모델', value: getModelLabel(currentRun.evalModel) },
          { key: 'updatedAt', label: '마지막 업데이트', value: lastUpdatedRelative, valueTooltip: lastUpdatedAbsolute },
        ]}
      />

      <Tabs
        activeKey={historyDetailTab}
        items={[
          { key: 'history', label: '검증 이력' },
          { key: 'results', label: '평가 결과' },
        ]}
        onChange={(nextTab) => {
          setDrawerOpen(false);
          onChangeHistoryDetailTab?.(nextTab as HistoryDetailTab);
        }}
      />

      {historyDetailTab === 'history' ? (
        <ValidationHistoryDetailHistoryTab
          currentRun={currentRun}
          rows={historyRows}
          filters={historyFilters}
          onChangeFilters={setHistoryFilters}
          currentPage={runItemsCurrentPage}
          pageSize={runItemsPageSize}
          setCurrentPage={setRunItemsCurrentPage}
          setPageSize={setRunItemsPageSize}
          onOpenRow={openHistoryRow}
        />
      ) : (
        <ValidationHistoryDetailResultsTab
          currentRun={currentRun}
          runItems={runItems}
          rows={resultsRows}
          filters={resultsFilters}
          onChangeFilters={setResultsFilters}
          currentPage={resultsCurrentPage}
          pageSize={resultsPageSize}
          setCurrentPage={setResultsCurrentPage}
          setPageSize={setResultsPageSize}
          onOpenRow={openResultsRow}
        />
      )}

      <ValidationHistoryDetailRowDrawer
        open={drawerOpen}
        activeTab={historyDetailTab}
        historyRow={historySelectedRow}
        resultsRow={resultsSelectedRow}
        onClose={() => setDrawerOpen(false)}
      />

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
                extra="채팅방 단위로 순차 실행됩니다. A 방 완료 후 B 방이 시작됩니다."
                rules={[{ required: true, message: '필수 항목입니다.' }]}
              >
                <InputNumber min={1} />
              </Form.Item>
              <Form.Item
                label="동시 실행 수"
                name="agentParallelCalls"
                extra="각 채팅방 내 질의를 N개씩 병렬 처리합니다."
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

      <StandardModal
        title="기대결과 일괄 업데이트"
        open={expectedBulkModalOpen}
        width={920}
        onCancel={closeExpectedBulkModal}
        onOk={() => {
          void submitExpectedBulkUpdate();
        }}
        okText="업데이트"
        cancelText="취소"
        confirmLoading={expectedBulkUploading}
        okButtonProps={{ disabled: !expectedBulkFiles[0]?.originFileObj }}
        destroyOnHidden
      >
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Typography.Text type="secondary">
            이 수정은 원본 질의가 아니라 현재 Run의 스냅샷에만 반영됩니다.
          </Typography.Text>
          <div>
            <Typography.Text>템플릿 다운로드</Typography.Text>
            <div style={{ marginTop: 8 }}>
              <Button
                icon={<DownloadOutlined />}
                href={buildValidationRunExpectedResultsTemplateUrl(currentRun.id)}
              >
                CSV 다운로드
              </Button>
            </div>
          </div>
          <div>
            <Typography.Text>파일 업로드 (CSV/XLSX)</Typography.Text>
            <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <Upload
                beforeUpload={() => false}
                fileList={expectedBulkFiles}
                maxCount={1}
                accept=".csv,.xlsx,.xls"
                showUploadList={false}
                onChange={({ fileList }) => {
                  void handleExpectedBulkFileChange(fileList);
                }}
              >
                <Button>파일 선택</Button>
              </Upload>
              {expectedBulkFiles[0]?.name ? (
                <Typography.Text type="secondary">{expectedBulkFiles[0].name}</Typography.Text>
              ) : null}
            </div>
          </div>
          <Tag color="warning">
            적용 시 기존 평가결과가 초기화되며, 재평가가 필요합니다.
          </Tag>
          <Table
            size="small"
            rowKey="key"
            columns={expectedBulkPreviewColumns}
            dataSource={expectedBulkPreviewRows}
            tableLayout="fixed"
            pagination={false}
            scroll={{ x: 760, y: 280 }}
            locale={{ emptyText: expectedBulkPreviewEmptyText }}
          />
          {expectedBulkSummary ? (
            <Space direction="vertical" size={4}>
              <Typography.Text type="secondary">
                총 {expectedBulkSummary.totalRows}건 중 업데이트 예정 {expectedBulkSummary.plannedUpdateCount}건, 변경 없음 {expectedBulkSummary.unchangedCount}건
              </Typography.Text>
              <Typography.Text type="secondary">
                누락 ID {expectedBulkSummary.missingItemIdRows.length}건 / 중복 ID {expectedBulkSummary.duplicateItemIdRows.length}건 / 미매핑 {expectedBulkSummary.unmappedItemRows.length}건
              </Typography.Text>
              <Typography.Text type="secondary">
                적용 후 빈 기대결과 예상 {expectedBulkSummary.remainingMissingExpectedCountAfterApply}건
              </Typography.Text>
            </Space>
          ) : null}
        </Space>
      </StandardModal>
    </Space>
  );
}
