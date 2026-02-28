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
export const BULK_UPDATE_EMPTY_TEXT = '질의를 업로드해주세요.';
export const BULK_UPDATE_PREVIEW_LIMIT = 20;

export const DEFAULT_COLUMN_WIDTHS: Record<QueryColumnKey, number> = {
  queryId: 120,
  queryText: 380,
  category: 140,
  groupName: 100,
  testSetUsage: 120,
  createdAt: 140,
  updatedAt: 140,
  actions: 180,
};

export const TABLE_ROW_SELECTION_WIDTH = 72;

export const BULK_UPLOAD_PREVIEW_COLUMNS: ColumnsType<UploadPreviewRow> = [
  {
    key: 'queryText',
    title: '질의',
    dataIndex: 'queryText',
    width: 320,
    ellipsis: true,
  },
  {
    key: 'category',
    title: '카테고리',
    dataIndex: 'category',
    width: 140,
    ellipsis: true,
  },
  {
    key: 'groupName',
    title: '그룹',
    dataIndex: 'groupName',
    width: 140,
    ellipsis: true,
  },
  {
    key: 'expectedResult',
    title: '기대 결과',
    dataIndex: 'expectedResult',
    width: 220,
    ellipsis: true,
  },
  {
    key: 'latencyClass',
    title: 'latencyClass',
    dataIndex: 'latencyClass',
    width: 130,
    ellipsis: true,
  },
];
