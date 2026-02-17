import type { ColumnsType } from 'antd/es/table';

import type { QueryCategory } from '../../api/types/validation';
import type { QueryColumnKey, UploadPreviewRow } from './types';

export const CATEGORY_OPTIONS: Array<{ label: string; value: QueryCategory }> = [
  { label: 'Happy path', value: 'Happy path' },
  { label: 'Edge case', value: 'Edge case' },
  { label: 'Adversarial input', value: 'Adversarial input' },
];

export const BULK_UPLOAD_PREVIEW_LIMIT = 10;
export const BULK_UPLOAD_EMPTY_TEXT = '질의를 업로드해주세요.';

export const DEFAULT_COLUMN_WIDTHS: Record<QueryColumnKey, number> = {
  queryId: 120,
  queryText: 380,
  category: 140,
  groupName: 100,
  createdAt: 140,
  latestRun: 160,
  latestResult: 220,
  actions: 180,
};

export const TABLE_ROW_SELECTION_WIDTH = 72;

export const BULK_UPLOAD_PREVIEW_COLUMNS: ColumnsType<UploadPreviewRow> = [
  {
    key: 'queryText',
    title: '질의',
    dataIndex: 'queryText',
    width: 460,
    ellipsis: true,
  },
  {
    key: 'category',
    title: '카테고리',
    dataIndex: 'category',
    width: 160,
    ellipsis: true,
  },
  {
    key: 'groupName',
    title: '그룹',
    dataIndex: 'groupName',
    width: 160,
    ellipsis: true,
  },
];
