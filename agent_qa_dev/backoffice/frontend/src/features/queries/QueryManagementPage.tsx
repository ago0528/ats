import { DownloadOutlined, UploadOutlined } from '@ant-design/icons';
import { App, Button, Card, Popconfirm, Space, Tag, Tooltip, Typography, Upload } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useMemo } from 'react';

import type { ValidationQuery } from '../../api/types/validation';
import type { Environment } from '../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../app/types';
import { QueryCategoryTag } from '../../components/common/QueryCategoryTag';
import { StandardDataTable } from '../../components/common/StandardDataTable';
import { StandardModal } from '../../components/common/StandardModal';
import { formatDateYYYYMMDD } from '../../shared/utils/dateTime';
import { DEFAULT_COLUMN_WIDTHS, TABLE_ROW_SELECTION_WIDTH } from './constants';
import { AppendToTestSetModal } from './components/AppendToTestSetModal';
import { BulkDeleteModal } from './components/BulkDeleteModal';
import { BulkUploadGroupConfirmModal } from './components/BulkUploadGroupConfirmModal';
import { BulkUploadModal } from './components/BulkUploadModal';
import { CreateTestSetFromSelectionModal } from './components/CreateTestSetFromSelectionModal';
import { QueryFilters } from './components/QueryFilters';
import { QueryFormModal } from './components/QueryFormModal';
import { useQueryManagement } from './hooks/useQueryManagement';
import type { BulkUpdatePreviewRow } from './types';

const BULK_UPDATE_STATUS_LABEL: Record<string, string> = {
  'planned-update': '업데이트 예정',
  unchanged: '변경 없음',
  'unmapped-query-id': '쿼리 ID 미매핑',
  'missing-query-id': '쿼리 ID 누락',
  'duplicate-query-id': '쿼리 ID 중복',
};

const BULK_UPDATE_STATUS_COLOR: Record<string, string> = {
  'planned-update': 'blue',
  unchanged: 'default',
  'unmapped-query-id': 'orange',
  'missing-query-id': 'red',
  'duplicate-query-id': 'red',
};

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
    bulkUpdateModalOpen,
    bulkUpdateFiles,
    bulkUpdatePreviewRows,
    bulkUpdatePreviewTotal,
    bulkUpdatePreviewEmptyText,
    bulkUpdatePreviewSummary,
    bulkUpdateGroupConfirmOpen,
    bulkUpdatePendingGroupNames,
    bulkUpdatePendingGroupRows,
    bulkUpdateUnmappedConfirmOpen,
    bulkUpdatePendingUnmappedCount,
    bulkUpdating,
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
    openBulkUpdateModal,
    closeBulkUpdateModal,
    closeBulkUpdateGroupConfirmModal,
    closeBulkUpdateUnmappedConfirmModal,
    handleBulkUpdateFileChange,
    handleBulkUpdate,
    confirmBulkUpdateWithGroupCreation,
    confirmBulkUpdateWithUnmappedSkip,
    handleDownloadBulkUpdateCsv,
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
        key: 'testSetUsage',
        title: '테스트 세트',
        width: DEFAULT_COLUMN_WIDTHS.testSetUsage,
        render: (_, row: ValidationQuery) => {
          const usageCount = row.testSetUsage?.count || 0;
          const usageNames = row.testSetUsage?.testSetNames || [];
          if (usageCount <= 0) return '0';
          return (
            <Tooltip title={usageNames.length > 0 ? usageNames.join(', ') : '-'}>
              <Typography.Text style={{ cursor: 'help' }}>{usageCount}</Typography.Text>
            </Tooltip>
          );
        },
      },
      {
        key: 'createdAt',
        title: '등록일자',
        width: DEFAULT_COLUMN_WIDTHS.createdAt,
        render: (_, row: ValidationQuery) => formatDateYYYYMMDD(row.createdAt),
      },
      {
        key: 'updatedAt',
        title: '최근 수정일자',
        width: DEFAULT_COLUMN_WIDTHS.updatedAt,
        render: (_, row: ValidationQuery) => formatDateYYYYMMDD(row.updatedAt),
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

  const bulkUpdatePreviewColumns = useMemo<ColumnsType<BulkUpdatePreviewRow>>(
    () => [
      { key: 'rowNo', title: '행', dataIndex: 'rowNo', width: 80 },
      { key: 'queryId', title: '쿼리 ID', dataIndex: 'queryId', width: 170, ellipsis: true },
      { key: 'queryText', title: '질의', dataIndex: 'queryText', width: 320, ellipsis: true },
      {
        key: 'status',
        title: '상태',
        dataIndex: 'status',
        width: 140,
        render: (value: string) => (
          <Tag color={BULK_UPDATE_STATUS_COLOR[value] || 'default'}>{BULK_UPDATE_STATUS_LABEL[value] || value}</Tag>
        ),
      },
      {
        key: 'changedFields',
        title: '변경 필드',
        dataIndex: 'changedFields',
        width: 300,
        ellipsis: true,
        render: (value: string[]) => (value.length > 0 ? value.join(', ') : '-'),
      },
    ],
    [],
  );

  return (
    <Card className="backoffice-content-card">
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
          <Button onClick={openBulkUpdateModal}>대규모 업데이트</Button>
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

      <StandardModal
        title="대규모 업데이트"
        open={bulkUpdateModalOpen}
        width={920}
        onCancel={closeBulkUpdateModal}
        footer={(
          <Space>
            <Button onClick={closeBulkUpdateModal} disabled={bulkUpdating}>
              취소
            </Button>
            <Button type="primary" loading={bulkUpdating} disabled={!bulkUpdateFiles[0]?.originFileObj} onClick={() => { void handleBulkUpdate(); }}>
              업데이트
            </Button>
          </Space>
        )}
      >
        <div style={{ width: '100%', padding: 0, display: 'flex', flexDirection: 'column', gap: 16, overflowY: 'auto' }}>
          <Typography.Text type="secondary">현재 필터 결과의 질의를 CSV로 내려받아 수정 후 업로드하세요.</Typography.Text>

          <div>
            <Typography.Text>현재 질의 CSV 다운로드</Typography.Text>
            <div style={{ marginTop: 8 }}>
              <Button icon={<DownloadOutlined />} onClick={() => { void handleDownloadBulkUpdateCsv(); }} disabled={bulkUpdating}>
                CSV 다운로드
              </Button>
            </div>
          </div>

          <div>
            <Typography.Text>CSV 업로드</Typography.Text>
            <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <Upload
                fileList={bulkUpdateFiles}
                beforeUpload={() => false}
                onChange={({ fileList }) => {
                  void handleBulkUpdateFileChange(fileList);
                }}
                maxCount={1}
                accept=".csv,.xlsx,.xls"
                showUploadList={false}
              >
                <Button icon={<UploadOutlined />}>CSV 업로드</Button>
              </Upload>
              {bulkUpdateFiles[0]?.name ? <Typography.Text type="secondary">{bulkUpdateFiles[0].name}</Typography.Text> : null}
            </div>
          </div>

          <div>
            <Typography.Text>업로드한 질의 미리보기</Typography.Text>
            <div style={{ marginTop: 8 }}>
              {bulkUpdateFiles.length === 0 ? (
                <Typography.Text type="secondary">질의를 업로드해주세요.</Typography.Text>
              ) : (
                <Space direction="vertical" style={{ width: '100%' }} size={8}>
                  <StandardDataTable
                    tableId="query-management-bulk-update-preview"
                    className="query-management-table"
                    rowKey="key"
                    size="small"
                    columns={bulkUpdatePreviewColumns}
                    dataSource={bulkUpdatePreviewRows}
                    tableLayout="fixed"
                    pagination={false}
                    scroll={{ x: 1120, y: 300 }}
                    locale={{ emptyText: bulkUpdatePreviewEmptyText }}
                  />
                  {bulkUpdatePreviewSummary ? (
                    <Typography.Text type="secondary">
                      총 {bulkUpdatePreviewSummary.totalRows}건 중 업데이트 예정 {bulkUpdatePreviewSummary.plannedUpdateCount}건, 변경 없음 {bulkUpdatePreviewSummary.unchangedCount}건
                    </Typography.Text>
                  ) : null}
                  {bulkUpdatePreviewSummary && bulkUpdatePreviewSummary.unmappedQueryCount > 0 ? (
                    <Typography.Text type="warning">
                      쿼리 ID가 수정된 항목이 있어요. 쿼리 ID가 수정된 항목은 업데이트되지 않아요.
                    </Typography.Text>
                  ) : null}
                </Space>
              )}
            </div>
          </div>
        </div>
      </StandardModal>

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

      <BulkUploadGroupConfirmModal
        open={bulkUpdateGroupConfirmOpen}
        groupNames={bulkUpdatePendingGroupNames}
        groupRows={bulkUpdatePendingGroupRows}
        loading={bulkUpdating}
        title="그룹 생성 확인"
        description="업데이트 중 아래 그룹을 새로 생성합니다. 계속할까요?"
        confirmText="생성 후 업데이트"
        onClose={closeBulkUpdateGroupConfirmModal}
        onConfirm={() => {
          void confirmBulkUpdateWithGroupCreation();
        }}
      />

      <StandardModal
        title="쿼리 ID 미매핑 확인"
        open={bulkUpdateUnmappedConfirmOpen}
        width={560}
        onCancel={closeBulkUpdateUnmappedConfirmModal}
        footer={(
          <Space>
            <Button onClick={closeBulkUpdateUnmappedConfirmModal} disabled={bulkUpdating}>
              취소
            </Button>
            <Button type="primary" loading={bulkUpdating} onClick={() => { void confirmBulkUpdateWithUnmappedSkip(); }}>
              업데이트
            </Button>
          </Space>
        )}
      >
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Typography.Text>
            쿼리 ID가 매핑되지 않은 항목 {bulkUpdatePendingUnmappedCount}건은 업데이트에서 제외됩니다.<br />
            쿼리 ID가 수정된 항목은 업데이트되지 않아요.
          </Typography.Text>
        </Space>
      </StandardModal>

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
