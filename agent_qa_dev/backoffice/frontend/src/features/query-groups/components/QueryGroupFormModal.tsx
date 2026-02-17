import { Form, Input, Modal, Typography } from 'antd';
import type { FormInstance } from 'antd/es/form';

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
    <Modal
      title={editing ? '그룹 수정' : '그룹 등록'}
      open={open}
      confirmLoading={saving}
      onCancel={onCancel}
      onOk={onSave}
      width={760}
    >
      <Form form={form} layout="vertical">
        <Form.Item name="groupName" label="그룹명" rules={[{ required: true, message: '그룹명을 입력해 주세요.' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="description" label="설명">
          <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} />
        </Form.Item>
        <Form.Item name="defaultTargetAssistant" label="기본 대상 어시스턴트">
          <Input placeholder="예: ORCHESTRATOR_WORKER_V3" />
        </Form.Item>
        <Form.Item name="llmEvalCriteriaDefault" label="기본 LLM 평가기준(JSON)">
          <Input.TextArea
            autoSize={{ minRows: 6, maxRows: 12 }}
            placeholder='{"version":1,"metrics":[{"key":"accuracy","weight":0.4}]}'
          />
        </Form.Item>
      </Form>
      <Typography.Text type="secondary">환경: {environment}</Typography.Text>
    </Modal>
  );
}
