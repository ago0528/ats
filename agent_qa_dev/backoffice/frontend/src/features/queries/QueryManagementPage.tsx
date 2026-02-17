import { App, Button, Card, Popconfirm, Space } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useMemo } from 'react';

import type { ValidationQuery } from '../../api/types/validation';
import type { Environment } from '../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../app/types';
import { QueryCategoryTag } from '../../components/common/QueryCategoryTag';
import { StandardDataTable } from '../../components/common/StandardDataTable';
import { formatDateTime, formatShortDate } from '../../shared/utils/dateTime';
import { DEFAULT_COLUMN_WIDTHS, TABLE_ROW_SELECTION_WIDTH } from './constants';
import { BulkDeleteModal } from './components/BulkDeleteModal';
import { BulkUploadGroupConfirmModal } from './components/BulkUploadGroupConfirmModal';
import { BulkUploadModal } from './components/BulkUploadModal';
import { QueryFilters } from './components/QueryFilters';
import { QueryFormModal } from './components/QueryFormModal';
import { useQueryManagement } from './hooks/useQueryManagement';

export function QueryManagementPage({
  environment,
  tokens,
  onCreateTestSetFromQueries,
}: {
  environment: Environment;
  tokens: RuntimeSecrets;
  onCreateTestSetFromQueries?: (queryIds: string[]) => void;
}) {
  const { message } = App.useApp();
  const {
    groups,
    items,
    total,
    loading,
    category,
    groupId,
    selectedRowKeys,
    setSelectedRowKeys,
    modalOpen,
    setModalOpen,
    editing,
    saving,
    form,
    bulkUploadModalOpen,
    bulkUploadFiles,
    bulkUploadPreviewRows,
    bulkUploadPreviewTotal,
    bulkUploadPreviewEmptyText,
    bulkUploadGroupConfirmOpen,
    bulkUploadPendingGroupNames,
    bulkUploadPendingGroupRows,
    bulkUploading,
    bulkDeleteModalOpen,
    setBulkDeleteModalOpen,
    bulkDeleting,
    currentPage,
    pageSize,
    setCurrentPage,
    setPageSize,
    openCreate,
    openEdit,
    handleSave,
    handleDelete,
    openBulkUploadModal,
    closeBulkUploadModal,
    closeBulkUploadGroupConfirmModal,
    handleBulkUploadFileChange,
    handleBulkUpload,
    confirmBulkUploadWithGroupCreation,
    handleBulkDelete,
    handleSearch,
    handleCategoryChange,
    handleGroupChange,
  } = useQueryManagement({ environment, tokens, message });

  const columns = useMemo<ColumnsType<ValidationQuery>>(
    () => [
      {
        key: 'queryId',
        title: '쿼리 ID',
        dataIndex: 'id',
        width: DEFAULT_COLUMN_WIDTHS.queryId,
        ellipsis: true,
      },
      {
        key: 'queryText',
        title: '질의',
        dataIndex: 'queryText',
        ellipsis: true,
        width: DEFAULT_COLUMN_WIDTHS.queryText,
      },
      {
        key: 'category',
        title: '카테고리',
        dataIndex: 'category',
        width: DEFAULT_COLUMN_WIDTHS.category,
        render: (value: string) => <QueryCategoryTag category={value} />,
      },
      {
        key: 'groupName',
        title: '그룹',
        dataIndex: 'groupName',
        width: DEFAULT_COLUMN_WIDTHS.groupName,
        render: (value?: string) => value || '-',
      },
      {
        key: 'createdAt',
        title: '등록일자',
        width: DEFAULT_COLUMN_WIDTHS.createdAt,
        render: (_, row: ValidationQuery) => formatShortDate(row.createdAt),
      },
      {
        key: 'latestRun',
        title: '최근 검증',
        width: DEFAULT_COLUMN_WIDTHS.latestRun,
        render: (_, row: ValidationQuery) => formatDateTime(row.latestRunSummary?.executedAt),
      },
      {
        key: 'latestResult',
        title: '최근 결과',
        width: DEFAULT_COLUMN_WIDTHS.latestResult,
        render: (_, row: ValidationQuery) =>
          `${row.latestRunSummary?.logicResult || '-'} / ${row.latestRunSummary?.llmStatus || '-'}`,
      },
      {
        key: 'actions',
        title: '작업',
        width: DEFAULT_COLUMN_WIDTHS.actions,
        render: (_, row: ValidationQuery) => (
          <Space size="small">
            <Button onClick={() => openEdit(row)}>수정</Button>
            <Popconfirm
              title="질의를 삭제할까요?"
              okText="삭제"
              cancelText="취소"
              onConfirm={() => handleDelete(row.id)}
            >
              <Button danger>삭제</Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [handleDelete, openEdit],
  );

  return (
    <Card className="backoffice-content-card" title="질의 관리">
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        <QueryFilters
          category={category}
          groupId={groupId}
          groups={groups}
          onSearch={handleSearch}
          onCategoryChange={handleCategoryChange}
          onGroupChange={handleGroupChange}
        />

        <Space wrap>
          <Button onClick={openBulkUploadModal}>대규모 업로드</Button>
          <Button onClick={openCreate}>질의 등록</Button>
          <Button danger disabled={selectedRowKeys.length === 0} onClick={() => setBulkDeleteModalOpen(true)}>
            삭제
          </Button>
          <Button
            type="primary"
            onClick={() => onCreateTestSetFromQueries?.(selectedRowKeys.map(String))}
            disabled={selectedRowKeys.length === 0}
          >
            테스트 세트 만들기
          </Button>
        </Space>

        <StandardDataTable
          tableId="query-management-main"
          initialColumnWidths={DEFAULT_COLUMN_WIDTHS}
          minColumnWidth={120}
          scrollXPadding={TABLE_ROW_SELECTION_WIDTH}
          className="query-management-table"
          rowSelection={{
            preserveSelectedRowKeys: true,
            selectedRowKeys,
            onChange: (keys) => setSelectedRowKeys(keys.map(String)),
          }}
          rowKey="id"
          size="small"
          loading={loading}
          dataSource={items}
          tableLayout="fixed"
          pagination={{
            current: currentPage,
            pageSize,
            total,
            onChange: (page, nextPageSize) => {
              if (nextPageSize !== pageSize) {
                setPageSize(nextPageSize);
                setCurrentPage(1);
                return;
              }
              setCurrentPage(page);
            },
          }}
          columns={columns}
        />
      </Space>

      <BulkUploadModal
        open={bulkUploadModalOpen}
        files={bulkUploadFiles}
        previewRows={bulkUploadPreviewRows}
        previewTotal={bulkUploadPreviewTotal}
        previewEmptyText={bulkUploadPreviewEmptyText}
        uploading={bulkUploading}
        onClose={closeBulkUploadModal}
        onFilesChange={(files) => {
          void handleBulkUploadFileChange(files);
        }}
        onUpload={() => {
          void handleBulkUpload();
        }}
      />

      <BulkUploadGroupConfirmModal
        open={bulkUploadGroupConfirmOpen}
        groupNames={bulkUploadPendingGroupNames}
        groupRows={bulkUploadPendingGroupRows}
        loading={bulkUploading}
        onClose={closeBulkUploadGroupConfirmModal}
        onConfirm={() => {
          void confirmBulkUploadWithGroupCreation();
        }}
      />

      <BulkDeleteModal
        open={bulkDeleteModalOpen}
        selectedCount={selectedRowKeys.length}
        deleting={bulkDeleting}
        onClose={() => setBulkDeleteModalOpen(false)}
        onConfirm={() => {
          void handleBulkDelete();
        }}
      />

      <QueryFormModal
        open={modalOpen}
        editing={editing}
        saving={saving}
        form={form}
        groups={groups}
        onClose={() => setModalOpen(false)}
        onSave={() => {
          void handleSave();
        }}
      />
    </Card>
  );
}
