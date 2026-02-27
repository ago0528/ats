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
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';

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
import {
  CONTEXT_SAMPLE,
  normalizeAgentModeValue,
  parseContextJson,
  stringifyContext,
} from '../../../shared/utils/validationConfig';
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
import {
  getAgentModeLabel,
  getLastUpdatedAt,
  getModelLabel,
  NOT_AGGREGATED_LABEL,
} from '../utils/historyDetailDisplay';
import {
  getEvaluationStateLabel,
  getExecutionStateLabel,
} from '../utils/runStatus';

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

const HISTORY_FILTER_PARAM_KEYS = [
  'h_status',
  'h_err',
  'h_slow',
  'h_from',
  'h_to',
  'h_page',
  'h_size',
] as const;

const RESULTS_FILTER_PARAM_KEYS = [
  'r_preset',
  'r_low',
  'r_abnormal',
  'r_slow',
  'r_unclassified',
  'r_focus',
  'r_page',
  'r_size',
] as const;

const HISTORY_STATUS_VALUES: HistoryTableFilters['status'][] = [
  'all',
  'success',
  'failed',
  'stopped',
  'pending',
];

const RESULTS_PRESET_VALUES: ResultsFilters['tablePreset'][] = [
  'default',
  'low',
  'abnormal',
  'slow',
];

const RESULTS_FOCUS_VALUES: NonNullable<ResultsFilters['focusMetric']>[] = [
  'intent',
  'accuracy',
  'consistency',
  'speed',
  'stability',
];

const getDateParam = (value: Date | null) => {
  if (!value) return '';
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const parseDateParam = (value: string | null) => {
  const text = String(value || '').trim();
  if (!text) return null;
  const parsed = new Date(`${text}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return null;
  return new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate());
};

const parsePositiveInt = (value: string | null, fallback: number) => {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) return fallback;
  return parsed;
};

const parseBooleanFlag = (value: string | null) => String(value || '') === '1';

const isOneOf = <T extends string>(
  value: string,
  candidates: readonly T[],
): value is T => candidates.includes(value as T);

const hasHistoryDetailViewParams = (search: string) => {
  const params = new URLSearchParams(search);
  return [...HISTORY_FILTER_PARAM_KEYS, ...RESULTS_FILTER_PARAM_KEYS].some(
    (key) => params.has(key),
  );
};

const parseHistoryDetailViewState = (search: string) => {
  const params = new URLSearchParams(search);
  const status = String(params.get('h_status') || '').trim();
  const preset = String(params.get('r_preset') || '').trim();
  const focusMetric = String(params.get('r_focus') || '').trim();

  return {
    historyFilters: {
      onlyErrors: parseBooleanFlag(params.get('h_err')),
      onlySlow: parseBooleanFlag(params.get('h_slow')),
      status: isOneOf(status, HISTORY_STATUS_VALUES)
        ? status
        : INITIAL_HISTORY_FILTERS.status,
      dateRange: [
        parseDateParam(params.get('h_from')),
        parseDateParam(params.get('h_to')),
      ] as [Date | null, Date | null],
    } satisfies HistoryTableFilters,
    resultsFilters: {
      tablePreset: isOneOf(preset, RESULTS_PRESET_VALUES)
        ? preset
        : INITIAL_RESULTS_FILTERS.tablePreset,
      onlyLowScore: parseBooleanFlag(params.get('r_low')),
      onlyAbnormal: parseBooleanFlag(params.get('r_abnormal')),
      onlySlow: parseBooleanFlag(params.get('r_slow')),
      onlyLatencyUnclassified: parseBooleanFlag(params.get('r_unclassified')),
      scoreBucketFilter: null,
      focusMetric: isOneOf(focusMetric, RESULTS_FOCUS_VALUES)
        ? focusMetric
        : null,
    } satisfies ResultsFilters,
    historyPage: parsePositiveInt(params.get('h_page'), 1),
    historyPageSize: parsePositiveInt(params.get('h_size'), 50),
    resultsPage: parsePositiveInt(params.get('r_page'), 1),
    resultsPageSize: parsePositiveInt(params.get('r_size'), 50),
  };
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
  onUpdateRunItemSnapshot,
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
  onOpenInRunWorkspace?: (payload: {
    runId: string;
    testSetId?: string | null;
  }) => void;
  onChangeHistoryDetailTab?: (tab: HistoryDetailTab) => void;
  onUpdateRun?: (
    runId: string,
    payload: ValidationRunUpdateRequest,
  ) => Promise<void>;
  onDeleteRun?: (runId: string) => Promise<void>;
  onUpdateRunItemSnapshot?: (
    runId: string,
    itemId: string,
    payload: {
      expectedResult?: string;
      latencyClass?: 'SINGLE' | 'MULTI' | 'UNCLASSIFIED' | null;
    },
  ) => Promise<void>;
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
  const [expectedBulkPreviewRows, setExpectedBulkPreviewRows] = useState<
    ExpectedBulkPreviewRow[]
  >([]);
  const [expectedBulkSummary, setExpectedBulkSummary] =
    useState<ValidationRunExpectedBulkPreviewResult | null>(null);
  const [expectedBulkPreviewEmptyText, setExpectedBulkPreviewEmptyText] =
    useState('파일을 업로드하면 미리보기가 표시됩니다.');
  const [updateContextSnapshot, setUpdateContextSnapshot] = useState('');
  const [historyFilters, setHistoryFilters] = useState<HistoryTableFilters>(
    INITIAL_HISTORY_FILTERS,
  );
  const [resultsFilters, setResultsFilters] = useState<ResultsFilters>(
    INITIAL_RESULTS_FILTERS,
  );
  const [resultsCurrentPage, setResultsCurrentPage] = useState(1);
  const [resultsPageSize, setResultsPageSize] = useState(50);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [historySelectedRowId, setHistorySelectedRowId] = useState('');
  const [resultsSelectedRowId, setResultsSelectedRowId] = useState('');
  const [latencyClassSavingItemId, setLatencyClassSavingItemId] = useState('');
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
  const location = useLocation();
  const hydratedRunIdRef = useRef('');
  const hydratedSearchRef = useRef('');
  const isHydratingViewStateRef = useRef(false);
  const parsedViewState = useMemo(
    () => parseHistoryDetailViewState(location.search),
    [location.search],
  );

  const testSetName = useMemo(
    () =>
      currentRun?.testSetId
        ? testSetNameById?.[currentRun.testSetId] || currentRun.testSetId
        : '-',
    [currentRun, testSetNameById],
  );
  const historyRows = useMemo(() => buildHistoryRows(runItems), [runItems]);
  const resultsRows = useMemo(() => buildResultsRows(runItems), [runItems]);
  const historySelectedRow = useMemo(
    () =>
      historyRows.find((row) => row.item.id === historySelectedRowId) || null,
    [historyRows, historySelectedRowId],
  );
  const resultsSelectedRow = useMemo(
    () =>
      resultsRows.find((row) => row.item.id === resultsSelectedRowId) || null,
    [resultsRows, resultsSelectedRowId],
  );
  const canEditCurrentRun = canUpdateRun(currentRun);
  const canDeleteCurrentRun = canDeleteRun(currentRun);
  const canOpenExpectedBulkUpdate = Boolean(
    onPreviewExpectedResultsBulkUpdate && onApplyExpectedResultsBulkUpdate,
  );

  useEffect(() => {
    if (!currentRun?.id) return;

    const shouldHydrateForRunChange =
      hydratedRunIdRef.current !== currentRun.id;
    const shouldHydrateForSearch =
      hasHistoryDetailViewParams(location.search) &&
      hydratedSearchRef.current !== location.search;

    if (!shouldHydrateForRunChange && !shouldHydrateForSearch) return;

    hydratedRunIdRef.current = currentRun.id;
    hydratedSearchRef.current = location.search;
    isHydratingViewStateRef.current = true;

    setHistoryFilters(parsedViewState.historyFilters);
    setResultsFilters(parsedViewState.resultsFilters);
    setRunItemsCurrentPage(parsedViewState.historyPage);
    setRunItemsPageSize(parsedViewState.historyPageSize);
    setResultsCurrentPage(parsedViewState.resultsPage);
    setResultsPageSize(parsedViewState.resultsPageSize);
    setDrawerOpen(false);
    setHistorySelectedRowId('');
    setResultsSelectedRowId('');
    setLatencyClassSavingItemId('');
    window.setTimeout(() => {
      isHydratingViewStateRef.current = false;
    }, 0);
  }, [
    currentRun?.id,
    location.search,
    parsedViewState,
    setRunItemsCurrentPage,
    setRunItemsPageSize,
  ]);

  useEffect(() => {
    if (isHydratingViewStateRef.current) return;
    setRunItemsCurrentPage(1);
  }, [historyFilters, setRunItemsCurrentPage]);

  useEffect(() => {
    if (isHydratingViewStateRef.current) return;
    setResultsCurrentPage(1);
  }, [resultsFilters]);

  const openUpdateRunModal = () => {
    if (!currentRun) return;
    const contextText = stringifyContext(currentRun.options?.context);
    setUpdateContextSnapshot(contextText);
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
      content:
        '실행 기록이 없는 PENDING 상태의 Run만 삭제할 수 있습니다. 삭제하시겠습니까?',
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
      setExpectedBulkPreviewEmptyText(
        '파일을 업로드하면 미리보기가 표시됩니다.',
      );
      return;
    }

    try {
      setExpectedBulkUploading(true);
      const preview = await onPreviewExpectedResultsBulkUpdate(
        currentRun.id,
        origin,
      );
      setExpectedBulkSummary(preview);
      setExpectedBulkPreviewRows(
        toExpectedBulkPreviewRows(preview.previewRows || []),
      );
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

  const expectedBulkPreviewColumns = useMemo<
    ColumnsType<ExpectedBulkPreviewRow>
  >(
    () => [
      { key: 'rowNo', title: '행', dataIndex: 'rowNo', width: 80 },
      {
        key: 'itemId',
        title: 'Item ID',
        dataIndex: 'itemId',
        width: 220,
        ellipsis: true,
      },
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
        render: (value: string[]) =>
          value.length > 0 ? value.join(', ') : '-',
      },
    ],
    [],
  );

  const openHistoryRow = (row: HistoryRowView) => {
    setHistorySelectedRowId(row.item.id);
    setResultsSelectedRowId('');
    setDrawerOpen(true);
  };

  const openResultsRow = (row: ResultsRowView) => {
    setResultsSelectedRowId(row.item.id);
    setHistorySelectedRowId('');
    setDrawerOpen(true);
  };

  const handleChangeResultsLatencyClass = async (
    nextLatencyClass: 'SINGLE' | 'MULTI' | 'UNCLASSIFIED',
  ) => {
    const selected = resultsSelectedRow;
    if (!selected || !currentRun || !onUpdateRunItemSnapshot) return;
    try {
      setLatencyClassSavingItemId(selected.item.id);
      await onUpdateRunItemSnapshot(currentRun.id, selected.item.id, {
        latencyClass: nextLatencyClass,
      });
      message.success('응답 속도 타입을 수정했습니다.');
    } catch (error) {
      console.error(error);
      const detail = error instanceof Error ? error.message : '';
      message.error(detail || '응답 속도 타입 수정에 실패했습니다.');
    } finally {
      setLatencyClassSavingItemId('');
    }
  };

  const handleCopyShareLink = useCallback(async () => {
    if (!currentRun) return;

    const params = new URLSearchParams();
    params.set('tab', historyDetailTab);

    if (historyFilters.status !== INITIAL_HISTORY_FILTERS.status) {
      params.set('h_status', historyFilters.status);
    }
    if (historyFilters.onlyErrors) params.set('h_err', '1');
    if (historyFilters.onlySlow) params.set('h_slow', '1');
    if (historyFilters.dateRange[0])
      params.set('h_from', getDateParam(historyFilters.dateRange[0]));
    if (historyFilters.dateRange[1])
      params.set('h_to', getDateParam(historyFilters.dateRange[1]));
    if (runItemsCurrentPage > 1)
      params.set('h_page', String(runItemsCurrentPage));
    if (runItemsPageSize !== 50) params.set('h_size', String(runItemsPageSize));

    if (resultsFilters.tablePreset !== INITIAL_RESULTS_FILTERS.tablePreset) {
      params.set('r_preset', resultsFilters.tablePreset);
    }
    if (resultsFilters.onlyLowScore) params.set('r_low', '1');
    if (resultsFilters.onlyAbnormal) params.set('r_abnormal', '1');
    if (resultsFilters.onlySlow) params.set('r_slow', '1');
    if (resultsFilters.onlyLatencyUnclassified)
      params.set('r_unclassified', '1');
    if (resultsFilters.focusMetric)
      params.set('r_focus', resultsFilters.focusMetric);
    if (resultsCurrentPage > 1)
      params.set('r_page', String(resultsCurrentPage));
    if (resultsPageSize !== 50) params.set('r_size', String(resultsPageSize));

    const queryString = params.toString();
    const sharePath = `/validation/history/${encodeURIComponent(currentRun.id)}${queryString ? `?${queryString}` : ''}`;
    const shareUrl = `${window.location.origin}${sharePath}`;

    const fallbackCopy = () => {
      const textarea = document.createElement('textarea');
      textarea.value = shareUrl;
      textarea.setAttribute('readonly', 'true');
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
    };

    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(shareUrl);
      } else {
        fallbackCopy();
      }
      message.success('공유 링크를 복사했습니다.');
    } catch (error) {
      console.error(error);
      try {
        fallbackCopy();
        message.success('공유 링크를 복사했습니다.');
      } catch (fallbackError) {
        console.error(fallbackError);
        message.error('링크 복사에 실패했습니다.');
      }
    }
  }, [
    currentRun,
    historyDetailTab,
    historyFilters,
    runItemsCurrentPage,
    runItemsPageSize,
    resultsFilters,
    resultsCurrentPage,
    resultsPageSize,
    message,
  ]);

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
  const lastUpdatedAbsolute = lastUpdatedAt
    ? formatDateTime(lastUpdatedAt)
    : NOT_AGGREGATED_LABEL;
  const lastUpdatedRelative = formatRelativeUpdatedTime(lastUpdatedAt);
  const executionStateLabel = getExecutionStateLabel(currentRun);
  const evaluationStateLabel = getEvaluationStateLabel(currentRun, runItems);
  const summaryItems = [
    { key: 'executionState', label: '실행 상태', value: executionStateLabel },
    { key: 'evaluationState', label: '평가 상태', value: evaluationStateLabel },
    {
      key: 'updatedAt',
      label: '마지막 업데이트',
      value: lastUpdatedRelative,
      valueTooltip: lastUpdatedAbsolute,
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <ValidationHistoryDetailHeaderBar
        currentRun={currentRun}
        summaryItems={summaryItems}
        onOpenInRunWorkspace={onOpenInRunWorkspace}
        onCopyShareLink={handleCopyShareLink}
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
          { key: 'runId', label: 'Run ID', value: currentRun.id },
          { key: 'testSet', label: '테스트 세트', value: testSetName },
          {
            key: 'agent',
            label: '에이전트',
            value: getAgentModeLabel(currentRun.agentId),
          },
          {
            key: 'evalModel',
            label: '평가 모델',
            value: getModelLabel(currentRun.evalModel),
          },
        ]}
      />

      <Tabs
        activeKey={historyDetailTab}
        items={[
          { key: 'history', label: '질문 결과' },
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
        resultsLatencyClassSaving={
          Boolean(resultsSelectedRow) &&
          latencyClassSavingItemId === resultsSelectedRow?.item.id
        }
        onChangeResultsLatencyClass={
          historyDetailTab === 'results' && onUpdateRunItemSnapshot
            ? handleChangeResultsLatencyClass
            : undefined
        }
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
          <Form
            form={form}
            layout="vertical"
            className="standard-modal-field-stack"
          >
            <Form.Item
              label="Run 이름"
              name="name"
              rules={[{ required: false }]}
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
            <Form.Item
              label="Context"
              name="contextJson"
              extra="API 호출 context에 전달할 JSON"
            >
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
                href={buildValidationRunExpectedResultsTemplateUrl(
                  currentRun.id,
                )}
              >
                CSV 다운로드
              </Button>
            </div>
          </div>
          <div>
            <Typography.Text>파일 업로드 (CSV/XLSX)</Typography.Text>
            <div
              style={{
                marginTop: 8,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}
            >
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
                <Typography.Text type="secondary">
                  {expectedBulkFiles[0].name}
                </Typography.Text>
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
                총 {expectedBulkSummary.totalRows}건 중 업데이트 예정{' '}
                {expectedBulkSummary.plannedUpdateCount}건, 변경 없음{' '}
                {expectedBulkSummary.unchangedCount}건
              </Typography.Text>
              <Typography.Text type="secondary">
                누락 ID {expectedBulkSummary.missingItemIdRows.length}건 / 중복
                ID {expectedBulkSummary.duplicateItemIdRows.length}건 / 미매핑{' '}
                {expectedBulkSummary.unmappedItemRows.length}건
              </Typography.Text>
              <Typography.Text type="secondary">
                적용 후 빈 기대결과 예상{' '}
                {expectedBulkSummary.remainingMissingExpectedCountAfterApply}건
              </Typography.Text>
            </Space>
          ) : null}
        </Space>
      </StandardModal>
    </Space>
  );
}
