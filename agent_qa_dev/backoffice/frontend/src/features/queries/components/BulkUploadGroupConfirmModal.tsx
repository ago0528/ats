import { Button, Space, Tag, Typography } from 'antd';

import { StandardModal } from '../../../components/common/StandardModal';

export function BulkUploadGroupConfirmModal({
  open,
  groupNames,
  groupRows,
  loading,
  title = '그룹 생성 확인',
  description = '업로드 중 아래 그룹을 새로 생성합니다. 계속할까요?',
  confirmText = '생성 후 업로드',
  onClose,
  onConfirm,
}: {
  open: boolean;
  groupNames: string[];
  groupRows: number[];
  loading: boolean;
  title?: string;
  description?: string;
  confirmText?: string;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <StandardModal
      title={title}
      open={open}
      width={560}
      onCancel={onClose}
      footer={
        <Space>
          <Button onClick={onClose} disabled={loading}>
            취소
          </Button>
          <Button type="primary" loading={loading} onClick={onConfirm}>
            {confirmText}
          </Button>
        </Space>
      }
    >
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Typography.Text>{description}</Typography.Text>
        {groupRows.length > 0 ? (
          <Typography.Text type="secondary">감지된 행: {groupRows.join(', ')}</Typography.Text>
        ) : null}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {groupNames.map((groupName) => (
            <Tag key={groupName} color="blue">
              {groupName}
            </Tag>
          ))}
        </div>
      </Space>
    </StandardModal>
  );
}
