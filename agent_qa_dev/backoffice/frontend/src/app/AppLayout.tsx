import { useEffect, useMemo, useState } from 'react';
import { AxiosError } from 'axios';
import { FileTextOutlined, RobotOutlined, SafetyOutlined, SyncOutlined } from '@ant-design/icons';
import { App, Button, Form, Input, Layout, Menu, Space, Tag, Tooltip, Typography, theme } from 'antd';
import { useLocation, useNavigate } from 'react-router-dom';

import { EnvironmentScope, type Environment } from './EnvironmentScope';
import { GenericRunPage } from '../features/generic/GenericRunPage';
import { PromptManagementPage } from '../features/prompts/PromptManagementPage';
import { QueryManagementPage } from '../features/queries/QueryManagementPage';
import { QueryGroupManagementPage } from '../features/query-groups/QueryGroupManagementPage';
import { TestSetManagementPage } from '../features/test-sets/TestSetManagementPage';
import { AgentValidationManagementPage } from '../features/validations/AgentValidationManagementPage';
import { ValidationSettingsPage } from '../features/validation-settings/ValidationSettingsPage';
import { api } from '../api/client';
import { getValidationSettings } from '../api/validation';
import { RuntimeSecrets } from './types';
import { StandardModal, StandardModalMetaBlock } from '../components/common/StandardModal';
import {
  StandardPaginationConfigContext,
  STANDARD_PAGE_SIZE_LIMIT_DEFAULT,
  normalizeStandardPageSizeLimit,
} from '../components/common/standardPaginationConfig';
import {
  MENU_KEYS,
  MENU_PATHS,
  isKnownPath,
  normalizePathname,
  resolveHistoryRunId,
  resolveMenu,
  resolveValidationSection,
  type MenuKey,
} from './navigation/validationNavigation';
import { emptyRuntimeSecrets, normalizeBearerToken } from './utils/runtimeSecrets';

const { Header, Content, Sider } = Layout;
const FALLBACK_APP_VERSION = '0.1.0';

type CurlStatusItem = {
  field: 'bearer' | 'cms' | 'mrs';
  label: string;
  present: boolean;
  valid: boolean;
  length: number;
  preview: string;
  message: string;
};

type CurlStatusResponse = {
  checks: CurlStatusItem[];
  allValid: boolean;
};

type ParsedCurlResponse = {
  authorization?: string | null;
  'cms-access-token'?: string | null;
  'mrs-session'?: string | null;
};

const LEGACY_PATH_REDIRECTS: Record<string, string> = {
  '/queries': '/validation-data/queries',
  '/query-groups': '/validation-data/query-groups',
};

export function AppLayout() {
  const { notification } = App.useApp();
  const { token: antdToken } = theme.useToken();
  const location = useLocation();
  const navigate = useNavigate();
  const pathname = useMemo(() => normalizePathname(location.pathname), [location.pathname]);

  const [appVersion, setAppVersion] = useState(FALLBACK_APP_VERSION);
  const [environment, setEnvironment] = useState<Environment>('dev');
  const [runtimeSecrets, setRuntimeSecrets] = useState<RuntimeSecrets>(emptyRuntimeSecrets());
  const [isCurlOpen, setIsCurlOpen] = useState(false);
  const [curlText, setCurlText] = useState('');
  const [isParsingCurl, setIsParsingCurl] = useState(false);
  const [parsedCurlPreview, setParsedCurlPreview] = useState<RuntimeSecrets>({ bearer: '', cms: '', mrs: '' });
  const [curlParseError, setCurlParseError] = useState('');
  const [isCheckingCurlStatus, setIsCheckingCurlStatus] = useState(false);
  const [paginationPageSizeLimit, setPaginationPageSizeLimit] = useState(STANDARD_PAGE_SIZE_LIMIT_DEFAULT);

  useEffect(() => {
    const loadVersion = async () => {
      try {
        let responseData: { version?: string } | undefined;
        try {
          ({ data: responseData } = await api.get('/version'));
        } catch {
          ({ data: responseData } = await api.get('/api/v1/version'));
        }
        if (typeof responseData?.version === 'string' && responseData.version) {
          setAppVersion(responseData.version);
        }
      } catch {
        // keep fallback version when version endpoint is unavailable
      }
    };
    void loadVersion();
  }, []);

  useEffect(() => {
    if (pathname === '/') {
      navigate('/validation/run', { replace: true });
      return;
    }
    if (pathname in LEGACY_PATH_REDIRECTS) {
      navigate(LEGACY_PATH_REDIRECTS[pathname], { replace: true });
      return;
    }
    if (!isKnownPath(pathname)) {
      navigate('/validation/run', { replace: true });
    }
  }, [pathname, navigate]);

  useEffect(() => {
    let active = true;
    const loadPaginationPageSizeLimit = async () => {
      try {
        const data = await getValidationSettings(environment);
        if (!active) return;
        setPaginationPageSizeLimit(normalizeStandardPageSizeLimit(data.paginationPageSizeLimitDefault));
      } catch (error) {
        if (!active) return;
        console.error(error);
        setPaginationPageSizeLimit(STANDARD_PAGE_SIZE_LIMIT_DEFAULT);
      }
    };
    void loadPaginationPageSizeLimit();
    return () => {
      active = false;
    };
  }, [environment]);

  const resetCurlModalState = () => {
    setCurlText('');
    setParsedCurlPreview({ bearer: '', cms: '', mrs: '' });
    setCurlParseError('');
  };

  const openCurlModal = () => {
    setParsedCurlPreview({
      bearer: runtimeSecrets.bearer,
      cms: runtimeSecrets.cms,
      mrs: runtimeSecrets.mrs,
    });
    setIsCurlOpen(true);
  };

  const closeCurlModal = () => {
    setIsCurlOpen(false);
    setIsParsingCurl(false);
    resetCurlModalState();
  };

  const handleCurlStatusCheck = async () => {
    setIsCheckingCurlStatus(true);
    try {
      const { data } = await api.post<CurlStatusResponse>('/utils/curl-status', {
        ...runtimeSecrets,
        environment,
      });
      const details = data.checks.map((item) => (
        <Space direction="vertical" size={2} key={item.field}>
          <strong>{item.label}</strong>
          <div>
            상태: <span style={{ color: item.valid ? '#389e0d' : '#d4380d' }}>{item.valid ? '정상' : '미설정'}</span>
          </div>
          <div>길이: {item.length}자</div>
          <div>미리보기: {item.preview || '-'}</div>
          {item.message ? <div>사유: {item.message}</div> : null}
        </Space>
      ));
      const statusMessage = data.allValid ? '현재 cURL 토큰 상태가 정상입니다.' : 'cURL 토큰/세션 상태에 누락이 있습니다.';

      if (data.allValid) {
        notification.success({
          message: 'cURL Status Check',
          description: (
            <Space direction="vertical" size={4}>
              <div>{statusMessage}</div>
              {details}
            </Space>
          ),
        });
      } else {
        notification.warning({
          message: 'cURL Status Check',
          description: (
            <Space direction="vertical" size={4}>
              <div>{statusMessage}</div>
              {details}
            </Space>
          ),
        });
      }
    } catch (error) {
      notification.error({
        message: 'cURL Status Check 실패',
        description: (error as AxiosError<{ detail?: string }>)?.response?.data?.detail || 'Python 검사 API 호출에 실패했습니다.',
      });
      console.error(error);
    } finally {
      setIsCheckingCurlStatus(false);
    }
  };

  const handleParseCurl = async () => {
    if (!curlText.trim()) {
      setCurlParseError('cURL을 입력해 주세요.');
      return;
    }

    setIsParsingCurl(true);
    setCurlParseError('');
    try {
      const { data } = await api.post('/utils/parse-curl', { curlText });
      const parsed = data as ParsedCurlResponse;
      const nextSecrets: RuntimeSecrets = {
        bearer: normalizeBearerToken(parsed.authorization ?? ''),
        cms: (parsed['cms-access-token'] ?? '').trim(),
        mrs: (parsed['mrs-session'] ?? '').trim(),
      };
      setRuntimeSecrets(nextSecrets);
      setParsedCurlPreview(nextSecrets);
      setIsCurlOpen(false);
      setCurlText('');
      notification.success({
        message: 'cURL 파싱 완료',
        description: '입력한 cURL에서 Bearer/CMS/MRS 토큰이 반영되었습니다.',
      });
    } catch (error) {
      setCurlParseError('cURL 파싱에 실패했습니다. 형식을 확인해 주세요.');
      console.error(error);
      notification.error({
        message: 'cURL 파싱 실패',
        description: '요청 본문 형식을 다시 확인하고 다시 시도해 주세요.',
      });
    } finally {
      setIsParsingCurl(false);
    }
  };

  const menu = useMemo(() => resolveMenu(pathname), [pathname]);
  const validationSection = useMemo(() => resolveValidationSection(pathname), [pathname]);
  const historyRunId = useMemo(() => resolveHistoryRunId(pathname), [pathname]);

  const content = useMemo(() => {
    if (menu === 'validation-data-queries') {
      return (
        <QueryManagementPage
          environment={environment}
          tokens={runtimeSecrets}
        />
      );
    }
    if (menu === 'validation-data-query-groups') {
      return <QueryGroupManagementPage environment={environment} tokens={runtimeSecrets} />;
    }
    if (menu === 'validation-data-test-sets') {
      return (
        <TestSetManagementPage
          environment={environment}
          tokens={runtimeSecrets}
          onOpenValidationRun={(testSetId) =>
            navigate(
              testSetId
                ? `/validation/run?testSetId=${encodeURIComponent(testSetId)}`
                : '/validation/run',
            )}
          onOpenValidationHistory={() => navigate('/validation/history')}
        />
      );
    }
    if (menu === 'validation-settings') {
      return (
        <ValidationSettingsPage
          environment={environment}
          tokens={runtimeSecrets}
          onPaginationPageSizeLimitChange={(value) => setPaginationPageSizeLimit(normalizeStandardPageSizeLimit(value))}
        />
      );
    }
    if (menu === 'prompt') {
      return <PromptManagementPage environment={environment} tokens={runtimeSecrets} />;
    }
    if (menu === 'generic-legacy') {
      return <GenericRunPage environment={environment} tokens={runtimeSecrets} />;
    }
    return (
      <AgentValidationManagementPage
        environment={environment}
        tokens={runtimeSecrets}
        section={validationSection}
        historyRunId={historyRunId}
        onOpenHistoryRunDetail={(runId) => navigate(`/validation/history/${encodeURIComponent(runId)}`)}
        onBackToHistory={() => navigate('/validation/history')}
        onOpenRunWorkspace={({ runId, testSetId }) => {
          const params = new URLSearchParams();
          params.set('runId', runId);
          if (testSetId) {
            params.set('testSetId', testSetId);
          }
          navigate(`/validation/run?${params.toString()}`);
        }}
      />
    );
  }, [
    menu,
    environment,
    runtimeSecrets,
    navigate,
    validationSection,
    historyRunId,
  ]);

  return (
    <StandardPaginationConfigContext.Provider value={{ pageSizeLimit: paginationPageSizeLimit }}>
      <Layout className="backoffice-shell">
        <Header className="backoffice-header">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '100%' }}>
            <Space align="center" size="small">
              <Typography.Title level={4} className="backoffice-gnb-logo" style={{ margin: 0 }}>
                <span className="backoffice-gnb-logo-mark">AQB</span>
                <span className="backoffice-gnb-logo-text">Backoffice</span>
              </Typography.Title>
              <Tooltip title="현재 백오피스 버전">
                <Tag color="purple">v{appVersion}</Tag>
              </Tooltip>
            </Space>
            <Space align="center" size="small">
              <EnvironmentScope value={environment} onChange={setEnvironment} controlHeight={antdToken.controlHeight} />
              <Button
                type="default"
                size="middle"
                loading={isCheckingCurlStatus}
                onClick={handleCurlStatusCheck}
                icon={<SyncOutlined />}
              >
                토큰 상태 체크
              </Button>
              <Button
                type="default"
                size="middle"
                onClick={openCurlModal}
                icon={<SafetyOutlined />}
              >
                로그인
              </Button>
            </Space>
          </div>
        </Header>

        <StandardModal
          title="cURL 토큰 파싱"
          open={isCurlOpen}
          width={760}
          destroyOnHidden
          onCancel={closeCurlModal}
          footer={
            <Space>
              <Button onClick={closeCurlModal}>취소</Button>
              <Button type="primary" loading={isParsingCurl} onClick={handleParseCurl}>
                완료
              </Button>
            </Space>
          }

        >
          <StandardModalMetaBlock padding={0} gap={8} marginBottom={12}>
            <Typography.Text type="secondary">
              브라우저에서 복사한 전체 cURL 명령어를 넣어 주세요. 토큰은 이 본문에서 추출됩니다.
            </Typography.Text>
          </StandardModalMetaBlock>
          <Form layout="vertical" className="standard-modal-field-stack">
            <Form.Item
              label="요청 전문 붙여넣기"
              required
              validateStatus={curlParseError ? 'error' : ''}
              extra={curlParseError || undefined}
            >
              <Input.TextArea
                autoSize={{ minRows: 4, maxRows: 6 }}
                value={curlText}
                onChange={(e) => setCurlText(e.target.value)}
                placeholder="curl -X GET 'https://.../...' -H 'Authorization: Bearer ...' -H 'cms-access-token: ...' -H 'mrs-session: ...'"
              />
            </Form.Item>

            <Form.Item
              label="Bearer 토큰"
            >
              <Input.Password value={parsedCurlPreview.bearer} readOnly />
            </Form.Item>
            <Form.Item
              label="CMS Access Token"
            >
              <Input.Password value={parsedCurlPreview.cms} readOnly />
            </Form.Item>
            <Form.Item
              label="MRS Session"
            >
              <Input.Password value={parsedCurlPreview.mrs} readOnly />
            </Form.Item>
          </Form>
        </StandardModal>

        <Layout className="backoffice-main">
          <Sider width={240} className="backoffice-main-sider" theme="light">
            <Menu
              mode="inline"
              selectedKeys={[menu]}
              defaultOpenKeys={['validation-root', 'validation-data-root']}
              onClick={(e) => {
                const nextMenu = e.key as MenuKey;
                if (!MENU_KEYS.includes(nextMenu)) return;
                const targetPath = MENU_PATHS[nextMenu];
                if (targetPath === pathname) return;
                navigate(targetPath);
              }}
              items={[
                {
                  key: 'validation-root',
                  icon: <RobotOutlined />,
                  label: (
                    <Space size={8} align="center">
                      에이전트 검증 운영
                    </Space>
                  ),
                  children: [
                    {
                      key: 'validation-run',
                      label: '검증 실행',
                    },
                    {
                      key: 'validation-history',
                      label: '검증 이력',
                    },
                    {
                      key: 'validation-dashboard',
                      label: '대시보드',
                    },
                  ],
                },
                {
                  key: 'validation-data-root',
                  icon: <FileTextOutlined />,
                  label: (
                    <Space size={8} align="center">
                      검증 데이터 관리
                    </Space>
                  ),
                  children: [
                    {
                      key: 'validation-data-queries',
                      label: '질의 관리',
                    },
                    {
                      key: 'validation-data-query-groups',
                      label: '질의 그룹',
                    },
                    {
                      key: 'validation-data-test-sets',
                      label: '테스트 세트',
                    },
                  ],
                },
                {
                  key: 'validation-settings',
                  icon: <SafetyOutlined />,
                  label: (
                    <Space size={8} align="center">
                      환경설정
                    </Space>
                  ),
                },
                {
                  key: 'prompt',
                  icon: <FileTextOutlined />,
                  label: (
                    <Space size={8} align="center">
                      프롬프트 관리
                    </Space>
                  ),
                },
                {
                  key: 'generic-legacy',
                  icon: <RobotOutlined />,
                  label: (
                    <Space size={8} align="center">
                      레거시 검증
                    </Space>
                  ),
                },
              ]}
              style={{ borderRight: 0 }}
            />
          </Sider>
          <Content className="backoffice-content">
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              {content}
            </Space>
          </Content>
        </Layout>
      </Layout>
    </StandardPaginationConfigContext.Provider>
  );
}
