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
};

export type UploadPreviewParseResult = {
  rows: UploadPreviewRow[];
  totalRows: number;
  emptyText: string;
  warningText?: string;
};
