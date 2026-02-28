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
  expectedResult: string;
  latencyClass: string;
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
