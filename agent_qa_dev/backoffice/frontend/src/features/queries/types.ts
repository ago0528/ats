export type QueryColumnKey =
  | 'queryId'
  | 'queryText'
  | 'category'
  | 'groupName'
  | 'testSetUsage'
  | 'createdAt'
  | 'updatedAt'
  | 'actions';

export type UploadPreviewRow = {
  key: string;
  queryText: string;
  category: string;
  groupName: string;
  targetAssistant: string;
  contextJson: string;
  expectedResult: string;
  llmEvalCriteria: string;
  logicFieldPath: string;
  logicExpectedValue: string;
  formType: string;
  actionType: string;
  dataKey: string;
  buttonKey: string;
  buttonUrlContains: string;
  multiSelectAllowYn: string;
  intentRubricJson: string;
  accuracyChecksJson: string;
  latencyClass: string;
  criteriaSource: string;
};

export type UploadPreviewParseResult = {
  rows: UploadPreviewRow[];
  totalRows: number;
  emptyText: string;
  warningText?: string;
};

export type BulkUpdatePreviewRow = {
  key: string;
  rowNo: number;
  queryId: string;
  queryText: string;
  status: string;
  changedFields: string[];
};
