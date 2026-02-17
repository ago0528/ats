import { useEffect } from 'react';

import type { ValidationSection } from '../types';

export function useValidationRuntimeEffects({
  environment,
  section,
  historyRunId,
  queryPickerOpen,
  queryPickerSearchKeyword,
  queryPickerCategory,
  queryPickerGroupId,
  queryPickerPage,
  queryPickerPageSize,
  selectedRunId,
  currentRunStatus,
  runItemsLength,
  runItemsPageSize,
  runItemsCurrentPage,
  historyLength,
  historyPageSize,
  historyCurrentPage,
  loadMeta,
  loadQueryPicker,
  loadRunDetail,
  loadRuns,
  setRunItemsCurrentPage,
  setHistoryCurrentPage,
  setQueryPickerOpen,
}: {
  environment: string;
  section: ValidationSection;
  historyRunId?: string;
  queryPickerOpen: boolean;
  queryPickerSearchKeyword: string;
  queryPickerCategory?: string;
  queryPickerGroupId?: string;
  queryPickerPage: number;
  queryPickerPageSize: number;
  selectedRunId: string;
  currentRunStatus?: string;
  runItemsLength: number;
  runItemsPageSize: number;
  runItemsCurrentPage: number;
  historyLength: number;
  historyPageSize: number;
  historyCurrentPage: number;
  loadMeta: () => Promise<void>;
  loadQueryPicker: () => Promise<void>;
  loadRunDetail: (runId: string) => Promise<void>;
  loadRuns: () => Promise<void>;
  setRunItemsCurrentPage: (page: number) => void;
  setHistoryCurrentPage: (page: number) => void;
  setQueryPickerOpen: (open: boolean) => void;
}) {
  useEffect(() => {
    void loadMeta();
  }, [environment]);

  useEffect(() => {
    if (!queryPickerOpen) return;
    void loadQueryPicker();
  }, [
    queryPickerOpen,
    queryPickerSearchKeyword,
    queryPickerCategory,
    queryPickerGroupId,
    queryPickerPage,
    queryPickerPageSize,
  ]);

  useEffect(() => {
    if (section !== 'history-detail' || !historyRunId) return;
    void loadRunDetail(historyRunId);
  }, [section, historyRunId]);

  useEffect(() => {
    if (!selectedRunId) return;
    if (currentRunStatus !== 'RUNNING') return;
    const timer = window.setInterval(() => {
      void loadRunDetail(selectedRunId);
      void loadRuns();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [selectedRunId, currentRunStatus]);

  useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(runItemsLength / runItemsPageSize));
    if (runItemsCurrentPage > maxPage) {
      setRunItemsCurrentPage(maxPage);
    }
  }, [runItemsLength, runItemsPageSize, runItemsCurrentPage]);

  useEffect(() => {
    if (section === 'run') return;
    setQueryPickerOpen(false);
  }, [section]);

  useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(historyLength / historyPageSize));
    if (historyCurrentPage > maxPage) {
      setHistoryCurrentPage(maxPage);
    }
  }, [historyLength, historyPageSize, historyCurrentPage]);
}
