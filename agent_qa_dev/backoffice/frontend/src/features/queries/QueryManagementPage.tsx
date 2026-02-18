import { App, Button, Card, Popconfirm, Space, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useMemo } from 'react';

import type { ValidationQuery } from '../../api/types/validation';
import type { Environment } from '../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../app/types';
import { QueryCategoryTag } from '../../components/common/QueryCategoryTag';
import { StandardDataTable } from '../../components/common/StandardDataTable';
import { formatDateTime, formatShortDate } from '../../shared/utils/dateTime';
import { DEFAULT_COLUMN_WIDTHS, TABLE_ROW_SELECTION_WIDTH } from './constants';
import { AppendToTestSetModal } from './components/AppendToTestSetModal';
import { BulkDeleteModal } from './components/BulkDeleteModal';
import { BulkUploadGroupConfirmModal } from './components/BulkUploadGroupConfirmModal';
import { BulkUploadModal } from './components/BulkUploadModal';
import { CreateTestSetFromSelectionModal } from './components/CreateTestSetFromSelectionModal';
import { QueryFilters } from './components/QueryFilters';
import { QueryFormModal } from './components/QueryFormModal';
import { useQueryManagement } from './hooks/useQueryManagement';

export function QueryManagementPage({
  environment,
  tokens,
}: {
  environment: Environment;
  tokens: RuntimeSecrets;
}) {
  const { message } = App.useApp();
  const {
    groups,
    items,
    total,
    loading,
    category,
    groupId,
    selectionMode,
    isFilteredSelectionLocked,
    selectedCount,
    filteredSelectionTotal,
    filteredDeselectedCount,
    tableSelectedRowKeys,
    canBulkDelete,
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
    createTestSetModalOpen,
    creatingTestSet,
    appendToTestSetModalOpen,
    appendingToTestSet,
    testSetOptionsLoading,
    testSetOptions,
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
    handleRowSelectionChange,
    handleSelectAllFiltered,
    clearQuerySelection,
    handleOpenCreateTestSetModal,
    handleOpenAppendToTestSetModal,
    handleCreateTestSetFromSelection,
    handleAppendToTestSet,
    closeCreateTestSetModal,
    closeAppendToTestSetModal,
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
          <Button onClick={handleSelectAllFiltered} disabled={total === 0}>
            전체 선택(필터 결과 {total}건)
          </Button>
          <Button onClick={clearQuerySelection} disabled={selectedCount === 0}>
            선택 해제
          </Button>
          <Button danger disabled={!canBulkDelete} onClick={() => setBulkDeleteModalOpen(true)}>
            삭제
          </Button>
          <Button type="primary" onClick={handleOpenCreateTestSetModal} disabled={selectedCount === 0}>
            테스트 세트 만들기
          </Button>
          <Button onClick={handleOpenAppendToTestSetModal} disabled={selectedCount === 0}>
            테스트 세트에 추가
          </Button>
        </Space>

        {selectedCount > 0 ? (
          <Typography.Text type={isFilteredSelectionLocked ? 'warning' : 'secondary'}>
            {selectionMode === 'filtered'
              ? `필터 결과 전체 선택 ${filteredSelectionTotal}건 (제외 ${filteredDeselectedCount}건, 현재 ${selectedCount}건)`
              : `선택된 질의 ${selectedCount}건`}
            {isFilteredSelectionLocked ? ' · 필터가 변경되어 선택 컨텍스트가 잠겼습니다. 선택 해제 후 다시 선택해 주세요.' : ''}
          </Typography.Text>
        ) : null}

        <StandardDataTable
          tableId="query-management-main"
          initialColumnWidths={DEFAULT_COLUMN_WIDTHS}
          minColumnWidth={120}
          scrollXPadding={TABLE_ROW_SELECTION_WIDTH}
          className="query-management-table"
          rowSelection={{
            preserveSelectedRowKeys: true,
            selectedRowKeys: tableSelectedRowKeys,
            hideSelectAll: isFilteredSelectionLocked,
            getCheckboxProps: () => ({ disabled: isFilteredSelectionLocked }),
            onChange: handleRowSelectionChange,
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
        selectedCount={tableSelectedRowKeys.length}
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

      <CreateTestSetFromSelectionModal
        open={createTestSetModalOpen}
        loading={creatingTestSet}
        selectedCount={selectedCount}
        onClose={closeCreateTestSetModal}
        onSubmit={(values) => {
          void handleCreateTestSetFromSelection(values);
        }}
      />

      <AppendToTestSetModal
        open={appendToTestSetModalOpen}
        loading={appendingToTestSet}
        optionsLoading={testSetOptionsLoading}
        selectedCount={selectedCount}
        options={testSetOptions}
        onClose={closeAppendToTestSetModal}
        onSubmit={(values) => {
          void handleAppendToTestSet(values);
        }}
      />
    </Card>
  );
}
