import { useMemo } from 'react';
import { App, Button, Card, Input, Popconfirm, Space } from 'antd';

import type { ValidationTestSet } from '../../api/types/validation';
import type { Environment } from '../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../app/types';
import { StandardDataTable } from '../../components/common/StandardDataTable';
import { formatDateTime } from '../../shared/utils/dateTime';
import { QueryPickerModal } from '../validations/components/QueryPickerModal';
import { TestSetFormModal } from './components/TestSetFormModal';
import { useTestSetManagement } from './hooks/useTestSetManagement';

const TEST_SET_COLUMN_WIDTHS = {
  name: 260,
  description: 360,
  itemCount: 100,
  updatedAt: 180,
  actions: 220,
};

export function TestSetManagementPage({
  environment,
  tokens,
  onOpenValidationRun,
  onOpenValidationHistory,
}: {
  environment: Environment;
  tokens: RuntimeSecrets;
  onOpenValidationRun?: (testSetId?: string) => void;
  onOpenValidationHistory?: () => void;
}) {
  const { message } = App.useApp();
  const {
    items,
    total,
    loading,
    selectedTestSetId,
    setSelectedTestSetId,
    setSearch,
    queryPickerOpen,
    setQueryPickerOpen,
    queryPickerLoading,
    queryPickerSearchInput,
    setQueryPickerSearchInput,
    queryPickerSearchKeyword,
    setQueryPickerSearchKeyword,
    queryPickerCategory,
    setQueryPickerCategory,
    queryPickerGroupId,
    setQueryPickerGroupId,
    queryPickerSelectedIds,
    setQueryPickerSelectedIds,
    queryPickerItems,
    queryPickerPage,
    setQueryPickerPage,
    queryPickerPageSize,
    setQueryPickerPageSize,
    queryPickerTotal,
    queryGroups,
    modalOpen,
    setModalOpen,
    editing,
    saving,
    form,
    openCreate,
    openEdit,
    handleSave,
    handleDelete,
    handleClone,
    setQuerySelection,
  } = useTestSetManagement({
    environment,
    tokens,
    message,
  });

  const columns = useMemo(
    () => [
      {
        key: 'name',
        title: '이름',
        dataIndex: 'name',
        width: TEST_SET_COLUMN_WIDTHS.name,
        sorter: (a: ValidationTestSet, b: ValidationTestSet) =>
          String(a.name).localeCompare(String(b.name)),
      },
      {
        key: 'description',
        title: '설명',
        dataIndex: 'description',
        width: TEST_SET_COLUMN_WIDTHS.description,
        ellipsis: true,
        render: (value?: string) => value || '-',
      },
      {
        key: 'itemCount',
        title: '질의 수',
        dataIndex: 'itemCount',
        width: TEST_SET_COLUMN_WIDTHS.itemCount,
        sorter: (a: ValidationTestSet, b: ValidationTestSet) =>
          a.itemCount - b.itemCount,
      },
      {
        key: 'updatedAt',
        title: '수정시각',
        dataIndex: 'updatedAt',
        width: TEST_SET_COLUMN_WIDTHS.updatedAt,
        render: (value?: string) => formatDateTime(value),
        sorter: (a: ValidationTestSet, b: ValidationTestSet) =>
          String(a.updatedAt || '').localeCompare(String(b.updatedAt || '')),
      },
      {
        key: 'actions',
        title: '작업',
        width: TEST_SET_COLUMN_WIDTHS.actions,
        render: (_: unknown, row: ValidationTestSet) => (
          <Space size="small">
            <Button
              onClick={() => {
                void openEdit(row);
              }}
            >
              수정
            </Button>
            <Button
              onClick={() => {
                void handleClone(row.id);
              }}
            >
              복제
            </Button>
            <Popconfirm
              title="테스트 세트를 삭제할까요?"
              onConfirm={() => {
                void handleDelete(row.id);
              }}
            >
              <Button danger>삭제</Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [handleClone, handleDelete, openEdit],
  );

  return (
    <Card className="backoffice-content-card">
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        <Space wrap>
          <Input.Search
            allowClear
            placeholder="테스트 세트 이름 검색"
            onSearch={setSearch}
            style={{ width: 320 }}
            enterButton
          />
          <Button onClick={openCreate}>테스트 세트 생성</Button>
          <Button onClick={onOpenValidationHistory}>질문 결과로 이동</Button>
          <Button
            type="primary"
            disabled={!selectedTestSetId}
            onClick={() => onOpenValidationRun?.(selectedTestSetId)}
          >
            검증 실행으로 이동
          </Button>
        </Space>

        <StandardDataTable
          tableId="validation-test-sets-main"
          initialColumnWidths={TEST_SET_COLUMN_WIDTHS}
          minColumnWidth={100}
          className="query-management-table"
          rowKey="id"
          size="small"
          loading={loading}
          dataSource={items}
          rowSelection={{
            type: 'radio',
            selectedRowKeys: selectedTestSetId ? [selectedTestSetId] : [],
            onChange: (keys) => setSelectedTestSetId(String(keys[0] || '')),
          }}
          pagination={{ total }}
          columns={columns}
        />
      </Space>

      <TestSetFormModal
        open={modalOpen}
        editing={Boolean(editing)}
        saving={saving}
        form={form}
        selectedQueryCount={queryPickerSelectedIds.length}
        onOpenQueryPicker={() => setQueryPickerOpen(true)}
        onResetQuerySelection={() => setQuerySelection([])}
        onCancel={() => setModalOpen(false)}
        onSubmit={() => {
          void handleSave();
        }}
      />

      <QueryPickerModal
        queryPickerOpen={queryPickerOpen}
        setQueryPickerOpen={setQueryPickerOpen}
        queryPickerSaving={saving}
        handleImportQueries={() => {
          setQueryPickerOpen(false);
        }}
        queryPickerSearchInput={queryPickerSearchInput}
        setQueryPickerSearchInput={setQueryPickerSearchInput}
        setQueryPickerSearchKeyword={setQueryPickerSearchKeyword}
        queryPickerSearchKeyword={queryPickerSearchKeyword}
        setQueryPickerPage={setQueryPickerPage}
        queryPickerCategory={queryPickerCategory}
        setQueryPickerCategory={setQueryPickerCategory}
        queryPickerGroupId={queryPickerGroupId}
        setQueryPickerGroupId={setQueryPickerGroupId}
        groups={queryGroups}
        queryPickerSelectedIds={queryPickerSelectedIds}
        queryPickerLoading={queryPickerLoading}
        queryPickerItems={queryPickerItems}
        setQueryPickerSelectedIds={setQueryPickerSelectedIds}
        queryPickerPage={queryPickerPage}
        queryPickerPageSize={queryPickerPageSize}
        setQueryPickerPageSize={setQueryPickerPageSize}
        queryPickerTotal={queryPickerTotal}
      />
    </Card>
  );
}
