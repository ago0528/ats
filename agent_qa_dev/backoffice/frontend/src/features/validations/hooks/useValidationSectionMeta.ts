import { useMemo } from 'react';

import type { ValidationRun } from '../../../api/types/validation';
import type { ValidationSection } from '../types';

export function useValidationSectionMeta({
  section,
  historyRunId,
  currentRun,
}: {
  section: ValidationSection;
  historyRunId?: string;
  currentRun: ValidationRun | null;
}) {
  const sectionTitle = useMemo(() => {
    if (section === 'history') return '검증 이력';
    if (section === 'history-detail') return '검증 이력 상세';
    if (section === 'dashboard') return '대시보드';
    return '검증 실행';
  }, [section]);

  const isHistoryDetailMatched =
    section !== 'history-detail' || !historyRunId || currentRun?.id === historyRunId;

  return {
    sectionTitle,
    isHistoryDetailMatched,
  };
}
