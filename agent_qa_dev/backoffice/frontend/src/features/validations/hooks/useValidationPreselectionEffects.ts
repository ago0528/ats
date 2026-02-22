import { useEffect } from 'react';
import type { MessageInstance } from 'antd/es/message/interface';

import { getValidationRun, listValidationRunItems } from '../../../api/validation';
import type { ValidationQuery } from '../../../api/types/validation';
import { stringifyPretty } from '../../../shared/utils/json';
import type { RunCreateOverrides } from './useValidationActions';

export function useValidationPreselectionEffects({
  preselectedQueryIds,
  onConsumedPreselectedQueryIds,
  preselectedRerunRunId,
  onConsumedPreselectedRerunRunId,
  applySelectedQueryIds,
  message,
  setCreateRunOverrides,
  setRunMode,
  setLoading,
  setAdHocQueryText,
  setAdHocExpected,
  setAdHocCriteria,
  setAdHocLogicFieldPath,
  setAdHocLogicExpected,
  setSelectedQueryIds,
  setSelectedQueries,
}: {
  preselectedQueryIds?: string[];
  onConsumedPreselectedQueryIds?: () => void;
  preselectedRerunRunId?: string;
  onConsumedPreselectedRerunRunId?: () => void;
  applySelectedQueryIds: (queryIds: string[], options?: { silentMissingWarning?: boolean }) => Promise<number>;
  message: MessageInstance;
  setCreateRunOverrides: (next: RunCreateOverrides) => void;
  setRunMode: (mode: 'REGISTERED' | 'AD_HOC') => void;
  setLoading: (value: boolean) => void;
  setAdHocQueryText: (value: string) => void;
  setAdHocExpected: (value: string) => void;
  setAdHocCriteria: (value: string) => void;
  setAdHocLogicFieldPath: (value: string) => void;
  setAdHocLogicExpected: (value: string) => void;
  setSelectedQueryIds: (ids: string[]) => void;
  setSelectedQueries: (queries: ValidationQuery[]) => void;
}) {
  useEffect(() => {
    if (!preselectedQueryIds?.length) return;
    setCreateRunOverrides({});
    setRunMode('REGISTERED');
    void (async () => {
      try {
        await applySelectedQueryIds(preselectedQueryIds, { silentMissingWarning: true });
      } catch (error) {
        console.error(error);
        message.error('선택 질의를 불러오지 못했습니다.');
      } finally {
        onConsumedPreselectedQueryIds?.();
      }
    })();
  }, [preselectedQueryIds, onConsumedPreselectedQueryIds, applySelectedQueryIds, message]);

  useEffect(() => {
    if (!preselectedRerunRunId) return;
    setRunMode('REGISTERED');
    void (async () => {
      try {
        setLoading(true);
        const [sourceRun, sourceItemsResponse] = await Promise.all([
          getValidationRun(preselectedRerunRunId),
          listValidationRunItems(preselectedRerunRunId, { limit: 2000 }),
        ]);
        const sortedItems = [...sourceItemsResponse.items].sort((a, b) => a.ordinal - b.ordinal);
        setCreateRunOverrides({
          agentId: sourceRun.agentId,
          testModel: sourceRun.testModel,
          evalModel: sourceRun.evalModel,
          repeatInConversation: sourceRun.repeatInConversation,
          conversationRoomCount: sourceRun.conversationRoomCount,
          agentParallelCalls: sourceRun.agentParallelCalls,
          timeoutMs: sourceRun.timeoutMs,
        });

        const sourceMode: 'REGISTERED' | 'AD_HOC' = sortedItems.every((item) => !item.queryId)
          ? 'AD_HOC'
          : 'REGISTERED';

        if (sourceMode === 'REGISTERED') {
          const uniqueQueryIds = Array.from(
            new Set(
              sortedItems
                .map((item) => item.queryId)
                .filter((queryId): queryId is string => Boolean(queryId)),
            ),
          );
          setRunMode('REGISTERED');
          await applySelectedQueryIds(uniqueQueryIds);
          setAdHocQueryText('');
          setAdHocExpected('');
          setAdHocCriteria('');
          setAdHocLogicFieldPath('');
          setAdHocLogicExpected('');
        } else {
          const firstItem = sortedItems[0];
          setRunMode('AD_HOC');
          setSelectedQueryIds([]);
          setSelectedQueries([]);
          setAdHocQueryText(firstItem?.queryText ?? '');
          setAdHocExpected(firstItem?.expectedResult ?? '');
          setAdHocCriteria(firstItem ? stringifyPretty(firstItem.appliedCriteria) : '');
          setAdHocLogicFieldPath(firstItem?.logicFieldPath ?? '');
          setAdHocLogicExpected(firstItem?.logicExpectedValue ?? '');
        }
        message.success('재실행 프리셋을 불러왔습니다.');
      } catch (error) {
        console.error(error);
        message.error('재실행 프리셋 불러오기에 실패했습니다.');
      } finally {
        setLoading(false);
        onConsumedPreselectedRerunRunId?.();
      }
    })();
  }, [preselectedRerunRunId, onConsumedPreselectedRerunRunId, applySelectedQueryIds, message]);
}
