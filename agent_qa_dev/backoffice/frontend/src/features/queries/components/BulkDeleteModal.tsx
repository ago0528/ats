import { Button, Space, Typography } from 'antd';

import { StandardModal } from '../../../components/common/StandardModal';

export function BulkDeleteModal({
  open,
  selectedCount,
  deleting,
  onClose,
  onConfirm,
}: {
  open: boolean;
  selectedCount: number;
  deleting: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <StandardModal
      title="질의 삭제"
      open={open}
      width={420}
      onCancel={() => {
        if (!deleting) {
          onClose();
        }
      }}
      footer={
        <Space>
          <Button onClick={onClose} disabled={deleting}>
            취소
          </Button>
          <Button danger type="primary" loading={deleting} onClick={onConfirm}>
            삭제
          </Button>
        </Space>
      }
    >
      <Typography.Text>{`${selectedCount}개의 질의를 삭제하시겠어요?`}</Typography.Text>
    </StandardModal>
  );
}
