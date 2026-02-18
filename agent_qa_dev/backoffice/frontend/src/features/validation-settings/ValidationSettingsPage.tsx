import { useEffect, useState } from 'react';
import { App, Button, Form, Input, InputNumber, Select, Typography } from 'antd';

import { ENV_OPTIONS, type Environment } from '../../app/EnvironmentScope';
import { getValidationSettings, updateValidationSettings } from '../../api/validation';
import type { RuntimeSecrets } from '../../app/types';
import {
  STANDARD_PAGE_SIZE_LIMIT_MIN,
  normalizeStandardPageSizeLimit,
} from '../../components/common/standardPaginationConfig';

type ValidationSettingsValues = {
  repeatInConversationDefault: number;
  conversationRoomCountDefault: number;
  agentParallelCallsDefault: number;
  timeoutMsDefault: number;
  testModelDefault: string;
  evalModelDefault: string;
  paginationPageSizeLimitDefault: number;
};

function areValidationSettingsEqual(left: ValidationSettingsValues, right: ValidationSettingsValues) {
  return (
    left.repeatInConversationDefault === right.repeatInConversationDefault
    && left.conversationRoomCountDefault === right.conversationRoomCountDefault
    && left.agentParallelCallsDefault === right.agentParallelCallsDefault
    && left.timeoutMsDefault === right.timeoutMsDefault
    && left.testModelDefault === right.testModelDefault
    && left.evalModelDefault === right.evalModelDefault
    && left.paginationPageSizeLimitDefault === right.paginationPageSizeLimitDefault
  );
}

export function ValidationSettingsPage({
  environment,
  tokens,
  onPaginationPageSizeLimitChange,
}: {
  environment: Environment;
  tokens: RuntimeSecrets;
  onPaginationPageSizeLimitChange?: (value: number) => void;
}) {
  const { message } = App.useApp();
  const [targetEnvironment, setTargetEnvironment] = useState<Environment>(environment);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [savedValues, setSavedValues] = useState<ValidationSettingsValues | null>(null);
  const [form] = Form.useForm<ValidationSettingsValues>();

  const load = async (env: Environment) => {
    setLoading(true);
    try {
      const data = await getValidationSettings(env);
      const nextValues = {
        repeatInConversationDefault: data.repeatInConversationDefault,
        conversationRoomCountDefault: data.conversationRoomCountDefault,
        agentParallelCallsDefault: data.agentParallelCallsDefault,
        timeoutMsDefault: data.timeoutMsDefault,
        testModelDefault: data.testModelDefault,
        evalModelDefault: data.evalModelDefault,
        paginationPageSizeLimitDefault: normalizeStandardPageSizeLimit(data.paginationPageSizeLimitDefault),
      };
      form.setFieldsValue(nextValues);
      setSavedValues(nextValues);
      setIsDirty(false);
      onPaginationPageSizeLimitChange?.(nextValues.paginationPageSizeLimitDefault);
    } catch (error) {
      console.error(error);
      message.error('환경설정을 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setTargetEnvironment(environment);
  }, [environment]);

  useEffect(() => {
    void load(targetEnvironment);
  }, [targetEnvironment, tokens.bearer, tokens.cms, tokens.mrs]);

  const handleValuesChange = (_: unknown, allValues: ValidationSettingsValues) => {
    if (!savedValues) return;
    const next = !areValidationSettingsEqual(allValues, savedValues);
    setIsDirty(next);
  };

  const handleSave = async () => {
    try {
      const values = (await form.validateFields()) as ValidationSettingsValues;
      setSaving(true);
      await updateValidationSettings(targetEnvironment, values);
      setSavedValues(values);
      setIsDirty(false);
      onPaginationPageSizeLimitChange?.(values.paginationPageSizeLimitDefault);
      message.success({
        content: '저장되었습니다.',
        duration: 2.5,
      });
      await load(targetEnvironment);
    } catch (error) {
      console.error(error);
      message.error({
        content: '저장되지 않았습니다. 다시 한번 시도해 주세요.',
        duration: 2.5,
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="settings-page-surface">
      <Typography.Title level={4} style={{ margin: 0 }}>
        환경설정
      </Typography.Title>

      <Form
        form={form}
        layout="vertical"
        className="settings-form-stack"
        onValuesChange={handleValuesChange}
      >
        <Form.Item label="적용 환경" className="settings-field-block">
          <Select
            options={ENV_OPTIONS}
            value={targetEnvironment}
            onChange={(value) => setTargetEnvironment(value as Environment)}
          />
        </Form.Item>

        <Form.Item
          className="settings-field-block"
          label="동일 질문 반복 횟수"
          name="repeatInConversationDefault"
          rules={[{ required: true, message: '반복 횟수를 입력해 주세요.' }]}
        >
          <InputNumber min={1} precision={0} />
        </Form.Item>
        <Form.Item
          className="settings-field-block"
          label="채팅방 개수"
          name="conversationRoomCountDefault"
          rules={[{ required: true, message: '채팅방 개수를 입력해 주세요.' }]}
        >
          <InputNumber min={1} precision={0} />
        </Form.Item>
        <Form.Item
          className="settings-field-block"
          label="에이전트 병렬 호출 수"
          name="agentParallelCallsDefault"
          rules={[{ required: true, message: '병렬 수를 입력해 주세요.' }]}
        >
          <InputNumber min={1} precision={0} />
        </Form.Item>
        <Form.Item
          className="settings-field-block"
          label="타임아웃(ms)"
          name="timeoutMsDefault"
          rules={[{ required: true, message: '타임아웃을 입력해 주세요.' }]}
        >
          <InputNumber min={1000} precision={0} step={1000} />
        </Form.Item>
        <Form.Item className="settings-field-block" label="테스트 모델" name="testModelDefault" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item className="settings-field-block" label="평가 모델" name="evalModelDefault" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item
          className="settings-field-block"
          label="페이지네이션 > OO개 보기 제한 개수"
          name="paginationPageSizeLimitDefault"
          rules={[{ required: true, message: '제한 개수를 입력해 주세요.' }]}
        >
          <InputNumber min={STANDARD_PAGE_SIZE_LIMIT_MIN} precision={0} step={10} />
        </Form.Item>
      </Form>

      <div className="settings-page-footer">
        <Button
          type="primary"
          loading={saving || loading}
          onClick={handleSave}
          disabled={!isDirty || loading}
          className="settings-save-button"
        >
          저장
        </Button>
      </div>
    </div>
  );
}
