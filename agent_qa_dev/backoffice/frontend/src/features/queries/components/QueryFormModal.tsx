import { Button, Form, Input, Select, Space } from 'antd';
import type { FormInstance } from 'antd/es/form';

import type { QueryCategory, QueryGroup, ValidationQuery } from '../../../api/types/validation';
import { StandardModal } from '../../../components/common/StandardModal';
import { CATEGORY_OPTIONS } from '../constants';
import type { QueryFormValues } from '../hooks/useQueryManagement';

export function QueryFormModal({
  open,
  editing,
  saving,
  form,
  groups,
  onClose,
  onSave,
}: {
  open: boolean;
  editing: ValidationQuery | null;
  saving: boolean;
  form: FormInstance<QueryFormValues>;
  groups: QueryGroup[];
  onClose: () => void;
  onSave: () => void;
}) {
  return (
    <StandardModal
      title={editing ? '질의 수정' : '질의 등록'}
      open={open}
      width={820}
      onCancel={onClose}
      footer={
        <Space>
          <Button onClick={onClose}>취소</Button>
          <Button type="primary" loading={saving} onClick={onSave}>
            {editing ? '수정하기' : '등록하기'}
          </Button>
        </Space>
      }
    >
      <Form form={form} layout="vertical">
        <Space style={{ width: '100%' }} size={12}>
          <Form.Item
            name="category"
            label="카테고리"
            style={{ minWidth: 220 }}
            rules={[{ required: true, message: '카테고리를 선택해 주세요.' }]}
          >
            <Select options={CATEGORY_OPTIONS} />
          </Form.Item>
          <Form.Item name="groupId" label="그룹" style={{ minWidth: 220 }}>
            <Select allowClear options={groups.map((group) => ({ label: group.groupName, value: group.id }))} />
          </Form.Item>
        </Space>
        <Form.Item name="queryText" label="질의" rules={[{ required: true, message: '질의를 입력해 주세요.' }]}>
          <Input.TextArea autoSize={{ minRows: 1, maxRows: 2 }} />
        </Form.Item>
        <Form.Item name="expectedResult" label="기대 결과">
          <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} />
        </Form.Item>
      </Form>
    </StandardModal>
  );
}
