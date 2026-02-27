import { useEffect, useMemo, useState } from 'react';

import type { ValidationRun, ValidationTestSet } from '../../../api/types/validation';
import type { ValidationSection } from '../types';
import { getEvaluationStateLabel } from '../utils/runStatus';

export type HistorySortOrder = 'createdAt_desc' | 'createdAt_asc';

export function useValidationHistoryState({
  section,
  runs,
  testSets,
}: {
  section: ValidationSection;
  runs: ValidationRun[];
  testSets: ValidationTestSet[];
}) {
  const [historyCurrentPage, setHistoryCurrentPage] = useState(1);
  const [historyPageSize, setHistoryPageSize] = useState<number>(50);
  const [historyExecutionStatusFilter, setHistoryExecutionStatusFilter] =
    useState<string>('');
  const [historyEvaluationStatusFilter, setHistoryEvaluationStatusFilter] =
    useState<string>('');
  const [historyTestSetFilter, setHistoryTestSetFilter] = useState<string>('');
  const [historyKeywordFilter, setHistoryKeywordFilter] = useState<string>('');
  const [historyCreatedAtFilter, setHistoryCreatedAtFilter] = useState<
    [Date | null, Date | null]
  >([null, null]);
  const [historySortOrder, setHistorySortOrder] = useState<HistorySortOrder>('createdAt_desc');

  const historyTestSetFilterOptions = useMemo(
    () => [
      { label: '전체 테스트 세트', value: '' },
      ...testSets.map((testSet) => ({ label: testSet.name, value: testSet.id })),
    ],
    [testSets],
  );

  useEffect(() => {
    if (!historyTestSetFilter) return;
    if (testSets.some((testSet) => testSet.id === historyTestSetFilter)) {
      return;
    }
    setHistoryTestSetFilter('');
  }, [historyTestSetFilter, testSets]);

  const testSetNameById = useMemo(
    () =>
      testSets.reduce<Record<string, string>>((acc, testSet) => {
        acc[testSet.id] = testSet.name;
        return acc;
      }, {}),
    [testSets],
  );

  const filteredHistoryRuns = useMemo(() => {
    if (section !== 'history') return runs;

    const keyword = historyKeywordFilter.trim().toLowerCase();
    const [startAt, endAt] = historyCreatedAtFilter;
    const startBoundary = startAt
      ? new Date(startAt.getFullYear(), startAt.getMonth(), startAt.getDate())
      : null;
    const endBoundary = endAt
      ? new Date(
        endAt.getFullYear(),
        endAt.getMonth(),
        endAt.getDate(),
        23,
        59,
        59,
        999,
      )
      : null;

    const filtered = runs.filter((run) => {
      if (historyExecutionStatusFilter && run.status !== historyExecutionStatusFilter) {
        return false;
      }
      if (
        historyEvaluationStatusFilter
        && getEvaluationStateLabel(run) !== historyEvaluationStatusFilter
      ) {
        return false;
      }
      if (historyTestSetFilter && run.testSetId !== historyTestSetFilter) {
        return false;
      }
      if (startBoundary || endBoundary) {
        const createdAt = run.createdAt ? new Date(run.createdAt) : null;
        if (!createdAt || Number.isNaN(createdAt.getTime())) return false;
        if (startBoundary && createdAt < startBoundary) return false;
        if (endBoundary && createdAt > endBoundary) return false;
      }
      if (!keyword) return true;

      const testSetName = run.testSetId
        ? testSetNameById[run.testSetId] || run.testSetId
        : '';
      const haystack = [run.id, run.name, testSetName]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(keyword);
    });

    return filtered.sort((a, b) => {
      const aCreated = a.createdAt ? new Date(a.createdAt).getTime() : 0;
      const bCreated = b.createdAt ? new Date(b.createdAt).getTime() : 0;
      if (historySortOrder === 'createdAt_asc') {
        return aCreated - bCreated;
      }
      return bCreated - aCreated;
    });
  }, [
    section,
    runs,
    historyKeywordFilter,
    historyEvaluationStatusFilter,
    historyExecutionStatusFilter,
    historyTestSetFilter,
    historyCreatedAtFilter,
    historySortOrder,
    testSetNameById,
  ]);

  useEffect(() => {
    if (section !== 'history') return;
    const maxPage = Math.max(
      1,
      Math.ceil(filteredHistoryRuns.length / historyPageSize),
    );
    if (historyCurrentPage > maxPage) {
      setHistoryCurrentPage(maxPage);
    }
  }, [
    section,
    filteredHistoryRuns.length,
    historyCurrentPage,
    historyPageSize,
  ]);

  useEffect(() => {
    if (section !== 'history') return;
    setHistoryCurrentPage(1);
  }, [
    section,
    historyExecutionStatusFilter,
    historyEvaluationStatusFilter,
    historyTestSetFilter,
    historyKeywordFilter,
    historyCreatedAtFilter,
    historySortOrder,
  ]);

  const resetHistoryFilters = () => {
    setHistoryExecutionStatusFilter('');
    setHistoryEvaluationStatusFilter('');
    setHistoryTestSetFilter('');
    setHistoryKeywordFilter('');
    setHistoryCreatedAtFilter([null, null]);
    setHistorySortOrder('createdAt_desc');
  };

  return {
    historyCurrentPage,
    historyPageSize,
    setHistoryCurrentPage,
    setHistoryPageSize,
    historyExecutionStatusFilter,
    setHistoryExecutionStatusFilter,
    historyEvaluationStatusFilter,
    setHistoryEvaluationStatusFilter,
    historyTestSetFilter,
    setHistoryTestSetFilter,
    historyKeywordFilter,
    setHistoryKeywordFilter,
    historyCreatedAtFilter,
    setHistoryCreatedAtFilter,
    historySortOrder,
    setHistorySortOrder,
    historyTestSetFilterOptions,
    filteredHistoryRuns,
    resetHistoryFilters,
    testSetNameById,
  };
}
