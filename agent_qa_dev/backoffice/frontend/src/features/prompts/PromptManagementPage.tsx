import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Modal,
  Input,
  App,
  Space,
  Tag,
  Typography,
} from 'antd';
import { CopyOutlined } from '@ant-design/icons';
import { DiffEditor } from '@monaco-editor/react';

import { api } from '../../api/client';
import { RuntimeSecrets } from '../../app/types';
import type { Environment } from '../../app/EnvironmentScope';
import { StandardDataTable } from '../../components/common/StandardDataTable';
import { StandardModal, StandardModalMetaBlock } from '../../components/common/StandardModal';
import { calculateLineDiff, getLengthDelta } from './utils/promptDiff';
import { normalizePromptSnapshot, normalizePromptText, type PromptSnapshotData } from './utils/promptSnapshot';

type Worker = {
  workerType: string;
  description: string;
};

type WorkerPromptData = PromptSnapshotData;

type ModalMode = 'view' | 'edit';

const MODAL_TITLES: Record<ModalMode, string> = {
  view: '프롬프트 조회',
  edit: '프롬프트 수정',
};

const MODAL_WIDTH: Record<ModalMode, string> = {
  view: 'min(1200px, 90vw)',
  edit: 'min(1200px, 90vw)',
};

const DIFF_EDITOR_OPTIONS = {
  renderSideBySide: true,
  useInlineViewWhenSpaceIsLimited: false,
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  fontSize: 13,
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
  automaticLayout: true,
  unusualLineTerminators: 'off' as const,
};

function getApiHeaders(tokens: RuntimeSecrets) {
  return {
    headers: {
      bearer: tokens.bearer,
      cms: tokens.cms,
      mrs: tokens.mrs,
    },
  };
}

export function buildWorkerLabel(worker: Worker): string {
  return `${worker.workerType} - ${worker.description}`;
}

function createPromptTableColumns(
  onView: (workerType: string) => void,
  onEdit: (workerType: string) => void,
  onReset: (workerType: string) => void,
) {
  return [
    { key: 'workerType', title: '워커', dataIndex: 'workerType', width: 260, ellipsis: true },
    { key: 'description', title: '설명', dataIndex: 'description', width: 440, ellipsis: true },
    {
      key: 'actions',
      title: '작업',
      dataIndex: 'actions',
      width: 280,
      render: (_: unknown, row: Worker) => (
        <Space size="small">
          <Button onClick={() => onView(row.workerType)}>
            조회
          </Button>
          <Button type="primary" onClick={() => onEdit(row.workerType)}>
            수정
          </Button>
          <Button onClick={() => onReset(row.workerType)}>
            초기화
          </Button>
        </Space>
      ),
    },
  ];
}

export function PromptManagementPage({ environment, tokens }: { environment: Environment; tokens: RuntimeSecrets }) {
  const { message } = App.useApp();
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [activeModal, setActiveModal] = useState<ModalMode | null>(null);
  const [selectedWorker, setSelectedWorker] = useState('');
  const [promptData, setPromptData] = useState<WorkerPromptData>({
    before: '',
    after: '',
    currentPrompt: '',
    previousPrompt: '',
  });
  const [draft, setDraft] = useState('');
  const [search, setSearch] = useState('');
  const [isFetchingList, setIsFetchingList] = useState(false);
  const [isPromptSaving, setIsPromptSaving] = useState(false);
  const [editorSessionKey, setEditorSessionKey] = useState(0);
  const closeModeRef = useRef<ModalMode | null>(null);
  const activeModalRef = useRef<ModalMode | null>(null);
  const diffModifiedChangeRef = useRef<{ dispose: () => void } | null>(null);
  const viewDiffEditorRef = useRef<{ layout: () => void } | null>(null);
  const viewDiffWrapperRef = useRef<HTMLDivElement | null>(null);
  const diffEditorRef = useRef<{
    layout: () => void;
    getOriginalEditor?: () => { updateOptions: (options: Record<string, unknown>) => void; getDomNode?: () => HTMLElement | null };
    getModifiedEditor?: () => { updateOptions: (options: Record<string, unknown>) => void };
  } | null>(null);
  const diffWrapperRef = useRef<HTMLDivElement | null>(null);

  const hasTokens = Boolean(tokens.bearer && tokens.cms && tokens.mrs);
  const hasUnsavedChanges = useMemo(
    () => normalizePromptText(draft) !== normalizePromptText(promptData.currentPrompt),
    [draft, promptData.currentPrompt],
  );
  const viewDiffSummary = useMemo(
    () => calculateLineDiff(promptData.previousPrompt, promptData.currentPrompt),
    [promptData.previousPrompt, promptData.currentPrompt],
  );
  const diffSummary = useMemo(
    () => calculateLineDiff(promptData.currentPrompt, draft),
    [promptData.currentPrompt, draft],
  );

  const loadWorkers = async () => {
    setIsFetchingList(true);
    try {
      const r = await api.get('/prompts/workers', getApiHeaders(tokens));
      const list = r.data.workers || [];
      setWorkers(list);
    } catch (e) {
      message.error('프롬프트 worker 목록 조회에 실패했습니다.');
      console.error(e);
      setWorkers([]);
    } finally {
      setIsFetchingList(false);
    }
  };

  useEffect(() => {
    if (!hasTokens) {
      setWorkers([]);
      return;
    }
    void loadWorkers();
  }, [hasTokens, tokens.bearer, tokens.cms, tokens.mrs]);

  const selectedWorkerLabel = useMemo(
    () => workers.find((w) => w.workerType === selectedWorker)?.description || '',
    [selectedWorker, workers],
  );

  const diffModelPaths = useMemo(
    () => ({
      originalModelPath: `inmemory://prompt/${environment}/${encodeURIComponent(selectedWorker || 'unspecified')}/original/${editorSessionKey}`,
      modifiedModelPath: `inmemory://prompt/${environment}/${encodeURIComponent(selectedWorker || 'unspecified')}/modified/${editorSessionKey}`,
    }),
    [environment, selectedWorker, editorSessionKey],
  );

  const fetchPromptSnapshot = async (workerType: string) => {
    const response = await api.get(`/prompts/${environment}/${workerType}`, getApiHeaders(tokens));
    return normalizePromptSnapshot(response.data);
  };

  const openPromptModal = async (workerType: string, nextMode: ModalMode = 'view') => {
    if (!hasTokens) {
      message.warning('토큰이 없어 프롬프트 조회가 불가합니다.');
      return;
    }
    setSelectedWorker(workerType);
    try {
      const nextData = await fetchPromptSnapshot(workerType);
      const nextDraft = nextData.currentPrompt;
      setPromptData(nextData);
      setDraft(nextMode === 'edit' ? nextDraft : nextData.currentPrompt);
      setEditorSessionKey((prev) => prev + 1);
      setActiveModal(nextMode);
    } catch (e) {
      message.error('프롬프트 조회에 실패했습니다.');
      console.error(e);
    }
  };

  const updatePrompt = async () => {
    if (!selectedWorker) return;
    const normalizedDraft = normalizePromptText(draft);
    const normalizedCurrentPrompt = normalizePromptText(promptData.currentPrompt);
    if (normalizedDraft === normalizedCurrentPrompt) {
      message.warning('프롬프트 수정사항이 없어요.');
      return;
    }
    setIsPromptSaving(true);
    try {
      const response = await api.put(
        `/prompts/${environment}/${selectedWorker}`,
        { prompt: normalizedDraft },
        getApiHeaders(tokens),
      );
      const nextData = normalizePromptSnapshot(response.data);
      let syncedData = nextData;
      try {
        syncedData = await fetchPromptSnapshot(selectedWorker);
      } catch (verifyError) {
        console.error(verifyError);
      }

      if (syncedData.currentPrompt === normalizedDraft) {
        message.success('프롬프트가 수정되었습니다.');
      } else {
        message.warning('저장 후 다시 조회된 프롬프트가 입력값과 달라 확인이 필요합니다.');
      }

      await loadWorkers();
      closeModeRef.current = 'edit';
      disposeDiffEditorListeners();
      setActiveModal(null);
    } catch (e) {
      message.error('프롬프트 저장에 실패했습니다.');
      console.error(e);
    } finally {
      setIsPromptSaving(false);
    }
  };

  const resetPrompt = async (workerType: string) => {
    if (!hasTokens) {
      message.warning('토큰이 없어 프롬프트 초기화가 불가합니다.');
      return;
    }
    setIsPromptSaving(true);
    try {
      const response = await api.put(`/prompts/${environment}/${workerType}/reset`, {}, getApiHeaders(tokens));
      const nextData = normalizePromptSnapshot(response.data);
      setPromptData(nextData);
      setDraft(nextData.currentPrompt);
      setSelectedWorker(workerType);
      setActiveModal('view');
      message.success('프롬프트가 초기화되었습니다.');
      await loadWorkers();
    } catch (e) {
      message.error('프롬프트 초기화에 실패했습니다.');
      console.error(e);
    } finally {
      setIsPromptSaving(false);
    }
  };

  const clearModalState = () => {
    disposeDiffEditorListeners();
    viewDiffEditorRef.current = null;
    setActiveModal(null);
    setSelectedWorker('');
    setPromptData({
      before: '',
      after: '',
      currentPrompt: '',
      previousPrompt: '',
    });
    setDraft('');
  };

  const closeModalStateIfNeeded = (mode: ModalMode) => {
    if (closeModeRef.current !== mode) return;

    closeModeRef.current = null;
    clearModalState();
  };

  const requestCloseViewModal = () => {
    closeModeRef.current = 'view';
    setActiveModal(null);
  };

  const requestCloseEditModal = () => {
    if (!hasUnsavedChanges) {
      closeModeRef.current = 'edit';
      setActiveModal(null);
      return;
    }

    Modal.confirm({
      title: '변경사항이 저장되지 않았습니다',
      content: '편집 중인 TO-BE 내용이 있습니다. 닫으면 변경사항이 사라집니다.',
      okText: '변경사항 버리기',
      cancelText: '계속 편집',
      okType: 'danger',
      onOk: () => {
        closeModeRef.current = 'edit';
        setActiveModal(null);
      },
    });
  };

  const disposeDiffEditorListeners = useCallback(() => {
    if (diffModifiedChangeRef.current) {
      diffModifiedChangeRef.current.dispose();
      diffModifiedChangeRef.current = null;
    }
    diffEditorRef.current = null;
  }, []);

  const layoutDiffEditor = useCallback(() => {
    requestAnimationFrame(() => {
      const editor = diffEditorRef.current;
      if (!editor) return;
      editor.layout();
    });
  }, []);

  const layoutViewDiffEditor = useCallback(() => {
    requestAnimationFrame(() => {
      const editor = viewDiffEditorRef.current;
      if (!editor) return;
      editor.layout();
    });
  }, []);

  const fallbackCopyText = (text: string) => {
    if (typeof document === 'undefined') return false;
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.top = '-9999px';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    const copied = document.execCommand('copy');
    document.body.removeChild(textarea);
    return copied;
  };

  const copyTextToClipboard = async (label: string, text: string, successMessage?: string) => {
    try {
      const clipboard = typeof navigator !== 'undefined' ? navigator.clipboard : undefined;
      if (clipboard?.writeText) {
        try {
          await clipboard.writeText(text);
        } catch (clipboardError) {
          const copied = fallbackCopyText(text);
          if (!copied) {
            throw clipboardError;
          }
        }
      } else {
        const copied = fallbackCopyText(text);
        if (!copied) {
          throw new Error('Clipboard API is unavailable');
        }
      }
      message.success(successMessage ?? `${label}을(를) 클립보드에 복사했습니다.`);
    } catch (e) {
      message.error(`${label} 복사에 실패했습니다.`);
      console.error(e);
    }
  };

  useEffect(() => {
    if (activeModal !== 'edit') {
      return;
    }

    const wrapper = diffWrapperRef.current;
    if (!wrapper) return;

    const resizeObserver = new ResizeObserver(() => {
      layoutDiffEditor();
    });
    resizeObserver.observe(wrapper);

    return () => {
      resizeObserver.disconnect();
    };
  }, [activeModal, layoutDiffEditor]);

  useEffect(() => {
    if (activeModal !== 'view') {
      return;
    }

    const wrapper = viewDiffWrapperRef.current;
    if (!wrapper) return;

    const resizeObserver = new ResizeObserver(() => {
      layoutViewDiffEditor();
    });
    resizeObserver.observe(wrapper);

    return () => {
      resizeObserver.disconnect();
    };
  }, [activeModal, layoutViewDiffEditor]);

  useEffect(() => {
    activeModalRef.current = activeModal;
  }, [activeModal]);

  useEffect(() => {
    if (activeModal === 'edit') {
      return;
    }

    disposeDiffEditorListeners();
  }, [activeModal, disposeDiffEditorListeners]);

  useEffect(() => {
    if (activeModal === 'view') {
      return;
    }

    viewDiffEditorRef.current = null;
  }, [activeModal]);


  const filteredWorkers = useMemo(
    () =>
      workers.filter(
        (worker) =>
          worker.workerType.toLowerCase().includes(search.toLowerCase()) ||
          worker.description.toLowerCase().includes(search.toLowerCase()),
      ),
    [workers, search],
  );

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={16}>
      {!hasTokens ? (
      <Alert
      type="warning"
      showIcon
      message="GNB의 로그인을 통해 Bearer/CMS/MRS를 먼저 입력해 주세요."
      />
      ) : null}
      <Card className="backoffice-content-card">
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Alert
            message="메뉴에서 선택한 워커의 최신 프롬프트를 조회하고 즉시 수정/초기화할 수 있습니다."
            type="info"
            showIcon
          />
          <Input.Search
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            allowClear
            placeholder="워커 혹은 워커 설명으로 검색해 주세요."
          />
        </Space>
      </Card>

      <StandardDataTable
        tableId="prompt-workers"
        initialColumnWidths={{ workerType: 260, description: 440, actions: 280 }}
        minColumnWidth={120}
        className="prompt-table"
        size="small"
        rowKey="workerType"
        dataSource={filteredWorkers}
        loading={isFetchingList}
        columns={createPromptTableColumns(
          (workerType) => void openPromptModal(workerType, 'view'),
          (workerType) => void openPromptModal(workerType, 'edit'),
          (workerType) => void resetPrompt(workerType),
        )}
        bordered
        rowClassName="prompt-table-row"
        onRow={(row) => ({
          onDoubleClick: () => {
            void openPromptModal(row.workerType, 'view');
          },
        })}
      />

      <StandardModal
        title={MODAL_TITLES.view}
        open={activeModal === 'view'}
        width={MODAL_WIDTH.view}
        onCancel={requestCloseViewModal}
        bodyPadding={0}
        afterClose={() => closeModalStateIfNeeded('view')}
        footer={
          <Space>
            <Button onClick={requestCloseViewModal}>닫기</Button>
          </Space>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', width: '100%', height: '100%', minHeight: 0 }}>
          <StandardModalMetaBlock padding={0} gap={8} marginBottom={12}>
            <div style={{ color: 'var(--ant-color-text-secondary)' }}>
              선택된 프롬프트: {selectedWorker}
              {selectedWorkerLabel ? ` (${selectedWorkerLabel})` : ''}
            </div>
          </StandardModalMetaBlock>
          <div style={{ display: 'flex', flexDirection: 'column', width: '100%', height: '520px', minHeight: 0, gap: 8 }}>
            <div style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <Space size={8}>
                <Tag color="blue">길이 차이: {getLengthDelta(promptData.previousPrompt, promptData.currentPrompt)}</Tag>
                <Tag color="success">+Added {viewDiffSummary.added}</Tag>
                <Tag color="error">-Removed {viewDiffSummary.removed}</Tag>
                <Tag color="warning">~Modified {viewDiffSummary.modified}</Tag>
              </Space>
              <Space size={8} wrap>
                <Button
                  icon={<CopyOutlined />}
                  disabled={!promptData.previousPrompt}
                  onClick={() => copyTextToClipboard('직전 프롬프트', promptData.previousPrompt, '클립보드로 복사됐어요.')}
                >
                  Copy 직전
                </Button>
                <Button
                  icon={<CopyOutlined />}
                  onClick={() => copyTextToClipboard('현재 프롬프트', promptData.currentPrompt, '클립보드로 복사됐어요.')}
                >
                  Copy 현재
                </Button>
                <Button
                  icon={<CopyOutlined />}
                  onClick={() => copyTextToClipboard('DIFF', viewDiffSummary.diffText, '클립보드로 복사됐어요.')}
                >
                  Copy DIFF
                </Button>
              </Space>
            </div>
            <div style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <Typography.Text strong>직전 프롬프트</Typography.Text>
              <Typography.Text strong>현재 프롬프트</Typography.Text>
            </div>
            {!promptData.previousPrompt ? (
              <Typography.Text type="secondary">직전 프롬프트가 없습니다.</Typography.Text>
            ) : null}
            <div
              ref={viewDiffWrapperRef}
              style={{ width: '100%', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}
            >
              <DiffEditor
                key={`prompt-view-diff-${environment}-${selectedWorker || 'unspecified'}-${editorSessionKey}`}
                language="markdown"
                original={promptData.previousPrompt}
                modified={promptData.currentPrompt}
                keepCurrentOriginalModel={true}
                keepCurrentModifiedModel={true}
                originalModelPath={`inmemory://prompt/${environment}/${encodeURIComponent(selectedWorker || 'unspecified')}/view-original/${editorSessionKey}`}
                modifiedModelPath={`inmemory://prompt/${environment}/${encodeURIComponent(selectedWorker || 'unspecified')}/view-modified/${editorSessionKey}`}
                onMount={(editor) => {
                  viewDiffEditorRef.current = editor;
                  const originalEditor = editor.getOriginalEditor?.();
                  const modifiedEditor = editor.getModifiedEditor?.();
                  originalEditor?.updateOptions({
                    readOnly: true,
                    renderLineHighlight: 'none',
                  });
                  modifiedEditor?.updateOptions({
                    readOnly: true,
                    renderLineHighlight: 'none',
                  });
                  originalEditor?.getDomNode()?.classList.add('prompt-monaco-readonly');
                  modifiedEditor?.getDomNode()?.classList.add('prompt-monaco-readonly');
                  layoutViewDiffEditor();
                }}
                options={DIFF_EDITOR_OPTIONS}
                height="100%"
                theme="light"
              />
            </div>
          </div>
        </div>
      </StandardModal>

      <StandardModal
        title={MODAL_TITLES.edit}
        open={activeModal === 'edit'}
        width={MODAL_WIDTH.edit}
        onCancel={requestCloseEditModal}
        afterOpenChange={(open) => {
          if (open) {
            requestAnimationFrame(layoutDiffEditor);
          }
        }}
        destroyOnHidden={true}
        afterClose={() => closeModalStateIfNeeded('edit')}
        footer={
          <Space>
            <Button onClick={requestCloseEditModal}>취소</Button>
            <Button type="primary" loading={isPromptSaving} onClick={updatePrompt}>
              저장
            </Button>
          </Space>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', width: '100%', height: '520px', minHeight: 0, gap: 12 }}>
          <StandardModalMetaBlock padding={0} gap={8} marginBottom={12}>
            <div style={{ color: 'var(--ant-color-text-secondary)' }}>
              선택된 프롬프트: {selectedWorker} {selectedWorkerLabel ? ` (${selectedWorkerLabel})` : ''} <br/>
              프롬프트 수정 후, 우측 하단의 '저장' 버튼을 눌러 변경사항을 저장하세요.
            </div>
          </StandardModalMetaBlock>
          <Space direction="vertical" style={{ width: '100%' }} size={6}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <Typography.Text strong>AS-IS</Typography.Text>
              <Typography.Text strong>
                TO-BE
              </Typography.Text>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <Space size={8}>
                <Tag color="blue">길이 차이: {getLengthDelta(promptData.currentPrompt, draft)}</Tag>
                <Tag color="success">+Added {diffSummary.added}</Tag>
                <Tag color="error">-Removed {diffSummary.removed}</Tag>
                <Tag color="warning">~Modified {diffSummary.modified}</Tag>
              </Space>
              <Space size={8} wrap>
                <Button icon={<CopyOutlined />} onClick={() => copyTextToClipboard('AS-IS', promptData.currentPrompt)}>
                  Copy AS-IS
                </Button>
                <Button icon={<CopyOutlined />} onClick={() => copyTextToClipboard('TO-BE', draft)}>
                  Copy TO-BE
                </Button>
                <Button icon={<CopyOutlined />} onClick={() => copyTextToClipboard('DIFF', diffSummary.diffText)}>
                  Copy DIFF
                </Button>
                <Button
                  danger
                  onClick={() => {
                    Modal.confirm({
                      title: 'TO-BE를 AS-IS로 되돌리기',
                      content: '현재 TO-BE 편집 내용을 AS-IS 내용으로 초기화합니다.',
                      okText: '초기화',
                      cancelText: '취소',
                      okType: 'danger',
                      onOk: () => setDraft(promptData.currentPrompt),
                    });
                  }}
                >
                  Reset TO-BE to AS-IS
                </Button>
              </Space>
            </div>
          </Space>
            <div
              ref={diffWrapperRef}
              style={{ flex: 1, minHeight: 0, height: '100%', display: 'flex', flexDirection: 'column' }}
            >
              <DiffEditor
                key={`prompt-diff-${environment}-${selectedWorker || 'unspecified'}-${editorSessionKey}`}
                language="markdown"
                original={promptData.currentPrompt}
                modified={draft}
                keepCurrentOriginalModel={true}
                keepCurrentModifiedModel={true}
                originalModelPath={diffModelPaths.originalModelPath}
                modifiedModelPath={diffModelPaths.modifiedModelPath}
                onMount={(editor) => {
                  diffEditorRef.current = editor;
                  const originalEditor = editor.getOriginalEditor?.();
                  const modifiedEditor = editor.getModifiedEditor?.();
                  originalEditor?.updateOptions({
                    readOnly: true,
                    renderLineHighlight: 'none',
                  });
                  modifiedEditor?.updateOptions({ readOnly: false });
                  diffModifiedChangeRef.current?.dispose();
                  const typedModifiedEditor = modifiedEditor as
                    | {
                        onDidChangeModelContent?: (listener: () => void) => { dispose: () => void };
                        getValue?: () => string;
                      }
                    | null
                    | undefined;
                  if (typedModifiedEditor?.onDidChangeModelContent) {
                    const listener = typedModifiedEditor.onDidChangeModelContent(() => {
                      if (activeModalRef.current !== 'edit') return;
                      try {
                        const nextValue = typeof typedModifiedEditor.getValue === 'function' ? typedModifiedEditor.getValue() : '';
                        setDraft(nextValue || '');
                      } catch (error) {
                        console.error('DIFF editor content sync error:', error);
                      }
                    });
                    diffModifiedChangeRef.current = listener as { dispose: () => void };
                  }
                  originalEditor?.getDomNode()?.classList.add('prompt-monaco-readonly');
                  layoutDiffEditor();
                }}
                options={DIFF_EDITOR_OPTIONS}
                height="100%"
                theme="light"
              />
            </div>
          </div>
      </StandardModal>
    </Space>
  );
}
