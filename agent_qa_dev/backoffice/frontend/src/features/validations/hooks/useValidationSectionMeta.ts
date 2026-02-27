import { useMemo } from 'react';

import type { ValidationRun } from '../../../api/types/validation';
import type { HistoryDetailTab, ValidationSection } from '../types';

export function useValidationSectionMeta({
  section,
  historyDetailTab,
  historyRunId,
  currentRun,
}: {
  section: ValidationSection;
  historyDetailTab?: HistoryDetailTab;
  historyRunId?: string;
  currentRun: ValidationRun | null;
}) {
  const sectionTitle = useMemo(() => {
    if (section === 'history') return '검증 결과';
    if (section === 'history-detail') {
      if (historyDetailTab === 'results') {
        return '평가 결과';
      }
      return '질문 결과 상세';
    }
    if (section === 'dashboard') return '대시보드';
    return '검증 실행';
  }, [section, historyDetailTab]);

  const isHistoryDetailMatched =
    section !== 'history-detail' || !historyRunId || currentRun?.id === historyRunId;

  return {
    sectionTitle,
    isHistoryDetailMatched,
  };
}
