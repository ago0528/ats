export type QueryColumnKey =
  | 'queryId'
  | 'queryText'
  | 'category'
  | 'groupName'
  | 'createdAt'
  | 'latestRun'
  | 'latestResult'
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
};

export type UploadPreviewParseResult = {
  rows: UploadPreviewRow[];
  totalRows: number;
  emptyText: string;
  warningText?: string;
};
