import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Affix,
  App,
  Button,
  Card,
  Collapse,
  Col,
  Drawer,
  Empty,
  Input,
  InputNumber,
  Steps,
  Progress,
  Row,
  Segmented,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography,
  Upload,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { UploadFile } from 'antd/es/upload/interface';
import { ClockCircleOutlined, CloudUploadOutlined, LoadingOutlined, PlayCircleOutlined, ReloadOutlined, FileExcelOutlined } from '@ant-design/icons';

import { api } from '../../api/client';
import { RuntimeSecrets } from '../../app/types';
import { StandardDataTable } from '../../components/common/StandardDataTable';
import { splitCsvLine } from '../../shared/utils/csv';
import { formatLocaleDateTime, formatLocaleTime } from '../../shared/utils/dateTime';
import { getRequestErrorMessage } from '../../shared/utils/error';
import { tryPrettyJson } from '../../shared/utils/json';
import { MetricsBar } from './components/MetricsBar';
import type { RowItem } from './components/RunTable';
import type { Environment } from '../../app/EnvironmentScope';

export type GenericRunMeta = {
  runId: string;
  status: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED';
  totalRows: number;
  doneRows: number;
  errorRows: number;
  llmDoneRows: number;
  createdAt?: string;
  startedAt?: string | null;
  finishedAt?: string | null;
};

type InputMode = 'upload' | 'single';
type RunStep = 0 | 1;
type RunAction = 'idle' | 'creating' | 'executing' | 'evaluating';

type DisplayRowItem = RowItem & {
  llmEvalJson?: string | null;
};

type CsvSummary = {
  fileName: string;
  rowCount: number;
  missingColumns: string[];
  emptyRows: number;
  invalidRows: number;
  isValid: boolean;
};

export const RUN_CREATION_LABEL = '검증 실행 생성';
export const RUN_CREATION_HELP_TOOLTIP =
  'CSV 업로드 또는 단일 질의를 입력한 뒤 1단계(실행 준비) -> 2단계(실행/평가) 순서로 진행하세요.';

const REQUIRED_UPLOAD_COLUMNS = ['질의', 'LLM 평가기준', '검증 필드', '기대값'];
const DEFAULT_OPENAI_MODEL = 'gpt-5.2';
const POLL_INTERVAL_MS = 2000;
const STALE_SECONDS = 15;
const RESULT_INITIAL_COLUMN_WIDTHS = {
  ordinal: 72,
  query: 360,
  status: 96,
  message: 280,
};

const clampNumber = (input: number | null | undefined, fallback: number) => {
  const value = Number(input);
  if (!Number.isFinite(value)) return fallback;
  if (value < 1) return 1;
  return Math.trunc(value);
};

const statusColor = (status: '미실행' | '실행중' | '완료' | '실패' | '중지중') => {
  if (status === '미실행' || status === '중지중') return 'default';
  if (status === '실행중') return 'processing';
  if (status === '완료') return 'success';
  return 'error';
};

async function inspectCsvFile(file: File): Promise<CsvSummary> {
  const raw = (await file.text()).replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();
  if (!raw) {
    return {
      fileName: file.name,
      rowCount: 0,
      missingColumns: [...REQUIRED_UPLOAD_COLUMNS],
      emptyRows: 0,
      invalidRows: 0,
      isValid: false,
    };
  }

  const lines = raw.split('\n').map((line) => line.replace(/\uFEFF/g, '').trim()).filter(Boolean);
  if (lines.length <= 1) {
    return {
      fileName: file.name,
      rowCount: 0,
      missingColumns: [...REQUIRED_UPLOAD_COLUMNS],
      emptyRows: 0,
      invalidRows: 0,
      isValid: false,
    };
  }

  const headerColumns = splitCsvLine(lines[0]).map((item) => item.replace(/^"|"$/g, ''));
  const missingColumns = REQUIRED_UPLOAD_COLUMNS.filter((header) => !headerColumns.includes(header));
  const queryIndex = headerColumns.findIndex((item) => item === '질의');
  const dataLines = lines.slice(1);
  const invalidRows = dataLines.reduce((count, line) => {
    const columns = splitCsvLine(line);
    const queryValue = queryIndex >= 0 ? columns[queryIndex] : '';
    return count + (queryValue.trim() ? 0 : 1);
  }, 0);

  const emptyRows = dataLines.reduce((count, line) => {
    const parsed = splitCsvLine(line);
    return count + (parsed.every((cell) => !cell.trim()) ? 1 : 0);
  }, 0);

  const rowCount = dataLines.length;

  return {
    fileName: file.name,
    rowCount,
    missingColumns,
    emptyRows,
    invalidRows,
    isValid: rowCount > 0 && missingColumns.length === 0 && invalidRows === 0,
  };
}

function isRowFailed(row: RowItem): boolean {
  const logic = String(row.logicResult ?? '').trim().toUpperCase();
  const llm = String(row.llmEvalStatus ?? '').trim().toUpperCase();
  const hasError = Boolean(String(row.error ?? '').trim());
  return hasError || logic.startsWith('FAIL') || logic.startsWith('FAILED') || llm.startsWith('FAILED');
}

function isRowDone(row: RowItem): boolean {
  return Boolean(String(row.responseText ?? '').trim() || String(row.error ?? '').trim() || String(row.llmEvalStatus ?? '').trim());
}

function isRowSuccess(row: RowItem): boolean {
  if (isRowFailed(row)) {
    return false;
  }
  if (String(row.llmEvalStatus ?? '').trim().startsWith('FAILED')) {
    return false;
  }
  return isRowDone(row);
}

function rowStatusTag(row: RowItem) {
  if (isRowFailed(row)) return <Tag color="error">실패</Tag>;
  if (isRowSuccess(row)) return <Tag color="success">성공</Tag>;
  if (isRowDone(row)) return <Tag color="processing">완료</Tag>;
  return <Tag color="default">대기</Tag>;
}

function rowShortMessage(row: RowItem) {
  if (String(row.error ?? '').trim()) {
    return String(row.error);
  }
  if (String(row.logicResult ?? '').trim()) {
    return String(row.logicResult);
  }
  if (String(row.executionProcess ?? '').trim()) {
    return String(row.executionProcess);
  }
  if (String(row.llmEvalStatus ?? '').trim()) {
    return String(row.llmEvalStatus);
  }
  return '결과 수신 대기';
}

function formatTimeLabel(isoValue?: string | null) {
  return formatLocaleDateTime(isoValue);
}

function buildErrorSummary(run: GenericRunMeta | null, rows: RowItem[]) {
  if (!run) {
    return null;
  }

  const failRows = rows.filter((row) => isRowFailed(row));
  const firstFailure = failRows[0];

  if (!firstFailure) {
    if (run.status === 'FAILED') {
      return {
        stage: '실행 단계',
        reason: '서버에서 실행 실패 응답을 받았습니다. 잠시 후 재시도 해주세요.',
      };
    }
    return null;
  }

  const failedAtEvaluate = String(firstFailure.llmEvalStatus ?? '').trim().startsWith('FAILED');
  return {
    stage: failedAtEvaluate ? '2단계 평가' : '1단계 실행',
    reason: rowShortMessage(firstFailure),
    retryHint: '동일 입력으로 재실행하면 같은 조건에서 다시 처리합니다.',
  };
}

export function GenericRunPage({ environment, tokens }: { environment: Environment; tokens: RuntimeSecrets }) {
  const { message } = App.useApp();
  const [step, setStep] = useState<RunStep>(0);
  const [inputMode, setInputMode] = useState<InputMode>('upload');

  const [files, setFiles] = useState<UploadFile[]>([]);
  const [uploadSummary, setUploadSummary] = useState<CsvSummary | null>(null);
  const [isCsvAnalyzing, setIsCsvAnalyzing] = useState(false);

  const [singleQuery, setSingleQuery] = useState('');
  const [singleLlmCriteria, setSingleLlmCriteria] = useState('');
  const [singleField, setSingleField] = useState('');
  const [singleExpected, setSingleExpected] = useState('');

  const [openaiKey, setOpenaiKey] = useState('');
  const [openaiModel, setOpenaiModel] = useState(DEFAULT_OPENAI_MODEL);
  const [maxParallel, setMaxParallel] = useState(3);
  const [maxChars, setMaxChars] = useState(15000);
  const [contextJson, setContextJson] = useState('');
  const [targetAssistant, setTargetAssistant] = useState('');

  const [rows, setRows] = useState<DisplayRowItem[]>([]);
  const [run, setRun] = useState<GenericRunMeta | null>(null);
  const [action, setAction] = useState<RunAction>('idle');
  const [shouldEvaluate, setShouldEvaluate] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedRow, setSelectedRow] = useState<DisplayRowItem | null>(null);
  const [resultCurrentPage, setResultCurrentPage] = useState(1);
  const [resultPageSize, setResultPageSize] = useState<number>(50);
  const [pollError, setPollError] = useState('');
  const [lastUpdateAt, setLastUpdateAt] = useState(0);
  const [lastProgressChangeAt, setLastProgressChangeAt] = useState<number>(Date.now());

  const hasTokens = Boolean(tokens.bearer && tokens.cms && tokens.mrs);
  const runId = run?.runId ?? '';

  const isBusy = useMemo(() => action !== 'idle' || run?.status === 'RUNNING', [action, run?.status]);

  const canRunInput = useMemo(() => {
    if (inputMode === 'upload') {
      return Boolean(uploadSummary?.isValid) && Boolean(files[0]?.originFileObj);
    }
    return Boolean(singleQuery.trim());
  }, [files, inputMode, singleQuery, uploadSummary]);

  const canStartRun = useMemo(() => canRunInput && hasTokens && !isBusy, [canRunInput, hasTokens, isBusy]);

  const progressTotal = run?.totalRows ?? rows.length;
  const progressDone = run?.doneRows ?? 0;
  const progressError = run?.errorRows ?? 0;
  const progressCount = Math.min(progressTotal, progressDone + progressError);
  const progressPercent = progressTotal > 0 ? Math.round((progressCount / progressTotal) * 100) : 0;

  const summary = useMemo(() => {
    const total = progressTotal;
    const failed = rows.filter(isRowFailed).length;
    const success = rows.filter(isRowSuccess).length;
    const done = rows.filter(isRowDone).length;
    const llmDone = rows.filter((row) => {
      const status = String(row.llmEvalStatus ?? '').trim();
      if (!status) return false;
      return status === 'DONE' || status.startsWith('SKIPPED');
    }).length;
    return {
      total,
      success,
      failed,
      done,
      llmDone,
      inProgress: Math.max(total - done, 0),
      errors: failed,
    };
  }, [progressTotal, rows]);

  const runStateLabel = useMemo(() => {
    if (!run) {
      return '미실행';
    }
    if (action === 'evaluating') return '실행중';
    if (action === 'executing' || action === 'creating') return '실행중';
    if (run.status === 'RUNNING') return '실행중';
    if (run.status === 'DONE') return '완료';
    if (run.status === 'FAILED') return '실패';
    return '미실행';
  }, [action, run]);

  const pipelineText = useMemo(() => {
    if (action === 'creating') return '업로드 처리중';
    if (action === 'executing') {
      return run?.status === 'RUNNING' ? '1단계 실행중' : '실행 요청중';
    }
    if (action === 'evaluating') return '2단계 평가중';
    if (!run) return '입력 대기';
    if (run.status === 'RUNNING') return '결과 수신중';
    if (run.status === 'DONE') return '결과 수신완료';
    if (run.status === 'FAILED') return '실패';
    return '입력 대기';
  }, [action, run]);

  const isStale = useMemo(() => {
    if (!isBusy) return false;
    return Date.now() - lastProgressChangeAt > STALE_SECONDS * 1000;
  }, [isBusy, lastProgressChangeAt]);

  const staleText = useMemo(() => {
    if (!isStale) return '';
    return `결과 수신 지연 중 (마지막 업데이트: ${formatLocaleTime(lastProgressChangeAt)})`;
  }, [isStale, lastProgressChangeAt]);

  const failureSummary = useMemo(() => buildErrorSummary(run, rows), [rows, run]);

  const updateRunAndRows = async (id: string) => {
    const [runResp, rowsResp] = await Promise.all([
      api.get(`/generic-runs/${id}`),
      api.get(`/generic-runs/${id}/rows`),
    ]);
    setRun(runResp.data as GenericRunMeta);
    setRows((rowsResp.data.rows || []) as DisplayRowItem[]);
    setPollError('');
    setLastUpdateAt(Date.now());
    setLastProgressChangeAt(Date.now());
  };

  const loadRunRows = async () => {
    if (!runId) return;
    try {
      await updateRunAndRows(runId);
    } catch (error) {
      console.error(error);
      setPollError('결과 조회 실패. 네트워크 또는 백엔드 상태를 확인해 주세요.');
    }
  };

  useEffect(() => {
    if (!runId || !isBusy) {
      return;
    }

    void loadRunRows();
    const timer = setInterval(() => {
      void loadRunRows();
    }, POLL_INTERVAL_MS);

    return () => {
      clearInterval(timer);
    };
  }, [runId, isBusy]);

  useEffect(() => {
    if (!run?.runId || action !== 'executing' || !shouldEvaluate) {
      return;
    }

    if (run.status === 'RUNNING') {
      return;
    }

    if (run.status === 'FAILED') {
      setAction('idle');
      setShouldEvaluate(false);
      return;
    }

    if (run.status === 'DONE') {
      void runEvaluation(run.runId);
    }
  }, [action, run?.status, run?.runId, shouldEvaluate]);

  useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(rows.length / resultPageSize));
    if (resultCurrentPage > maxPage) {
      setResultCurrentPage(maxPage);
    }
  }, [rows.length, resultCurrentPage, resultPageSize]);

  const handleCsvChange = async (info: { fileList: UploadFile[] }) => {
    const nextFiles = info.fileList.slice(-1);
    setFiles(nextFiles);
    setUploadSummary(null);

    const candidate = nextFiles[0]?.originFileObj;
    if (!candidate) {
      return;
    }

    setIsCsvAnalyzing(true);
    try {
      const summary = await inspectCsvFile(candidate);
      setUploadSummary(summary);
      if (!summary.isValid) {
        message.warning('CSV 기본 유효성 검사가 통과되지 않았습니다. 누락/빈 행을 확인하세요.');
      }
    } catch {
      message.error('CSV 유효성 검사에 실패했습니다.');
      setUploadSummary((prev) =>
        prev
          ? prev
          : {
              fileName: candidate.name,
              rowCount: 0,
              missingColumns: [...REQUIRED_UPLOAD_COLUMNS],
              emptyRows: 0,
              invalidRows: 0,
              isValid: false,
            },
      );
    } finally {
      setIsCsvAnalyzing(false);
    }
  };

  const handleTemplateDownload = () => {
    window.open(`${api.defaults.baseURL}/generic-runs/template`, '_blank');
  };

  const createRunFromCsv = async (): Promise<string> => {
    const sourceFile = files[0]?.originFileObj;
    if (!sourceFile) {
      throw new Error('CSV 파일이 없습니다.');
    }

    const fd = new FormData();
    fd.append('environment', environment);
    fd.append('maxParallel', String(clampNumber(maxParallel, 3)));
    if (contextJson.trim()) fd.append('contextJson', contextJson.trim());
    if (targetAssistant.trim()) fd.append('targetAssistant', targetAssistant.trim());
    fd.append('file', sourceFile);

    const resp = await api.post('/generic-runs', fd);
    const created = resp.data as { runId: string; status: GenericRunMeta['status']; rows: number };
    const totalRows = Number(created.rows) || uploadSummary?.rowCount || 0;

    setRun({
      runId: created.runId,
      status: created.status,
      totalRows,
      doneRows: 0,
      errorRows: 0,
      llmDoneRows: 0,
    });

    return created.runId;
  };

  const createRunFromSingle = async (): Promise<string> => {
    const resp = await api.post('/generic-runs/direct', {
      environment,
      query: singleQuery.trim(),
      llmCriteria: singleLlmCriteria.trim(),
      fieldPath: singleField.trim(),
      expectedValue: singleExpected.trim(),
      maxParallel: clampNumber(maxParallel, 3),
      contextJson: contextJson.trim() || undefined,
      targetAssistant: targetAssistant.trim() || undefined,
      bearer: tokens.bearer,
      cms: tokens.cms,
      mrs: tokens.mrs,
    });

    setRun({
      runId: resp.data.runId,
      status: 'RUNNING',
      totalRows: 1,
      doneRows: 0,
      errorRows: 0,
      llmDoneRows: 0,
    });

    return resp.data.runId;
  };

  const runEvaluation = async (targetRunId: string) => {
    if (!targetRunId) return;
    setAction('evaluating');
    try {
      await api.post(`/generic-runs/${targetRunId}/evaluate`, {
        openaiKey: openaiKey.trim() || undefined,
        openaiModel: openaiModel || DEFAULT_OPENAI_MODEL,
        maxChars: clampNumber(maxChars, 15000),
        maxParallel: clampNumber(maxParallel, 3),
      });
      await loadRunRows();
      setAction('idle');
      setShouldEvaluate(false);
    } catch (error) {
      setAction('idle');
      setShouldEvaluate(false);
      console.error(error);
      message.error(`LLM 평가 실행에 실패했습니다. ${getRequestErrorMessage(error, '요청이 실패했습니다.')}`);
    }
  };

  const startRun = async () => {
    if (!canStartRun) {
      if (!hasTokens) {
        message.warning('실행/평가 토큰이 필요합니다.');
      }
      return;
    }

    setRows([]);
    setResultCurrentPage(1);
    setPollError('');
    setLastProgressChangeAt(Date.now());
    setAction('creating');
    setShouldEvaluate(false);

    try {
      const nextRunId = inputMode === 'upload' ? await createRunFromCsv() : await createRunFromSingle();
      if (inputMode === 'upload') {
        await api.post(`/generic-runs/${nextRunId}/execute`, {
          bearer: tokens.bearer,
          cms: tokens.cms,
          mrs: tokens.mrs,
        });
      }

      await updateRunAndRows(nextRunId);
      setShouldEvaluate(true);
      setAction('executing');
      message.success('검증 실행을 시작했습니다.');
    } catch (error) {
      setAction('idle');
      console.error(error);
      message.error(`실행 시작에 실패했습니다. ${getRequestErrorMessage(error, '요청이 실패했습니다.')}`);
    }
  };

  const stopRun = () => {
    message.info('현재 백엔드에 중지 API가 없어 즉시 중단할 수 없습니다. 현재 요청은 백엔드 완료까지 계속 진행됩니다.');
  };

  const retryRun = () => {
    if (!canRunInput) {
      message.warning('재실행하려면 입력을 먼저 준비해 주세요.');
      return;
    }
    void startRun();
  };

  const handleRowSelect = (row: DisplayRowItem) => {
    setSelectedRow(row);
    setDrawerOpen(true);
  };

  const resultColumns = useMemo<ColumnsType<DisplayRowItem>>(() => {
    return [
      {
        key: 'ordinal',
        title: 'No',
        dataIndex: 'ordinal',
        width: RESULT_INITIAL_COLUMN_WIDTHS.ordinal,
        render: (_value, _row, index) => _row.ordinal ?? index + 1,
      },
      {
        key: 'query',
        title: '질의',
        dataIndex: 'query',
        width: RESULT_INITIAL_COLUMN_WIDTHS.query,
        ellipsis: true,
        render: (value: string | null) => (
          <Tooltip title={value ?? '-'}>
            <Typography.Text ellipsis={{ tooltip: value ?? '-' }}>{value ?? '-'}</Typography.Text>
          </Tooltip>
        ),
      },
      {
        key: 'status',
        title: '상태',
        width: RESULT_INITIAL_COLUMN_WIDTHS.status,
        render: (_: unknown, row) => rowStatusTag(row),
      },
      {
        key: 'message',
        title: '메시지',
        dataIndex: 'error',
        width: RESULT_INITIAL_COLUMN_WIDTHS.message,
        ellipsis: true,
        render: (_: unknown, row) => (
          <Tooltip title={rowShortMessage(row)}>
            <Typography.Text type="secondary" ellipsis={{ tooltip: rowShortMessage(row) }}>
              {rowShortMessage(row)}
            </Typography.Text>
          </Tooltip>
        ),
      },
    ];
  }, []);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }} className="run-page-stack">
      <Affix offsetTop={56}>
        <Card className="backoffice-content-card sticky-inline-action">
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            <Space wrap size={10} align="center" className="status-row">
              <Typography.Text strong>에이전트 검증</Typography.Text>
              <Tag color={statusColor(runStateLabel)}>{runStateLabel}</Tag>
              <Typography.Text className="run-meta">Run ID: {runId || '-'}</Typography.Text>
              <Typography.Text className="run-meta">{pipelineText}</Typography.Text>
              {isStale ? <Tag color="warning">지연</Tag> : null}
            </Space>

            <Space wrap direction="horizontal" size={16} align="center" className="status-row">
              <Typography.Text className="run-meta">진행: {progressDone + progressError} / {progressTotal}</Typography.Text>
              <Typography.Text className="run-meta">({summary.done} 완료 / {summary.failed} 실패)</Typography.Text>
              <Typography.Text className="run-meta">마지막 갱신: {lastUpdateAt ? formatLocaleTime(lastUpdateAt) : '-'}</Typography.Text>
            </Space>

            <Progress percent={progressPercent} status={runStateLabel === '실패' ? 'exception' : 'active'} size="small" />

            {pollError ? <Alert type="error" showIcon message="결과 조회 에러" description={pollError} /> : null}
            {isStale ? <Alert type="warning" showIcon message={staleText} description="결과 수신이 지연되고 있습니다. 마지막 업데이트를 기준으로 진행 상태를 점검합니다." /> : null}
            {failureSummary ? (
              <Alert
                type="error"
                showIcon
                message={`실패 구간: ${failureSummary.stage}`}
                description={
                  <div>
                    <div>원인: {failureSummary.reason}</div>
                    <div>안내: {failureSummary.retryHint}</div>
                  </div>
                }
              />
            ) : null}

            <Space wrap size={8}>
              <Button danger loading={isBusy && action !== 'evaluating'} onClick={stopRun} disabled={!isBusy}>
                중지
              </Button>
              <Button onClick={retryRun} loading={isBusy} disabled={!canRunInput} icon={<ReloadOutlined />}>
                재실행
              </Button>
              <Button
                href={runId ? `${api.defaults.baseURL}/generic-runs/${runId}/export.xlsx` : undefined}
                disabled={!runId || summary.total === 0}
                icon={<FileExcelOutlined />}
              >
                결과 다운로드
              </Button>
            </Space>
          </Space>
        </Card>
      </Affix>

      <Card className="backoffice-content-card">
        <Steps
          size="small"
          current={step}
          items={[
            { title: '1. 입력 준비' },
            { title: '2. 실행 / 결과' },
          ]}
        />
      </Card>

      {step === 0 ? (
        <Card title="입력 준비" className="backoffice-content-card">
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Segmented
              value={inputMode}
              onChange={(value) => setInputMode(value as InputMode)}
              options={[
                { label: 'CSV 업로드', value: 'upload' },
                { label: '단일 질의', value: 'single' },
              ]}
            />

            {inputMode === 'upload' ? (
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <Card size="small" title="CSV 업로드" className="backoffice-content-card">
                  <Space direction="vertical" style={{ width: '100%' }} size={12}>
                    <Button type="default" icon={<CloudUploadOutlined />} onClick={handleTemplateDownload}>
                      템플릿 다운로드
                    </Button>
                    <Upload.Dragger
                      beforeUpload={() => false}
                      fileList={files}
                      onChange={handleCsvChange}
                      maxCount={1}
                      accept=".csv,text/csv"
                    >
                      <p className="ant-upload-drag-icon">
                        <CloudUploadOutlined />
                      </p>
                      <p className="ant-upload-text">CSV 파일을 드래그하거나 클릭해 업로드</p>
                    </Upload.Dragger>
                  </Space>
                </Card>

                {isCsvAnalyzing ? (
                  <Alert
                    message="CSV 유효성 검사 중"
                    icon={<LoadingOutlined />}
                    type="info"
                    description="행 수와 필수 컬럼을 분석하고 있습니다."
                  />
                ) : null}

                {uploadSummary ? (
                  <Alert
                    type={uploadSummary.isValid ? 'success' : 'error'}
                    message={`CSV 검증: ${uploadSummary.fileName}`}
                    showIcon
                    description={
                      <div>
                        <div>데이터 행: {uploadSummary.rowCount}건</div>
                        <div>필수 컬럼 누락: {uploadSummary.missingColumns.join(', ') || '없음'}</div>
                        <div>빈 질의 행: {uploadSummary.emptyRows}건</div>
                        <div>질의 누락 행: {uploadSummary.invalidRows}건</div>
                      </div>
                    }
                  />
                ) : null}
              </Space>
            ) : (
              <Card size="small" title="단일 질의" className="backoffice-content-card">
                <Space direction="vertical" style={{ width: '100%' }} size={12}>
                  <Input.TextArea
                    value={singleQuery}
                    onChange={(event) => setSingleQuery(event.target.value)}
                    placeholder="에이전트에 질의할 문장을 입력하세요."
                    autoSize={{ minRows: 10, maxRows: 12 }}
                    style={{ minHeight: 220 }}
                  />
                  <Input
                    value={singleLlmCriteria}
                    onChange={(event) => setSingleLlmCriteria(event.target.value)}
                    placeholder="LLM 평가 기준(선택)"
                  />
                  <Row gutter={12}>
                    <Col span={12}>
                      <Input
                        value={singleField}
                        onChange={(event) => setSingleField(event.target.value)}
                        placeholder="검증 필드 키 (선택)"
                      />
                    </Col>
                    <Col span={12}>
                      <Input
                        value={singleExpected}
                        onChange={(event) => setSingleExpected(event.target.value)}
                        placeholder="기대값 (선택)"
                      />
                    </Col>
                  </Row>
                </Space>
              </Card>
            )}

            <Space>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={() => setStep(1)}
                disabled={!canRunInput}
              >
                다음: 실행
              </Button>
              {!run ? null : (
                <Button
                  onClick={() => {
                    setStep(1);
                  }}
                >
                  결과 화면으로 이동
                </Button>
              )}
            </Space>
          </Space>
        </Card>
      ) : (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Card title="실행 설정" className="backoffice-content-card">
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Typography.Text className="run-card-help">
                실행은 동시 실행 수/대상 에이전트로 제어하고, OpenAI 모델/Key/맥스 글자는 결과 평가 단계에서만 사용됩니다.
              </Typography.Text>
              <Row gutter={12} align="middle">
                <Col xs={24} md={12}>
                  <Input
                    value={openaiModel}
                    onChange={(event) => setOpenaiModel(event.target.value)}
                    placeholder="OpenAI 모델(평가 단계 전용, 기본값: gpt-5.2)"
                  />
                </Col>
                <Col xs={24} md={12}>
                  <InputNumber
                    min={1}
                    value={maxParallel}
                    onChange={(next) => setMaxParallel(clampNumber(next, 3))}
                    style={{ width: '100%' }}
                    placeholder="동시 실행 수"
                  />
                </Col>
              </Row>

              <Collapse
                defaultActiveKey={[]}
                items={[
                  {
                    key: 'advanced',
                    label: '고급 옵션(옵션 토글)',
                    children: (
                      <Space direction="vertical" size={12} style={{ width: '100%' }}>
                        <Input.Password
                          value={openaiKey}
                          onChange={(event) => setOpenaiKey(event.target.value)}
                          placeholder="OpenAI Key(선택: 미입력 시 SKIPPED)"
                        />
                        <Input.TextArea
                          autoSize={{ minRows: 3 }}
                          value={contextJson}
                          onChange={(event) => setContextJson(event.target.value)}
                          placeholder='컨텍스트 JSON(선택): {"recruitPlanId": 123}'
                        />
                        <Input
                          value={targetAssistant}
                          onChange={(event) => setTargetAssistant(event.target.value)}
                          placeholder="대상 에이전트(선택)"
                        />
                        <InputNumber
                          min={1000}
                          step={500}
                          value={maxChars}
                          onChange={(next) => setMaxChars(clampNumber(next, 15000))}
                          style={{ width: '100%' }}
                        />
                      </Space>
                    ),
                  },
                ]}
              />

              <Space wrap>
                <Button
                  type="primary"
                  loading={isBusy}
                  onClick={startRun}
                  disabled={!canRunInput || !hasTokens || isBusy}
                >
                  검증 실행
                </Button>
                <Button
                  onClick={() => setStep(0)}
                  disabled={isBusy}
                >
                  이전: 입력
                </Button>
                {action === 'evaluating' ? <Spin indicator={<LoadingOutlined />} /> : null}
                {failureSummary ? <ClockCircleOutlined /> : null}
              </Space>
            </Space>
          </Card>

          <Card title="결과" className="backoffice-content-card">
            <MetricsBar
              total={summary.total}
              passFail={`${summary.success} / ${summary.failed}`}
              llmDone={summary.llmDone}
              errors={summary.errors}
            />

            <div style={{ marginTop: 16 }}>
              <Typography.Text className="run-meta">
                총 {summary.total}건 / 완료 {summary.done}건 / 실패 {summary.failed}건 / 진행 {summary.inProgress}건
              </Typography.Text>
            </div>

            {rows.length === 0 ? (
              <Card className="backoffice-empty-state">
                <Empty description="아직 조회할 결과가 없습니다. 실행 후 결과가 쌓이면 리스트가 표시됩니다." />
              </Card>
            ) : (
              <StandardDataTable<DisplayRowItem>
                tableId="generic-results"
                initialColumnWidths={RESULT_INITIAL_COLUMN_WIDTHS}
                minColumnWidth={90}
                wrapperClassName="generic-results-table-wrap"
                rowKey="id"
                size="middle"
                className="run-table query-management-table generic-results-table"
                tableLayout="fixed"
                dataSource={rows}
                columns={resultColumns}
                pagination={{
                  current: resultCurrentPage,
                  pageSize: resultPageSize,
                  total: rows.length,
                  onChange: (page, nextPageSize) => {
                    if (nextPageSize !== resultPageSize) {
                      setResultPageSize(nextPageSize);
                      setResultCurrentPage(1);
                      return;
                    }
                    setResultCurrentPage(page);
                  },
                }}
                scroll={{ y: 420 }}
                onRow={(row) => ({ onClick: () => handleRowSelect(row) })}
                rowClassName=""
                title={() => '결과 리스트(항목 클릭 시 상세)'}
                locale={{ emptyText: '실행 결과를 불러오지 못했습니다.' }}
              />
            )}
          </Card>
        </Space>
      )}

      <Drawer
        title={`결과 상세${selectedRow?.ordinal ? ` (No. ${selectedRow.ordinal})` : ''}`}
        open={drawerOpen}
        placement="right"
        width={640}
        onClose={() => setDrawerOpen(false)}
      >
        {selectedRow ? (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Card size="small">
              <Typography.Title level={5}>원문 질의</Typography.Title>
              <Typography.Paragraph>{selectedRow.query || '-'}</Typography.Paragraph>
            </Card>

            <Card size="small">
              <Typography.Title level={5}>실행/평가 결과</Typography.Title>
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <div>상태: {rowStatusTag(selectedRow)}</div>
                <div>LLM 평가 기준: {selectedRow.llmCriteria || '-'}</div>
                <div>검증 필드: {selectedRow.fieldPath || '-'}</div>
                <div>기대값: {selectedRow.expectedValue || '-'}</div>
                <div>로직 결과: {selectedRow.logicResult || '-'}</div>
                <div>LLM 상태: {selectedRow.llmEvalStatus || '-'}</div>
                <div>응답 시간: {selectedRow.responseTimeSec ? `${selectedRow.responseTimeSec.toFixed(3)}초` : '-'}</div>
                <div>실행 시작: {formatTimeLabel(run?.startedAt)}</div>
                <div>실행 종료: {formatTimeLabel(run?.finishedAt)}</div>
              </Space>
            </Card>

            {selectedRow.responseText ? (
              <Card size="small">
                <Typography.Title level={5}>응답</Typography.Title>
                <Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>{selectedRow.responseText}</Typography.Paragraph>
              </Card>
            ) : null}

            {selectedRow.executionProcess ? (
              <Card size="small">
                <Typography.Title level={5}>실행 프로세스</Typography.Title>
                <Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>{selectedRow.executionProcess}</Typography.Paragraph>
              </Card>
            ) : null}

            {selectedRow.error ? (
              <Card size="small">
                <Typography.Title level={5}>에러 로그</Typography.Title>
                <Typography.Paragraph type="danger" style={{ whiteSpace: 'pre-wrap' }}>
                  {selectedRow.error}
                </Typography.Paragraph>
              </Card>
            ) : null}

            {selectedRow.rawJson ? (
              <Card size="small">
                <Typography.Title level={5}>raw_json</Typography.Title>
                <Typography.Paragraph copyable style={{ whiteSpace: 'pre-wrap' }}>
                  {tryPrettyJson(selectedRow.rawJson)}
                </Typography.Paragraph>
              </Card>
            ) : null}

            {selectedRow.llmEvalJson ? (
              <Card size="small">
                <Typography.Title level={5}>LLM 평가 결과</Typography.Title>
                <Typography.Paragraph copyable style={{ whiteSpace: 'pre-wrap' }}>
                  {tryPrettyJson(selectedRow.llmEvalJson)}
                </Typography.Paragraph>
              </Card>
            ) : null}
          </Space>
        ) : null}
      </Drawer>
    </Space>
  );
}
