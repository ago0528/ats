import { Button, Form, Input, InputNumber, Select, Space, Typography } from 'antd';
import type { FormInstance } from 'antd/es/form';

import { StandardModal } from '../../../components/common/StandardModal';
import { CONTEXT_SAMPLE } from '../../../shared/utils/validationConfig';
import {
  AGENT_MODE_OPTIONS,
  EVAL_MODEL_OPTIONS,
} from '../../validations/constants';
import type { TestSetFormValues } from '../utils/testSetForm';

export function TestSetFormModal({
  open,
  editing,
  saving,
  form,
  selectedQueryCount,
  onOpenQueryPicker,
  onResetQuerySelection,
  onCancel,
  onSubmit,
}: {
  open: boolean;
  editing: boolean;
  saving: boolean;
  form: FormInstance<TestSetFormValues>;
  selectedQueryCount: number;
  onOpenQueryPicker: () => void;
  onResetQuerySelection: () => void;
  onCancel: () => void;
  onSubmit: () => void;
}) {
  return (
    <StandardModal
      open={open}
      title={editing ? '테스트 세트 수정' : '테스트 세트 생성'}
      cancelText="취소"
      onCancel={onCancel}
      onOk={onSubmit}
      okText={editing ? '수정' : '생성'}
      confirmLoading={saving}
      width={760}
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        className="standard-modal-field-stack"
      >
        <Form.Item
          label="이름"
          name="name"
          rules={[{ required: true, message: '이름을 입력해 주세요.' }]}
        >
          <Input />
        </Form.Item>
        <Form.Item label="설명" name="description">
          <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} />
        </Form.Item>
        <Form.Item
          label="질의 선택"
          rules={[{ required: true, message: '필수 항목입니다.' }]}
        >
          <Space
            wrap
            style={{ width: '100%', justifyContent: 'space-between' }}
          >
            <Typography.Text type="secondary">
              선택 질의 {selectedQueryCount}개
            </Typography.Text>
            <Space>
              <Button onClick={onOpenQueryPicker}>질의 목록에서 선택</Button>
              <Button onClick={onResetQuerySelection}>초기화</Button>
            </Space>
          </Space>
        </Form.Item>
        <Form.Item
          label="에이전트 모드"
          name="agentId"
          style={{ flex: 1 }}
          rules={[{ required: true, message: '필수 항목입니다.' }]}
        >
          <Select options={[...AGENT_MODE_OPTIONS]} />
        </Form.Item>
        <Form.Item
          label="평가 모델"
          name="evalModel"
          style={{ flex: 1 }}
          rules={[{ required: true, message: '필수 항목입니다.' }]}
        >
          <Select options={[...EVAL_MODEL_OPTIONS]} />
        </Form.Item>
        <Space style={{ width: '100%' }} wrap>
          <Form.Item
            label="반복 수"
            name="repeatInConversation"
            style={{ flex: 1 }}
            rules={[{ required: true, message: '필수 항목입니다.' }]}
          >
            <InputNumber min={1} />
          </Form.Item>
          <Form.Item
            label="채팅방 수"
            name="conversationRoomCount"
            style={{ flex: 1 }}
            extra="채팅방 단위로 순차 실행됩니다. A 방 완료 후 B 방이 시작됩니다."
            rules={[{ required: true, message: '필수 항목입니다.' }]}
          >
            <InputNumber min={1} />
          </Form.Item>
          <Form.Item
            label="동시 실행 수"
            name="agentParallelCalls"
            style={{ flex: 1 }}
            extra="각 채팅방 내 질의를 N개씩 병렬 처리합니다."
            rules={[{ required: true, message: '필수 항목입니다.' }]}
          >
            <InputNumber min={1} />
          </Form.Item>
          <Form.Item
            label="타임아웃(ms)"
            name="timeoutMs"
            style={{ flex: 1 }}
            rules={[{ required: true, message: '필수 항목입니다.' }]}
          >
            <InputNumber min={1000} />
          </Form.Item>
        </Space>
        <Form.Item
          label="Context"
          name="contextJson"
          extra="API 호출 context에 전달할 JSON"
        >
          <Input.TextArea
            autoSize={{ minRows: 4, maxRows: 6 }}
            placeholder={CONTEXT_SAMPLE}
          />
        </Form.Item>
      </Form>
    </StandardModal>
  );
}
