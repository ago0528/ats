import { Button, Form, Input, Space, Typography } from 'antd';

import { StandardModal } from '../../../components/common/StandardModal';

type CreateTestSetFromSelectionFormValues = {
  name: string;
  description: string;
};

export function CreateTestSetFromSelectionModal({
  open,
  loading,
  selectedCount,
  onClose,
  onSubmit,
}: {
  open: boolean;
  loading: boolean;
  selectedCount: number;
  onClose: () => void;
  onSubmit: (values: CreateTestSetFromSelectionFormValues) => void;
}) {
  const [form] = Form.useForm<CreateTestSetFromSelectionFormValues>();

  return (
    <StandardModal
      title="테스트 세트 생성"
      open={open}
      width={680}
      onCancel={onClose}
      footer={
        <Space>
          <Button onClick={onClose} disabled={loading}>취소</Button>
          <Button
            type="primary"
            loading={loading}
            onClick={() => {
              void form.validateFields().then((values) => onSubmit(values));
            }}
          >
            생성
          </Button>
        </Space>
      }
      destroyOnHidden
    >
      <Form form={form} layout="vertical" initialValues={{ name: '', description: '' }}>
        <Typography.Text type="secondary">선택된 질의 {selectedCount}건으로 테스트 세트를 생성합니다.</Typography.Text>
        <Form.Item
          label="이름"
          name="name"
          style={{ marginTop: 12 }}
          rules={[{ required: true, message: '테스트 세트 이름을 입력해 주세요.' }]}
        >
          <Input placeholder="예: 2026-02 배치 검증 세트" maxLength={120} />
        </Form.Item>
        <Form.Item label="설명" name="description">
          <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} />
        </Form.Item>
      </Form>
    </StandardModal>
  );
}

export type { CreateTestSetFromSelectionFormValues };
