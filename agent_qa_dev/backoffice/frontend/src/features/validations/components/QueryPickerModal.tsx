import { Button, Input, Select, Space, Typography } from 'antd';

import type { QueryGroup, ValidationQuery } from '../../../api/types/validation';
import { QueryCategoryTag } from '../../../components/common/QueryCategoryTag';
import { StandardDataTable } from '../../../components/common/StandardDataTable';
import { StandardModal } from '../../../components/common/StandardModal';
import { QUERY_CATEGORY_OPTIONS } from '../constants';

export function QueryPickerModal({
  queryPickerOpen,
  setQueryPickerOpen,
  queryPickerSaving,
  handleImportQueries,
  queryPickerSearchInput,
  setQueryPickerSearchInput,
  setQueryPickerSearchKeyword,
  setQueryPickerPage,
  queryPickerCategory,
  setQueryPickerCategory,
  queryPickerGroupId,
  setQueryPickerGroupId,
  groups,
  queryPickerSelectedIds,
  queryPickerLoading,
  queryPickerItems,
  setQueryPickerSelectedIds,
  queryPickerPage,
  queryPickerPageSize,
  setQueryPickerPageSize,
  queryPickerTotal,
}: {
  queryPickerOpen: boolean;
  setQueryPickerOpen: (open: boolean) => void;
  queryPickerSaving: boolean;
  handleImportQueries: () => void;
  queryPickerSearchInput: string;
  setQueryPickerSearchInput: (value: string) => void;
  setQueryPickerSearchKeyword: (value: string) => void;
  setQueryPickerPage: (page: number) => void;
  queryPickerCategory?: string;
  setQueryPickerCategory: (value?: string) => void;
  queryPickerGroupId?: string;
  setQueryPickerGroupId: (value?: string) => void;
  groups: QueryGroup[];
  queryPickerSelectedIds: string[];
  queryPickerLoading: boolean;
  queryPickerItems: ValidationQuery[];
  setQueryPickerSelectedIds: (ids: string[]) => void;
  queryPickerPage: number;
  queryPickerPageSize: number;
  setQueryPickerPageSize: (size: number) => void;
  queryPickerTotal: number;
}) {
  return (
    <StandardModal
      title="질의 불러오기"
      open={queryPickerOpen}
      width={1260}
      onCancel={() => setQueryPickerOpen(false)}
      footer={
        <Space>
          <Button onClick={() => setQueryPickerOpen(false)}>취소</Button>
          <Button type="primary" loading={queryPickerSaving} onClick={handleImportQueries}>
            불러오기
          </Button>
        </Space>
      }
    >
      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0, flex: 1 }}>
        <Space wrap>
          <Input.Search
            value={queryPickerSearchInput}
            placeholder="질의 검색"
            allowClear
            enterButton
            style={{ width: 280 }}
            onChange={(event) => {
              const value = event.target.value;
              setQueryPickerSearchInput(value);
              if (!value) {
                setQueryPickerSearchKeyword('');
                setQueryPickerPage(1);
              }
            }}
            onSearch={(value) => {
              setQueryPickerSearchInput(value);
              setQueryPickerSearchKeyword(value);
              setQueryPickerPage(1);
            }}
          />
          <Select
            allowClear
            placeholder="카테고리"
            options={QUERY_CATEGORY_OPTIONS.map((option) => ({ label: option.label, value: option.value }))}
            value={queryPickerCategory}
            onChange={(value) => {
              setQueryPickerCategory(value);
              setQueryPickerPage(1);
            }}
            style={{ width: 160 }}
          />
          <Select
            allowClear
            placeholder="그룹"
            options={groups.map((group) => ({ label: group.groupName, value: group.id }))}
            value={queryPickerGroupId}
            onChange={(value) => {
              setQueryPickerGroupId(value);
              setQueryPickerPage(1);
            }}
            style={{ width: 180 }}
          />
          <Typography.Text type="secondary">선택 질의 {queryPickerSelectedIds.length}개</Typography.Text>
        </Space>

        <StandardDataTable
          tableId="validation-query-picker"
          scrollXPadding={72}
          rowKey="id"
          size="small"
          loading={queryPickerLoading}
          dataSource={queryPickerItems}
          rowSelection={{
            preserveSelectedRowKeys: true,
            selectedRowKeys: queryPickerSelectedIds,
            onChange: (keys) => setQueryPickerSelectedIds(keys.map(String)),
          }}
          pagination={{
            current: queryPickerPage,
            pageSize: queryPickerPageSize,
            total: queryPickerTotal,
            onChange: (page, nextPageSize) => {
              if (nextPageSize !== queryPickerPageSize) {
                setQueryPickerPageSize(nextPageSize);
                setQueryPickerPage(1);
                return;
              }
              setQueryPickerPage(page);
            },
          }}
          columns={[
            { key: 'id', title: '질의 ID', dataIndex: 'id', width: 220, ellipsis: true },
            { key: 'queryText', title: '질의', dataIndex: 'queryText', ellipsis: true },
            { key: 'category', title: '카테고리', dataIndex: 'category', width: 140, render: (value: string) => <QueryCategoryTag category={value} /> },
            { key: 'groupName', title: '그룹', dataIndex: 'groupName', width: 200, render: (value?: string) => value || '-' },
          ]}
        />
      </div>
    </StandardModal>
  );
}
