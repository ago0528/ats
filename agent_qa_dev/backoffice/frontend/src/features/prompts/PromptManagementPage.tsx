import { useCallback } from 'react';
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

import type { Environment } from '../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../app/types';
import { StandardModal, StandardModalMetaBlock } from '../../components/common/StandardModal';
import { getLengthDelta } from './utils/promptDiff';
import { PromptWorkerTable } from './components/PromptWorkerTable';
import { usePromptWorkers } from './hooks/usePromptWorkers';
import { usePromptModalLifecycle } from './hooks/usePromptModalLifecycle';
export { buildWorkerLabel } from './utils/promptViewModel';

const MODAL_TITLES = {
  view: '프롬프트 조회',
  edit: '프롬프트 수정',
} as const;

const MODAL_WIDTH = {
  view: 'min(1200px, 90vw)',
  edit: 'min(1200px, 90vw)',
} as const;

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

export function PromptManagementPage({
  environment,
  tokens,
}: {
  environment: Environment;
  tokens: RuntimeSecrets;
}) {
  const { message } = App.useApp();
  const {
    activeModal,
    setActiveModal,
    selectedWorker,
    selectedWorkerLabel,
    promptData,
    draft,
    setDraft,
    search,
    setSearch,
    isFetchingList,
    isPromptSaving,
    editorSessionKey,
    hasTokens,
    hasUnsavedChanges,
    viewDiffSummary,
    diffSummary,
    diffModelPaths,
    viewDiffModelPaths,
    filteredWorkers,
    isWorkerFetching,
    openPromptModal,
    updatePrompt,
    resetPrompt,
    clearPromptState,
  } = usePromptWorkers({
    environment,
    tokens,
    message,
  });

  const {
    activeModalRef,
    diffModifiedChangeRef,
    viewDiffEditorRef,
    viewDiffWrapperRef,
    diffEditorRef,
    diffWrapperRef,
    closeModal,
    closeModalStateIfNeeded,
    requestCloseViewModal,
    requestCloseEditModal,
    disposeDiffEditorListeners,
    layoutDiffEditor,
    layoutViewDiffEditor,
  } = usePromptModalLifecycle({
    activeModal,
    setActiveModal,
    hasUnsavedChanges,
    onClearModalState: clearPromptState,
  });

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

  const copyTextToClipboard = useCallback(async (
    label: string,
    text: string,
    successMessage?: string,
  ) => {
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
    } catch (error) {
      message.error(`${label} 복사에 실패했습니다.`);
      console.error(error);
    }
  }, [message]);

  const handleSavePrompt = async () => {
    const saved = await updatePrompt();
    if (!saved) return;
    disposeDiffEditorListeners();
    closeModal('edit');
  };

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
            onChange={(event) => setSearch(event.target.value)}
            allowClear
            placeholder="워커 혹은 워커 설명으로 검색해 주세요."
          />
        </Space>
      </Card>

      <PromptWorkerTable
        workers={filteredWorkers}
        loading={isFetchingList}
        onView={(workerType) => {
          void openPromptModal(workerType, 'view');
        }}
        onEdit={(workerType) => {
          void openPromptModal(workerType, 'edit');
        }}
        onReset={(workerType) => {
          void resetPrompt(workerType);
        }}
        isWorkerFetching={isWorkerFetching}
      />

      <StandardModal
        title={MODAL_TITLES.view}
        open={activeModal === 'view'}
        width={MODAL_WIDTH.view}
        onCancel={requestCloseViewModal}
        bodyPadding={0}
        afterClose={() => closeModalStateIfNeeded('view')}
        footer={(
          <Space>
            <Button onClick={requestCloseViewModal}>닫기</Button>
          </Space>
        )}
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
                  onClick={() => {
                    void copyTextToClipboard('직전 프롬프트', promptData.previousPrompt, '클립보드로 복사됐어요.');
                  }}
                >
                  Copy 직전
                </Button>
                <Button
                  icon={<CopyOutlined />}
                  onClick={() => {
                    void copyTextToClipboard('현재 프롬프트', promptData.currentPrompt, '클립보드로 복사됐어요.');
                  }}
                >
                  Copy 현재
                </Button>
                <Button
                  icon={<CopyOutlined />}
                  onClick={() => {
                    void copyTextToClipboard('DIFF', viewDiffSummary.diffText, '클립보드로 복사됐어요.');
                  }}
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
                originalModelPath={viewDiffModelPaths.originalModelPath}
                modifiedModelPath={viewDiffModelPaths.modifiedModelPath}
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
        footer={(
          <Space>
            <Button onClick={requestCloseEditModal}>취소</Button>
            <Button type="primary" loading={isPromptSaving} onClick={() => { void handleSavePrompt(); }}>
              저장
            </Button>
          </Space>
        )}
      >
        <div style={{ display: 'flex', flexDirection: 'column', width: '100%', height: '520px', minHeight: 0, gap: 12 }}>
          <StandardModalMetaBlock padding={0} gap={8} marginBottom={12}>
            <div style={{ color: 'var(--ant-color-text-secondary)' }}>
              선택된 프롬프트: {selectedWorker} {selectedWorkerLabel ? ` (${selectedWorkerLabel})` : ''} <br />
              프롬프트 수정 후, 우측 하단의 '저장' 버튼을 눌러 변경사항을 저장하세요.
            </div>
          </StandardModalMetaBlock>
          <Space direction="vertical" style={{ width: '100%' }} size={6}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <Typography.Text strong>AS-IS</Typography.Text>
              <Typography.Text strong>TO-BE</Typography.Text>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <Space size={8}>
                <Tag color="blue">길이 차이: {getLengthDelta(promptData.currentPrompt, draft)}</Tag>
                <Tag color="success">+Added {diffSummary.added}</Tag>
                <Tag color="error">-Removed {diffSummary.removed}</Tag>
                <Tag color="warning">~Modified {diffSummary.modified}</Tag>
              </Space>
              <Space size={8} wrap>
                <Button
                  icon={<CopyOutlined />}
                  onClick={() => {
                    void copyTextToClipboard('AS-IS', promptData.currentPrompt);
                  }}
                >
                  Copy AS-IS
                </Button>
                <Button
                  icon={<CopyOutlined />}
                  onClick={() => {
                    void copyTextToClipboard('TO-BE', draft);
                  }}
                >
                  Copy TO-BE
                </Button>
                <Button
                  icon={<CopyOutlined />}
                  onClick={() => {
                    void copyTextToClipboard('DIFF', diffSummary.diffText);
                  }}
                >
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
                      const nextValue =
                        typeof typedModifiedEditor.getValue === 'function'
                          ? typedModifiedEditor.getValue()
                          : '';
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
