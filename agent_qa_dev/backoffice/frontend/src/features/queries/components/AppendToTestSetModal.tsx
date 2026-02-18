import { Button, Form, Select, Space, Typography } from 'antd';

import { StandardModal } from '../../../components/common/StandardModal';

type AppendToTestSetFormValues = {
  testSetId: string;
};

export function AppendToTestSetModal({
  open,
  loading,
  optionsLoading,
  selectedCount,
  options,
  onClose,
  onSubmit,
}: {
  open: boolean;
  loading: boolean;
  optionsLoading: boolean;
  selectedCount: number;
  options: Array<{ label: string; value: string }>;
  onClose: () => void;
  onSubmit: (values: AppendToTestSetFormValues) => void;
}) {
  const [form] = Form.useForm<AppendToTestSetFormValues>();

  return (
    <StandardModal
      title="테스트 세트에 추가"
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
            추가
          </Button>
        </Space>
      }
      destroyOnHidden
    >
      <Form form={form} layout="vertical">
        <Typography.Text type="secondary">선택된 질의 {selectedCount}건을 기존 테스트 세트에 추가합니다.</Typography.Text>
        <Form.Item
          label="대상 테스트 세트"
          name="testSetId"
          style={{ marginTop: 12 }}
          rules={[{ required: true, message: '추가할 테스트 세트를 선택해 주세요.' }]}
        >
          <Select
            showSearch
            loading={optionsLoading}
            placeholder="테스트 세트를 선택하세요."
            optionFilterProp="label"
            options={options}
          />
        </Form.Item>
      </Form>
    </StandardModal>
  );
}

export type { AppendToTestSetFormValues };
