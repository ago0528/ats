import { normalizeCsvCell, resolveColumnIndex, splitCsvLine, toNormalizedCsvLines } from '../../../shared/utils/csv';

import { BULK_UPLOAD_PREVIEW_LIMIT } from '../constants';
import type { UploadPreviewParseResult, UploadPreviewRow } from '../types';

export async function parseUploadPreviewFile(file: File): Promise<UploadPreviewParseResult> {
  const filename = (file.name || '').toLowerCase();
  if (!filename.endsWith('.csv')) {
    return {
      rows: [],
      totalRows: 0,
      emptyText: '엑셀 파일은 미리보기를 지원하지 않아요. 업로드는 가능합니다.',
    };
  }

  const lines = toNormalizedCsvLines(await file.text());
  if (lines.length <= 1) {
    return {
      rows: [],
      totalRows: 0,
      emptyText: 'CSV 파일에 미리볼 데이터가 없어요.',
    };
  }

  const headers = splitCsvLine(lines[0]).map(normalizeCsvCell);
  const queryIndex = resolveColumnIndex(headers, ['질의', 'query', 'query_text']);
  const categoryIndex = resolveColumnIndex(headers, ['카테고리', 'category']);
  const groupIndex = resolveColumnIndex(headers, ['그룹', 'group', 'group_name', 'groupId', 'group_id']);
  const targetAssistantIndex = resolveColumnIndex(headers, ['targetAssistant', 'target_assistant', '대상어시스턴트']);
  const contextJsonIndex = resolveColumnIndex(headers, ['contextJson', 'context_json', 'context', '컨텍스트']);
  const expectedResultIndex = resolveColumnIndex(headers, ['기대 결과', '기대결과', '기대값', 'expectedResult', 'expected_result', 'expected']);
  const llmEvalCriteriaIndex = resolveColumnIndex(headers, ['LLM 평가기준(JSON)', 'LLM 평가기준', 'llmEvalCriteria', 'llm_eval_criteria']);
  const logicFieldPathIndex = resolveColumnIndex(headers, ['Logic 검증 필드', '검증 필드', 'logicFieldPath', 'logic_field_path', 'field_path']);
  const logicExpectedValueIndex = resolveColumnIndex(headers, [
    'Logic 기대값',
    '검증 기대값',
    'logicExpectedValue',
    'logic_expected_value',
    'logic_expected',
    'expected_value',
  ]);
  const formTypeIndex = resolveColumnIndex(headers, ['formType', 'form_type', '폼타입']);
  const actionTypeIndex = resolveColumnIndex(headers, ['actionType', 'action_type', '액션타입']);
  const dataKeyIndex = resolveColumnIndex(headers, ['dataKey', 'data_key']);
  const buttonKeyIndex = resolveColumnIndex(headers, ['buttonKey', 'button_key']);
  const buttonUrlContainsIndex = resolveColumnIndex(headers, ['buttonUrlContains', 'button_url_contains']);
  const multiSelectAllowYnIndex = resolveColumnIndex(headers, ['multiSelectAllowYn', 'multi_select_allow_yn']);
  const intentRubricJsonIndex = resolveColumnIndex(headers, ['의도 루브릭(JSON)', 'intentRubricJson', 'intent_rubric_json']);
  const accuracyChecksJsonIndex = resolveColumnIndex(headers, ['정확성 체크(JSON)', 'accuracyChecksJson', 'accuracy_checks_json']);
  const latencyClassIndex = resolveColumnIndex(headers, ['latencyClass', 'latency_class', '응답속도유형', '응답속도 유형']);

  const parsedRows = lines.slice(1).reduce<UploadPreviewRow[]>((acc, line, index) => {
    const columns = splitCsvLine(line).map(normalizeCsvCell);
    const queryText = queryIndex >= 0 ? (columns[queryIndex] || '') : '';
    const category = categoryIndex >= 0 ? (columns[categoryIndex] || '') : '';
    const groupName = groupIndex >= 0 ? (columns[groupIndex] || '') : '';
    const targetAssistant = targetAssistantIndex >= 0 ? (columns[targetAssistantIndex] || '') : '';
    const contextJson = contextJsonIndex >= 0 ? (columns[contextJsonIndex] || '') : '';
    const expectedResult = expectedResultIndex >= 0 ? (columns[expectedResultIndex] || '') : '';
    const llmEvalCriteria = llmEvalCriteriaIndex >= 0 ? (columns[llmEvalCriteriaIndex] || '') : '';
    const logicFieldPath = logicFieldPathIndex >= 0 ? (columns[logicFieldPathIndex] || '') : '';
    const logicExpectedValue = logicExpectedValueIndex >= 0 ? (columns[logicExpectedValueIndex] || '') : '';
    const formType = formTypeIndex >= 0 ? (columns[formTypeIndex] || '') : '';
    const actionType = actionTypeIndex >= 0 ? (columns[actionTypeIndex] || '') : '';
    const dataKey = dataKeyIndex >= 0 ? (columns[dataKeyIndex] || '') : '';
    const buttonKey = buttonKeyIndex >= 0 ? (columns[buttonKeyIndex] || '') : '';
    const buttonUrlContains = buttonUrlContainsIndex >= 0 ? (columns[buttonUrlContainsIndex] || '') : '';
    const multiSelectAllowYn = multiSelectAllowYnIndex >= 0 ? (columns[multiSelectAllowYnIndex] || '') : '';
    const intentRubricJson = intentRubricJsonIndex >= 0 ? (columns[intentRubricJsonIndex] || '') : '';
    const accuracyChecksJson = accuracyChecksJsonIndex >= 0 ? (columns[accuracyChecksJsonIndex] || '') : '';
    const latencyClass = latencyClassIndex >= 0 ? (columns[latencyClassIndex] || '') : '';

    if (
      !queryText
      && !category
      && !groupName
      && !targetAssistant
      && !contextJson
      && !expectedResult
      && !llmEvalCriteria
      && !logicFieldPath
      && !logicExpectedValue
      && !formType
      && !actionType
      && !dataKey
      && !buttonKey
      && !buttonUrlContains
      && !multiSelectAllowYn
      && !intentRubricJson
      && !accuracyChecksJson
      && !latencyClass
    ) {
      return acc;
    }

    const hasAqbV1 = (() => {
      if (!llmEvalCriteria) return false;
      try {
        const parsed = JSON.parse(llmEvalCriteria);
        return parsed && parsed.schemaVersion === 'aqb.v1';
      } catch {
        return false;
      }
    })();
    const hasHelperInputs =
      Boolean(formType || actionType || dataKey || buttonKey || buttonUrlContains || multiSelectAllowYn)
      || Boolean(intentRubricJson || accuracyChecksJson);
    const criteriaSource = hasAqbV1 ? 'aqb.v1' : (hasHelperInputs ? 'helper->aqb.v1' : 'legacy');

    acc.push({
      key: String(index + 1),
      queryText: queryText || '-',
      category: category || '-',
      groupName: groupName || '-',
      targetAssistant: targetAssistant || '-',
      contextJson: contextJson || '-',
      expectedResult: expectedResult || '-',
      llmEvalCriteria: llmEvalCriteria || '-',
      logicFieldPath: logicFieldPath || '-',
      logicExpectedValue: logicExpectedValue || '-',
      formType: formType || '-',
      actionType: actionType || '-',
      dataKey: dataKey || '-',
      buttonKey: buttonKey || '-',
      buttonUrlContains: buttonUrlContains || '-',
      multiSelectAllowYn: multiSelectAllowYn || '-',
      intentRubricJson: intentRubricJson || '-',
      accuracyChecksJson: accuracyChecksJson || '-',
      latencyClass: latencyClass || '-',
      criteriaSource,
    });
    return acc;
  }, []);

  return {
    rows: parsedRows.slice(0, BULK_UPLOAD_PREVIEW_LIMIT),
    totalRows: parsedRows.length,
    emptyText: '표시할 질의가 없어요.',
    warningText: queryIndex < 0 ? 'CSV 헤더에 "질의" 컬럼이 없어요.' : undefined,
  };
}
