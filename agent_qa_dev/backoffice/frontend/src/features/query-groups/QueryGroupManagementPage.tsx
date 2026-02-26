import { App, Button, Card, Input, Popconfirm, Space, Tooltip } from 'antd';
import { useMemo } from 'react';

import type { QueryGroup } from '../../api/types/validation';
import type { Environment } from '../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../app/types';
import { StandardDataTable } from '../../components/common/StandardDataTable';
import { QueryGroupFormModal } from './components/QueryGroupFormModal';
import { useQueryGroupManagement } from './hooks/useQueryGroupManagement';

const QUERY_GROUP_INITIAL_COLUMN_WIDTHS = {
  groupName: 260,
  description: 420,
  queryCount: 100,
  actions: 180,
};

export function QueryGroupManagementPage({ environment, tokens }: { environment: Environment; tokens: RuntimeSecrets }) {
  const { message } = App.useApp();
  const {
    items,
    total,
    loading,
    setSearch,
    modalOpen,
    setModalOpen,
    editing,
    saving,
    form,
    openCreate,
    openEdit,
    handleSave,
    handleDelete,
  } = useQueryGroupManagement({ environment, tokens, message });

  const columns = useMemo(
    () => [
      { key: 'groupName', title: '그룹명', dataIndex: 'groupName', width: QUERY_GROUP_INITIAL_COLUMN_WIDTHS.groupName, ellipsis: true },
      { key: 'description', title: '설명', dataIndex: 'description', width: QUERY_GROUP_INITIAL_COLUMN_WIDTHS.description, ellipsis: true },
      { key: 'queryCount', title: '질의 수', dataIndex: 'queryCount', width: QUERY_GROUP_INITIAL_COLUMN_WIDTHS.queryCount, ellipsis: true },
      {
        key: 'actions',
        title: '작업',
        width: QUERY_GROUP_INITIAL_COLUMN_WIDTHS.actions,
        ellipsis: true,
        render: (_: unknown, row: QueryGroup) => (
          <Space size="small">
            <Button onClick={() => openEdit(row)}>수정</Button>
            {row.queryCount > 0 ? (
              <Tooltip title="질의가 연결된 그룹은 삭제할 수 없습니다. 질의를 다른 그룹으로 옮기거나 삭제한 뒤 다시 시도하세요.">
                <Button danger disabled>삭제</Button>
              </Tooltip>
            ) : (
              <Popconfirm title="그룹을 삭제할까요?" onConfirm={() => { void handleDelete(row.id); }}>
                <Button danger>삭제</Button>
              </Popconfirm>
            )}
          </Space>
        ),
      },
    ],
    [handleDelete, openEdit],
  );

  return (
    <Card className="backoffice-content-card">
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        <Space wrap>
          <Input.Search allowClear placeholder="그룹명 검색" onSearch={setSearch} style={{ width: 300 }} enterButton />
          <Button type="primary" onClick={openCreate}>그룹 등록</Button>
        </Space>
        <StandardDataTable
          tableId="query-groups-main"
          initialColumnWidths={QUERY_GROUP_INITIAL_COLUMN_WIDTHS}
          minColumnWidth={100}
          className="query-management-table"
          rowKey="id"
          size="small"
          loading={loading}
          dataSource={items}
          pagination={{ total }}
          columns={columns}
        />
      </Space>
      <QueryGroupFormModal
        open={modalOpen}
        editing={editing}
        saving={saving}
        form={form}
        environment={environment}
        onCancel={() => setModalOpen(false)}
        onSave={handleSave}
      />
    </Card>
  );
}
