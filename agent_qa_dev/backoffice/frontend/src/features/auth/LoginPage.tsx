import { useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Divider,
  Form,
  Input,
  Select,
  Typography,
} from 'antd';

import type {
  AppEnvironment,
  LocalDevBypassPayload,
  LoginPayload,
} from '../../app/types';
import { ENV_OPTIONS } from '../../app/EnvironmentScope';

type Props = {
  environment: AppEnvironment;
  loading: boolean;
  errorMessage?: string;
  onEnvironmentChange: (environment: AppEnvironment) => void;
  onLogin: (payload: LoginPayload) => Promise<void>;
  localDevBypassEnabled?: boolean;
  localDevBypassLoading?: boolean;
  localDevBypassErrorMessage?: string;
  localDevBypassKey?: string;
  onLocalDevBypassKeyChange?: (value: string) => void;
  onLocalDevBypass?: (payload: LocalDevBypassPayload) => Promise<void>;
};

type LoginFormValues = {
  userId: string;
  password: string;
};

export function LoginPage({
  environment,
  loading,
  errorMessage,
  onEnvironmentChange,
  onLogin,
  localDevBypassEnabled = false,
  localDevBypassLoading = false,
  localDevBypassErrorMessage = '',
  localDevBypassKey = '',
  onLocalDevBypassKeyChange,
  onLocalDevBypass,
}: Props) {
  const [form] = Form.useForm<LoginFormValues>();
  const [submitting, setSubmitting] = useState(false);
  const [bypassSubmitting, setBypassSubmitting] = useState(false);
  const loginFormId = 'auth-login-form';

  const disabled = loading || submitting || localDevBypassLoading;
  const bypassDisabled =
    disabled ||
    bypassSubmitting ||
    !localDevBypassEnabled ||
    !onLocalDevBypass ||
    !onLocalDevBypassKeyChange;
  const mergedOptions = useMemo(
    () =>
      ENV_OPTIONS.map((item) => ({
        label: item.label,
        value: item.value as AppEnvironment,
      })),
    [],
  );

  const handleSubmit = async (values: LoginFormValues) => {
    setSubmitting(true);
    try {
      await onLogin({
        environment,
        userId: values.userId,
        password: values.password,
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleBypassLogin = async () => {
    if (bypassDisabled || !onLocalDevBypass) return;
    const normalizedKey = String(localDevBypassKey || '').trim();
    if (!normalizedKey) {
      onLocalDevBypassKeyChange?.('');
      return;
    }
    setBypassSubmitting(true);
    try {
      await onLocalDevBypass({
        environment,
        backdoorKey: normalizedKey,
      });
    } finally {
      setBypassSubmitting(false);
    }
  };

  return (
    <div className="auth-login-page">
      <Card className="auth-login-card" variant="outlined">
        <div className="auth-login-body">
          <div className="auth-login-header">
            <Typography.Title level={3} className="auth-login-title">
              Agent QA Backoffice
            </Typography.Title>
            <Typography.Text className="auth-login-subtitle">
              에이전트 검증 백오피스
            </Typography.Text>
            <Typography.Text
              type="secondary"
              className="auth-login-description"
            >
              채용에이전트 계정으로 로그인해 주세요.
            </Typography.Text>
          </div>

          {errorMessage ? (
            <Alert
              className="auth-login-error"
              type="error"
              showIcon
              message="로그인 실패"
              description={errorMessage}
            />
          ) : null}

          <Form<LoginFormValues>
            id={loginFormId}
            form={form}
            layout="vertical"
            autoComplete="off"
            onFinish={handleSubmit}
            requiredMark={false}
            className="auth-login-form standard-form-stack"
          >
            <Form.Item label="환경" required>
              <Select
                value={environment}
                options={mergedOptions}
                onChange={(value) =>
                  onEnvironmentChange(value as AppEnvironment)
                }
                disabled={disabled}
                style={{ marginBottom: 12 }}
              />
            </Form.Item>
            <Form.Item
              name="userId"
              label="아이디"
              rules={[{ required: true, message: '아이디를 입력해 주세요.' }]}
            >
              <Input placeholder="아이디" disabled={disabled} />
            </Form.Item>
            <Form.Item
              name="password"
              label="비밀번호"
              rules={[{ required: true, message: '비밀번호를 입력해 주세요.' }]}
            >
              <Input.Password placeholder="비밀번호" disabled={disabled} />
            </Form.Item>
          </Form>

          {localDevBypassEnabled ? (
            <div className="auth-login-bypass">
              <Divider className="auth-login-divider" plain>
                로컬 개발 전용
              </Divider>
              <Typography.Text
                type="secondary"
                className="auth-login-bypass-guide"
              >
                ATS 로그인 없이 UI 점검이 필요할 때만 백도어키를 사용하세요.
              </Typography.Text>
              {localDevBypassErrorMessage ? (
                <Alert
                  className="auth-login-error"
                  type="error"
                  showIcon
                  message="백도어키 인증 실패"
                  description={localDevBypassErrorMessage}
                />
              ) : null}
              <Input.Password
                placeholder="백도어키"
                value={localDevBypassKey}
                onChange={(event) =>
                  onLocalDevBypassKeyChange?.(event.target.value)
                }
                onPressEnter={() => {
                  void handleBypassLogin();
                }}
                disabled={bypassDisabled}
              />
              <Button
                type="default"
                block
                loading={localDevBypassLoading || bypassSubmitting}
                onClick={() => {
                  void handleBypassLogin();
                }}
                disabled={bypassDisabled}
              >
                백도어키로 입장
              </Button>
            </div>
          ) : null}
        </div>
        <div className="auth-login-footer">
          <Button
            type="primary"
            htmlType="submit"
            form={loginFormId}
            loading={disabled}
            disabled={disabled}
            block
          >
            로그인
          </Button>
        </div>
      </Card>
    </div>
  );
}
