import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MessageInstance } from 'antd/es/message/interface';

import { api } from '../../../api/client';
import type { RuntimeSecrets } from '../../../app/types';
import type { Environment } from '../../../app/EnvironmentScope';
import { calculateLineDiff } from '../utils/promptDiff';
import {
  normalizePromptSnapshot,
  normalizePromptText,
  type PromptSnapshotData,
} from '../utils/promptSnapshot';
import {
  buildPromptDiffModelPaths,
  buildPromptViewDiffModelPaths,
  filterPromptWorkers,
  type PromptWorker,
} from '../utils/promptViewModel';

export type ModalMode = 'view' | 'edit';

type WorkerPromptData = PromptSnapshotData;

const EMPTY_PROMPT_DATA: WorkerPromptData = {
  before: '',
  after: '',
  currentPrompt: '',
  previousPrompt: '',
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

export function usePromptWorkers({
  environment,
  tokens,
  message,
}: {
  environment: Environment;
  tokens: RuntimeSecrets;
  message: MessageInstance;
}) {
  const [workers, setWorkers] = useState<PromptWorker[]>([]);
  const [activeModal, setActiveModal] = useState<ModalMode | null>(null);
  const [selectedWorker, setSelectedWorker] = useState('');
  const [promptData, setPromptData] = useState<WorkerPromptData>(
    EMPTY_PROMPT_DATA,
  );
  const [draft, setDraft] = useState('');
  const [search, setSearch] = useState('');
  const [isFetchingList, setIsFetchingList] = useState(false);
  const [isPromptSaving, setIsPromptSaving] = useState(false);
  const [editorSessionKey, setEditorSessionKey] = useState(0);
  const [fetchingWorkerTypes, setFetchingWorkerTypes] = useState<string[]>([]);
  const promptFetchLocksRef = useRef<Set<string>>(new Set());

  const hasTokens = Boolean(tokens.bearer && tokens.cms && tokens.mrs);

  const hasUnsavedChanges = useMemo(
    () => normalizePromptText(draft) !== normalizePromptText(promptData.currentPrompt),
    [draft, promptData.currentPrompt],
  );

  const selectedWorkerLabel = useMemo(
    () => workers.find((worker) => worker.workerType === selectedWorker)?.description || '',
    [selectedWorker, workers],
  );

  const viewDiffSummary = useMemo(
    () => calculateLineDiff(promptData.previousPrompt, promptData.currentPrompt),
    [promptData.previousPrompt, promptData.currentPrompt],
  );

  const diffSummary = useMemo(
    () => calculateLineDiff(promptData.currentPrompt, draft),
    [promptData.currentPrompt, draft],
  );

  const diffModelPaths = useMemo(
    () =>
      buildPromptDiffModelPaths({
        environment,
        selectedWorker,
        editorSessionKey,
      }),
    [environment, selectedWorker, editorSessionKey],
  );

  const viewDiffModelPaths = useMemo(
    () =>
      buildPromptViewDiffModelPaths({
        environment,
        selectedWorker,
        editorSessionKey,
      }),
    [environment, selectedWorker, editorSessionKey],
  );

  const filteredWorkers = useMemo(
    () => filterPromptWorkers(workers, search),
    [workers, search],
  );

  const loadWorkers = useCallback(async () => {
    setIsFetchingList(true);
    try {
      const response = await api.get('/prompts/workers', getApiHeaders(tokens));
      setWorkers(response.data.workers || []);
    } catch (error) {
      message.error('프롬프트 worker 목록 조회에 실패했습니다.');
      console.error(error);
      setWorkers([]);
    } finally {
      setIsFetchingList(false);
    }
  }, [message, tokens]);

  useEffect(() => {
    if (!hasTokens) {
      setWorkers([]);
      return;
    }
    void loadWorkers();
  }, [hasTokens, loadWorkers]);

  const fetchPromptSnapshot = useCallback(async (workerType: string) => {
    const response = await api.get(
      `/prompts/${environment}/${workerType}`,
      getApiHeaders(tokens),
    );
    return normalizePromptSnapshot(response.data);
  }, [environment, tokens]);

  const setWorkerFetchingState = useCallback(
    (workerType: string, isFetching: boolean) => {
      setFetchingWorkerTypes((prev) => {
        if (isFetching) {
          if (prev.includes(workerType)) return prev;
          return [...prev, workerType];
        }
        return prev.filter((item) => item !== workerType);
      });
    },
    [],
  );

  const isWorkerFetching = useCallback(
    (workerType: string) => fetchingWorkerTypes.includes(workerType),
    [fetchingWorkerTypes],
  );

  const openPromptModal = useCallback(async (
    workerType: string,
    nextMode: ModalMode = 'view',
  ) => {
    if (!hasTokens) {
      message.warning('토큰이 없어 프롬프트 조회가 불가합니다.');
      return;
    }
    if (promptFetchLocksRef.current.has(workerType)) {
      return;
    }

    promptFetchLocksRef.current.add(workerType);
    setWorkerFetchingState(workerType, true);
    setSelectedWorker(workerType);
    try {
      const nextData = await fetchPromptSnapshot(workerType);
      setPromptData(nextData);
      setDraft(nextMode === 'edit' ? nextData.currentPrompt : nextData.currentPrompt);
      setEditorSessionKey((prev) => prev + 1);
      setActiveModal(nextMode);
    } catch (error) {
      message.error('프롬프트 조회에 실패했습니다.');
      console.error(error);
    } finally {
      promptFetchLocksRef.current.delete(workerType);
      setWorkerFetchingState(workerType, false);
    }
  }, [
    fetchPromptSnapshot,
    hasTokens,
    message,
    setWorkerFetchingState,
  ]);

  const updatePrompt = useCallback(async (): Promise<boolean> => {
    if (!selectedWorker) return false;

    const normalizedDraft = normalizePromptText(draft);
    const normalizedCurrentPrompt = normalizePromptText(promptData.currentPrompt);
    if (normalizedDraft === normalizedCurrentPrompt) {
      message.warning('프롬프트 수정사항이 없어요.');
      return false;
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

      setPromptData(syncedData);
      setDraft(syncedData.currentPrompt);
      await loadWorkers();
      return true;
    } catch (error) {
      message.error('프롬프트 저장에 실패했습니다.');
      console.error(error);
      return false;
    } finally {
      setIsPromptSaving(false);
    }
  }, [
    draft,
    environment,
    fetchPromptSnapshot,
    loadWorkers,
    message,
    promptData.currentPrompt,
    selectedWorker,
    tokens,
  ]);

  const resetPrompt = useCallback(async (workerType: string): Promise<boolean> => {
    if (!hasTokens) {
      message.warning('토큰이 없어 프롬프트 초기화가 불가합니다.');
      return false;
    }

    setIsPromptSaving(true);
    try {
      const response = await api.put(
        `/prompts/${environment}/${workerType}/reset`,
        {},
        getApiHeaders(tokens),
      );
      const nextData = normalizePromptSnapshot(response.data);
      setPromptData(nextData);
      setDraft(nextData.currentPrompt);
      setSelectedWorker(workerType);
      setActiveModal('view');
      message.success('프롬프트가 초기화되었습니다.');
      await loadWorkers();
      return true;
    } catch (error) {
      message.error('프롬프트 초기화에 실패했습니다.');
      console.error(error);
      return false;
    } finally {
      setIsPromptSaving(false);
    }
  }, [environment, hasTokens, loadWorkers, message, tokens]);

  const clearPromptState = useCallback(() => {
    setSelectedWorker('');
    setPromptData(EMPTY_PROMPT_DATA);
    setDraft('');
  }, []);

  return {
    workers,
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
  };
}
