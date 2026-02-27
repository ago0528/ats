import { useCallback, useEffect, useRef } from 'react';
import { Modal } from 'antd';

import type { ModalMode } from './usePromptWorkers';

export function usePromptModalLifecycle({
  activeModal,
  setActiveModal,
  hasUnsavedChanges,
  onClearModalState,
}: {
  activeModal: ModalMode | null;
  setActiveModal: (mode: ModalMode | null) => void;
  hasUnsavedChanges: boolean;
  onClearModalState: () => void;
}) {
  const closeModeRef = useRef<ModalMode | null>(null);
  const activeModalRef = useRef<ModalMode | null>(null);
  const diffModifiedChangeRef = useRef<{ dispose: () => void } | null>(null);
  const viewDiffEditorRef = useRef<{ layout: () => void } | null>(null);
  const viewDiffWrapperRef = useRef<HTMLDivElement | null>(null);
  const diffEditorRef = useRef<{
    layout: () => void;
    getOriginalEditor?: () => {
      updateOptions: (options: Record<string, unknown>) => void;
      getDomNode?: () => HTMLElement | null;
    };
    getModifiedEditor?: () => {
      updateOptions: (options: Record<string, unknown>) => void;
    };
  } | null>(null);
  const diffWrapperRef = useRef<HTMLDivElement | null>(null);

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

  const closeModal = useCallback((mode: ModalMode) => {
    closeModeRef.current = mode;
    setActiveModal(null);
  }, [setActiveModal]);

  const closeModalStateIfNeeded = useCallback((mode: ModalMode) => {
    if (closeModeRef.current !== mode) return;
    closeModeRef.current = null;
    disposeDiffEditorListeners();
    viewDiffEditorRef.current = null;
    onClearModalState();
  }, [disposeDiffEditorListeners, onClearModalState]);

  const requestCloseViewModal = useCallback(() => {
    closeModal('view');
  }, [closeModal]);

  const requestCloseEditModal = useCallback(() => {
    if (!hasUnsavedChanges) {
      closeModal('edit');
      return;
    }

    Modal.confirm({
      title: '변경사항이 저장되지 않았습니다',
      content: '편집 중인 TO-BE 내용이 있습니다. 닫으면 변경사항이 사라집니다.',
      okText: '변경사항 버리기',
      cancelText: '계속 편집',
      okType: 'danger',
      onOk: () => {
        closeModal('edit');
      },
    });
  }, [closeModal, hasUnsavedChanges]);

  useEffect(() => {
    if (activeModal !== 'edit') return;

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
    if (activeModal !== 'view') return;

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

  return {
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
  };
}
