import { Form, Input } from 'antd';
import type { FormInstance } from 'antd/es/form';

import { StandardModal } from '../../../components/common/StandardModal';
import type { Environment } from '../../../app/EnvironmentScope';
import type { QueryGroup } from '../../../api/types/validation';
import type { QueryGroupFormValues } from '../hooks/useQueryGroupManagement';

export function QueryGroupFormModal({
  open,
  editing,
  saving,
  form,
  environment,
  onCancel,
  onSave,
}: {
  open: boolean;
  editing: QueryGroup | null;
  saving: boolean;
  form: FormInstance<QueryGroupFormValues>;
  environment: Environment;
  onCancel: () => void;
  onSave: () => void;
}) {
  return (
    <StandardModal
      title={editing ? '그룹 수정' : '그룹 등록'}
      open={open}
      confirmLoading={saving}
      onCancel={onCancel}
      onOk={onSave}
      width={760}
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="groupName"
          label="그룹명"
          rules={[{ required: true, message: '그룹명을 입력해 주세요.' }]}
        >
          <Input placeholder="그룹명을 입력해 주세요." />
        </Form.Item>
        <Form.Item name="description" label="설명">
          <Input.TextArea
            autoSize={{ minRows: 2, maxRows: 4 }}
            placeholder="설명을 입력해 주세요."
          />
        </Form.Item>
      </Form>
    </StandardModal>
  );
}
