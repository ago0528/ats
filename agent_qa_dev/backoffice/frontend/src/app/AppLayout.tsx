import { useCallback, useEffect, useMemo, useState } from 'react';
import { AxiosError } from 'axios';
import {
  FileTextOutlined,
  LogoutOutlined,
  RobotOutlined,
  SafetyOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import {
  App,
  Breadcrumb,
  Button,
  Form,
  Input,
  Layout,
  Menu,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography,
  theme,
} from 'antd';
import type { BreadcrumbProps } from 'antd';
import { useLocation, useNavigate } from 'react-router-dom';

import {
  getAuthSession,
  loginAuth,
  localDevBypassAuth,
  logoutAuth,
  refreshAuthSession,
} from '../api/auth';
import { api } from '../api/client';
import { getValidationSettings } from '../api/validation';
import {
  StandardModal,
  StandardModalMetaBlock,
} from '../components/common/StandardModal';
import {
  StandardPaginationConfigContext,
  STANDARD_PAGE_SIZE_LIMIT_DEFAULT,
  normalizeStandardPageSizeLimit,
} from '../components/common/standardPaginationConfig';
import { LoginPage } from '../features/auth/LoginPage';
import { GenericRunPage } from '../features/generic/GenericRunPage';
import { PromptManagementPage } from '../features/prompts/PromptManagementPage';
import { QueryGroupManagementPage } from '../features/query-groups/QueryGroupManagementPage';
import { QueryManagementPage } from '../features/queries/QueryManagementPage';
import { TestSetManagementPage } from '../features/test-sets/TestSetManagementPage';
import { ValidationSettingsPage } from '../features/validation-settings/ValidationSettingsPage';
import { AgentValidationManagementPage } from '../features/validations/AgentValidationManagementPage';
import { EnvironmentScope, type Environment } from './EnvironmentScope';
import { ValidationRunActivityPopover } from './components/ValidationRunActivityPopover';
import {
  MENU_KEYS,
  MENU_PATHS,
  isKnownPath,
  normalizePathname,
  resolveHistoryDetailTab,
  resolveHistoryRunId,
  resolveMenu,
  resolveValidationSection,
  type MenuKey,
} from './navigation/validationNavigation';
import type {
  AuthSessionResponse,
  AuthSessionState,
  LocalDevBypassPayload,
  LoginPayload,
  RuntimeSecrets,
} from './types';
import {
  emptyRuntimeSecrets,
  normalizeBearerToken,
} from './utils/runtimeSecrets';

const { Header, Content, Sider } = Layout;
const FALLBACK_APP_VERSION = '0.2.0';
const FALLBACK_AFTER_LOGIN_PATH = '/validation/run';
const AUTH_REFRESH_INTERVAL_MS = 5 * 60 * 1000;
const AUTH_REFRESH_THRESHOLD_MS = 10 * 60 * 1000;
const ENV_STORAGE_KEY = 'aqb.backoffice.environment';
const LEGACY_CURL_LOGIN_ENABLED = ['1', 'true', 'yes', 'on'].includes(
  String(
    import.meta.env.VITE_ENABLE_LEGACY_CURL_LOGIN ?? 'false',
  ).toLowerCase(),
);
const LOCAL_DEV_BACKDOOR_ENABLED = ['1', 'true', 'yes', 'on'].includes(
  String(
    import.meta.env.VITE_ENABLE_LOCAL_DEV_BACKDOOR_LOGIN ?? 'false',
  ).toLowerCase(),
);

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

function buildEmptyAuthState(environment: Environment): AuthSessionState {
  return {
    isAuthenticated: false,
    environment,
    userId: '',
    expiresAt: null,
    refreshedAt: null,
  };
}

function resolveSafeNextPath(rawValue: string | null): string {
  const value = String(rawValue || '').trim();
  if (!value.startsWith('/')) return FALLBACK_AFTER_LOGIN_PATH;
  if (value.startsWith('//')) return FALLBACK_AFTER_LOGIN_PATH;
  if (value === '/login') return FALLBACK_AFTER_LOGIN_PATH;
  return value;
}

function resolveErrorDetail(error: unknown, fallbackMessage: string): string {
  const detail =
    (error as AxiosError<{ detail?: string }>)?.response?.data?.detail ||
    (error as Error)?.message ||
    '';
  return detail || fallbackMessage;
}

function parseIsoDate(value: string | null): Date | null {
  if (!value) return null;
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return null;
  return new Date(timestamp);
}

function isLocalHostname(hostname: string): boolean {
  const normalized = String(hostname || '')
    .trim()
    .toLowerCase();
  return (
    normalized === 'localhost' ||
    normalized === '127.0.0.1' ||
    normalized === '::1'
  );
}

function isEnvironment(value: string): value is Environment {
  return value === 'dev' || value === 'st2' || value === 'st' || value === 'pr';
}

function resolveInitialEnvironment(): Environment {
  if (typeof window === 'undefined') return 'dev';
  const rawValue = String(window.localStorage.getItem(ENV_STORAGE_KEY) || '')
    .trim()
    .toLowerCase();
  return isEnvironment(rawValue) ? rawValue : 'dev';
}

function resolveVersionEndpoints() {
  const normalizedBaseUrl = String(api.defaults.baseURL || '')
    .trim()
    .replace(/\/+$/, '')
    .toLowerCase();
  if (normalizedBaseUrl.endsWith('/api/v1')) {
    return ['/version', '/api/v1/version'] as const;
  }
  return ['/api/v1/version', '/version'] as const;
}

export function AppLayout() {
  const { notification, modal } = App.useApp();
  const { token: antdToken } = theme.useToken();
  const location = useLocation();
  const navigate = useNavigate();
  const pathname = useMemo(
    () => normalizePathname(location.pathname),
    [location.pathname],
  );
  const isLoginPath = pathname === '/login';
  const nextPathFromQuery = useMemo(
    () => resolveSafeNextPath(new URLSearchParams(location.search).get('next')),
    [location.search],
  );

  const [appVersion, setAppVersion] = useState(FALLBACK_APP_VERSION);
  const [environment, setEnvironment] = useState<Environment>(
    resolveInitialEnvironment,
  );
  const [runtimeSecrets, setRuntimeSecrets] = useState<RuntimeSecrets>(
    emptyRuntimeSecrets(),
  );
  const [authState, setAuthState] = useState<AuthSessionState>(
    buildEmptyAuthState('dev'),
  );
  const [authLoading, setAuthLoading] = useState(true);
  const [hasResolvedInitialSession, setHasResolvedInitialSession] =
    useState(false);
  const [authError, setAuthError] = useState('');
  const [hasLoginSubmitFailed, setHasLoginSubmitFailed] = useState(false);
  const [localDevBackdoorKey, setLocalDevBackdoorKey] = useState('');
  const [localDevBackdoorError, setLocalDevBackdoorError] = useState('');
  const [hasLocalDevBackdoorFailed, setHasLocalDevBackdoorFailed] =
    useState(false);
  const [isLocalDevBackdoorLoading, setIsLocalDevBackdoorLoading] =
    useState(false);
  const [isRefreshingAuth, setIsRefreshingAuth] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [isCurlOpen, setIsCurlOpen] = useState(false);
  const [curlText, setCurlText] = useState('');
  const [isParsingCurl, setIsParsingCurl] = useState(false);
  const [parsedCurlPreview, setParsedCurlPreview] = useState<RuntimeSecrets>({
    bearer: '',
    cms: '',
    mrs: '',
  });
  const [curlParseError, setCurlParseError] = useState('');
  const [isCheckingCurlStatus, setIsCheckingCurlStatus] = useState(false);
  const [paginationPageSizeLimit, setPaginationPageSizeLimit] = useState(
    STANDARD_PAGE_SIZE_LIMIT_DEFAULT,
  );

  const applyAuthSession = useCallback((payload: AuthSessionResponse) => {
    const normalizedSecrets: RuntimeSecrets = {
      bearer: normalizeBearerToken(payload.runtimeSecrets?.bearer ?? ''),
      cms: String(payload.runtimeSecrets?.cms ?? '').trim(),
      mrs: String(payload.runtimeSecrets?.mrs ?? '').trim(),
    };
    setEnvironment(payload.environment);
    setRuntimeSecrets(normalizedSecrets);
    setAuthState({
      isAuthenticated: Boolean(
        normalizedSecrets.bearer &&
        normalizedSecrets.cms &&
        normalizedSecrets.mrs,
      ),
      environment: payload.environment,
      userId: String(payload.userId || '').trim(),
      expiresAt: payload.expiresAt || null,
      refreshedAt: payload.refreshedAt || null,
    });
    setHasLoginSubmitFailed(false);
    setAuthError('');
    setHasLocalDevBackdoorFailed(false);
    setLocalDevBackdoorError('');
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(ENV_STORAGE_KEY, environment);
  }, [environment]);

  const clearAuthSession = useCallback((targetEnvironment: Environment) => {
    setRuntimeSecrets(emptyRuntimeSecrets());
    setAuthState(buildEmptyAuthState(targetEnvironment));
  }, []);

  const restoreSession = useCallback(
    async (targetEnvironment: Environment) => {
      try {
        const response = await getAuthSession(targetEnvironment);
        applyAuthSession(response);
        return true;
      } catch (error) {
        clearAuthSession(targetEnvironment);
        return false;
      }
    },
    [applyAuthSession, clearAuthSession],
  );

  const handleAuthRefresh = useCallback(
    async (options?: { silent?: boolean }) => {
      setIsRefreshingAuth(true);
      try {
        const response = await refreshAuthSession(environment);
        applyAuthSession(response);
        if (!options?.silent) {
          notification.success({
            message: '세션 갱신 완료',
            description: 'ATS 인증 세션이 갱신되었습니다.',
          });
        }
        return true;
      } catch (error) {
        clearAuthSession(environment);
        const detail = resolveErrorDetail(error, '세션 갱신에 실패했습니다.');
        if (!options?.silent) {
          notification.error({
            message: '세션 갱신 실패',
            description: detail,
          });
        }
        setAuthError(detail);
        return false;
      } finally {
        setIsRefreshingAuth(false);
      }
    },
    [applyAuthSession, clearAuthSession, environment, notification],
  );

  const handleLogout = useCallback(async () => {
    setIsLoggingOut(true);
    try {
      await logoutAuth();
    } catch (error) {
      console.error(error);
    } finally {
      clearAuthSession(environment);
      setLocalDevBackdoorKey('');
      setHasLocalDevBackdoorFailed(false);
      setLocalDevBackdoorError('');
      setIsLoggingOut(false);
      navigate('/login', { replace: true });
    }
  }, [clearAuthSession, environment, navigate]);

  const handleLogin = useCallback(
    async (payload: LoginPayload) => {
      setAuthLoading(true);
      setHasLoginSubmitFailed(false);
      setAuthError('');
      setHasLocalDevBackdoorFailed(false);
      setLocalDevBackdoorError('');
      try {
        const response = await loginAuth(payload);
        applyAuthSession(response);
      } catch (error) {
        clearAuthSession(payload.environment);
        setHasLoginSubmitFailed(true);
        setAuthError(
          resolveErrorDetail(error, '아이디 또는 비밀번호를 확인해 주세요.'),
        );
      } finally {
        setAuthLoading(false);
      }
    },
    [applyAuthSession, clearAuthSession],
  );

  const handleLocalDevBackdoorLogin = useCallback(
    async (payload: LocalDevBypassPayload) => {
      setAuthLoading(true);
      setIsLocalDevBackdoorLoading(true);
      setHasLocalDevBackdoorFailed(false);
      setLocalDevBackdoorError('');
      setHasLoginSubmitFailed(false);
      setAuthError('');
      try {
        const response = await localDevBypassAuth(payload);
        applyAuthSession(response);
        setLocalDevBackdoorKey('');
      } catch (error) {
        clearAuthSession(payload.environment);
        setHasLocalDevBackdoorFailed(true);
        setLocalDevBackdoorError(
          resolveErrorDetail(error, '백도어키를 확인해 주세요.'),
        );
      } finally {
        setIsLocalDevBackdoorLoading(false);
        setAuthLoading(false);
      }
    },
    [applyAuthSession, clearAuthSession],
  );

  useEffect(() => {
    const loadVersion = async () => {
      const [primaryEndpoint, fallbackEndpoint] = resolveVersionEndpoints();
      try {
        let responseData: { version?: string } | undefined;
        try {
          ({ data: responseData } = await api.get(primaryEndpoint));
        } catch {
          ({ data: responseData } = await api.get(fallbackEndpoint));
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
    if (pathname === '/login') return;
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
    const loadSession = async () => {
      if (
        isLoginPath &&
        hasResolvedInitialSession &&
        !authState.isAuthenticated
      ) {
        setAuthLoading(false);
        return;
      }
      setAuthLoading(true);
      await restoreSession(environment);
      if (!active) return;
      setHasResolvedInitialSession(true);
      setAuthLoading(false);
    };
    void loadSession();
    return () => {
      active = false;
    };
  }, [
    authState.isAuthenticated,
    environment,
    hasResolvedInitialSession,
    isLoginPath,
    restoreSession,
  ]);

  useEffect(() => {
    if (authLoading) return;
    if (authState.isAuthenticated) {
      if (isLoginPath) {
        navigate(nextPathFromQuery, { replace: true });
      }
      return;
    }
    if (!isLoginPath) {
      const next = `${pathname}${location.search}`;
      navigate(`/login?next=${encodeURIComponent(next)}`, { replace: true });
    }
  }, [
    authLoading,
    authState.isAuthenticated,
    isLoginPath,
    location.search,
    navigate,
    nextPathFromQuery,
    pathname,
  ]);

  useEffect(() => {
    if (!authState.isAuthenticated) return;
    const interval = window.setInterval(() => {
      void handleAuthRefresh({ silent: true });
    }, AUTH_REFRESH_INTERVAL_MS);
    return () => {
      window.clearInterval(interval);
    };
  }, [authState.isAuthenticated, handleAuthRefresh]);

  useEffect(() => {
    if (!authState.isAuthenticated) return;
    const expiresAt = parseIsoDate(authState.expiresAt);
    if (!expiresAt) return;
    const delay = expiresAt.getTime() - Date.now() - AUTH_REFRESH_THRESHOLD_MS;
    if (delay <= 0) {
      void handleAuthRefresh({ silent: true });
      return;
    }
    const timer = window.setTimeout(() => {
      void handleAuthRefresh({ silent: true });
    }, delay);
    return () => {
      window.clearTimeout(timer);
    };
  }, [authState.expiresAt, authState.isAuthenticated, handleAuthRefresh]);

  useEffect(() => {
    if (!authState.isAuthenticated) {
      setPaginationPageSizeLimit(STANDARD_PAGE_SIZE_LIMIT_DEFAULT);
      return;
    }
    let active = true;
    const loadPaginationPageSizeLimit = async () => {
      try {
        const data = await getValidationSettings(environment);
        if (!active) return;
        setPaginationPageSizeLimit(
          normalizeStandardPageSizeLimit(data.paginationPageSizeLimitDefault),
        );
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
  }, [authState.isAuthenticated, environment]);

  const resetCurlModalState = () => {
    setCurlText('');
    setParsedCurlPreview({ bearer: '', cms: '', mrs: '' });
    setCurlParseError('');
  };

  const openCurlModal = () => {
    if (!LEGACY_CURL_LOGIN_ENABLED) return;
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
    if (!LEGACY_CURL_LOGIN_ENABLED) return;
    setIsCheckingCurlStatus(true);
    try {
      const { data } = await api.post<CurlStatusResponse>(
        '/utils/curl-status',
        {
          ...runtimeSecrets,
          environment,
        },
      );
      const details = data.checks.map((item) => (
        <Space direction="vertical" size={2} key={item.field}>
          <strong>{item.label}</strong>
          <div>
            상태:{' '}
            <span style={{ color: item.valid ? '#389e0d' : '#d4380d' }}>
              {item.valid ? '정상' : '미설정'}
            </span>
          </div>
          <div>길이: {item.length}자</div>
          <div>미리보기: {item.preview || '-'}</div>
          {item.message ? <div>사유: {item.message}</div> : null}
        </Space>
      ));
      const statusMessage = data.allValid
        ? '현재 cURL 토큰 상태가 정상입니다.'
        : 'cURL 토큰/세션 상태에 누락이 있습니다.';

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
        description:
          (error as AxiosError<{ detail?: string }>)?.response?.data?.detail ||
          'Python 검사 API 호출에 실패했습니다.',
      });
      console.error(error);
    } finally {
      setIsCheckingCurlStatus(false);
    }
  };

  const handleParseCurl = async () => {
    if (!LEGACY_CURL_LOGIN_ENABLED) return;
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
  const validationSection = useMemo(
    () => resolveValidationSection(pathname),
    [pathname],
  );
  const historyRunId = useMemo(() => resolveHistoryRunId(pathname), [pathname]);
  const historyDetailTab = useMemo(
    () => resolveHistoryDetailTab(location.search),
    [location.search],
  );
  const authExpiresLabel = useMemo(() => {
    const expiresAt = parseIsoDate(authState.expiresAt);
    if (!expiresAt) return '만료 정보 없음';
    return expiresAt.toLocaleString();
  }, [authState.expiresAt]);

  const toBreadcrumbLink = useCallback(
    (label: string, path: string) => (
      <a
        href={path}
        onClick={(event) => {
          event.preventDefault();
          navigate(path);
        }}
      >
        {label}
      </a>
    ),
    [navigate],
  );

  const pageBreadcrumbItems = useMemo<BreadcrumbProps['items']>(() => {
    if (menu === 'validation-run') {
      return [{ title: '에이전트 검증 운영' }, { title: '검증 실행' }];
    }
    if (menu === 'validation-history') {
      if (validationSection === 'history-detail') {
        return [
          { title: '에이전트 검증 운영' },
          { title: toBreadcrumbLink('질문 결과', '/validation/history') },
          {
            title:
              historyDetailTab === 'results' ? '평가 결과' : '질문 결과 상세',
          },
        ];
      }
      return [{ title: '에이전트 검증 운영' }, { title: '질문 결과' }];
    }
    if (menu === 'validation-dashboard') {
      return [{ title: '에이전트 검증 운영' }, { title: '대시보드' }];
    }
    if (menu === 'validation-data-queries') {
      return [{ title: '검증 데이터 관리' }, { title: '질의 관리' }];
    }
    if (menu === 'validation-data-query-groups') {
      return [{ title: '검증 데이터 관리' }, { title: '질의 그룹' }];
    }
    if (menu === 'validation-data-test-sets') {
      return [{ title: '검증 데이터 관리' }, { title: '테스트 세트' }];
    }
    if (menu === 'validation-settings') {
      return [{ title: '환경설정' }];
    }
    if (menu === 'prompt') {
      return [{ title: '프롬프트 관리' }];
    }
    if (menu === 'generic-legacy') {
      return [{ title: '레거시 검증' }];
    }
    return [{ title: '에이전트 검증 운영' }];
  }, [historyDetailTab, menu, toBreadcrumbLink, validationSection]);

  const openRunWorkspace = useCallback(
    ({ runId, testSetId }: { runId: string; testSetId?: string | null }) => {
      const params = new URLSearchParams();
      params.set('runId', runId);
      if (testSetId) {
        params.set('testSetId', testSetId);
      }
      navigate(`/validation/run?${params.toString()}`);
    },
    [navigate],
  );

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
      return (
        <QueryGroupManagementPage
          environment={environment}
          tokens={runtimeSecrets}
        />
      );
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
            )
          }
          onOpenValidationHistory={() => navigate('/validation/history')}
        />
      );
    }
    if (menu === 'validation-settings') {
      return (
        <ValidationSettingsPage
          environment={environment}
          tokens={runtimeSecrets}
          onPaginationPageSizeLimitChange={(value) =>
            setPaginationPageSizeLimit(normalizeStandardPageSizeLimit(value))
          }
        />
      );
    }
    if (menu === 'prompt') {
      return (
        <PromptManagementPage
          environment={environment}
          tokens={runtimeSecrets}
        />
      );
    }
    if (menu === 'generic-legacy') {
      return (
        <GenericRunPage environment={environment} tokens={runtimeSecrets} />
      );
    }
    return (
      <AgentValidationManagementPage
        environment={environment}
        tokens={runtimeSecrets}
        section={validationSection}
        historyRunId={historyRunId}
        onOpenHistoryRunDetail={(runId) =>
          navigate(`/validation/history/${encodeURIComponent(runId)}`)
        }
        onBackToHistory={() => navigate('/validation/history')}
        onOpenRunWorkspace={openRunWorkspace}
      />
    );
  }, [
    menu,
    environment,
    runtimeSecrets,
    navigate,
    validationSection,
    historyRunId,
    openRunWorkspace,
  ]);

  const handleLoginEnvironmentChange = useCallback((next: Environment) => {
    setEnvironment(next);
    setHasLoginSubmitFailed(false);
    setAuthError('');
    setHasLocalDevBackdoorFailed(false);
    setLocalDevBackdoorError('');
    setLocalDevBackdoorKey('');
  }, []);

  const handleGnbEnvironmentChange = useCallback(
    (next: Environment) => {
      if (next === environment) return;
      modal.confirm({
        title: '환경을 변경하시겠어요?',
        content: '로그인 환경을 변경하기 위해 재로그인합니다.',
        cancelText: '취소',
        okText: '확인',
        onOk: async () => {
          try {
            await logoutAuth();
          } catch (error) {
            console.error(error);
          } finally {
            clearAuthSession(next);
            setHasLoginSubmitFailed(false);
            setAuthError('');
            setHasLocalDevBackdoorFailed(false);
            setLocalDevBackdoorError('');
            setLocalDevBackdoorKey('');
            setEnvironment(next);
            const nextPath = `${pathname}${location.search}`;
            navigate(`/login?next=${encodeURIComponent(nextPath)}`, {
              replace: true,
            });
          }
        },
      });
    },
    [clearAuthSession, environment, location.search, modal, navigate, pathname],
  );

  const isLocalDevBackdoorAvailable = useMemo(() => {
    if (!LOCAL_DEV_BACKDOOR_ENABLED) return false;
    if (typeof window === 'undefined') return false;
    return isLocalHostname(window.location.hostname);
  }, []);

  if (!authState.isAuthenticated) {
    if (isLoginPath) {
      return (
        <LoginPage
          environment={environment}
          loading={authLoading}
          errorMessage={hasLoginSubmitFailed ? authError : ''}
          localDevBypassEnabled={isLocalDevBackdoorAvailable}
          localDevBypassLoading={isLocalDevBackdoorLoading}
          localDevBypassErrorMessage={
            hasLocalDevBackdoorFailed ? localDevBackdoorError : ''
          }
          localDevBypassKey={localDevBackdoorKey}
          onLocalDevBypassKeyChange={setLocalDevBackdoorKey}
          onLocalDevBypass={handleLocalDevBackdoorLogin}
          onEnvironmentChange={handleLoginEnvironmentChange}
          onLogin={handleLogin}
        />
      );
    }
    return (
      <div className="auth-login-page">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <StandardPaginationConfigContext.Provider
      value={{ pageSizeLimit: paginationPageSizeLimit }}
    >
      <Layout className="backoffice-shell">
        <Header className="backoffice-header">
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              height: '100%',
            }}
          >
            <Space align="center" size="small">
              <Typography.Title
                level={4}
                className="backoffice-gnb-logo"
                style={{ margin: 0 }}
              >
                <span className="backoffice-gnb-logo-mark">AQB</span>
                <span className="backoffice-gnb-logo-text">
                  채용에이전트 검증
                </span>
              </Typography.Title>
              <Tooltip title="현재 백오피스 버전">
                <Tag color="purple">v{appVersion}</Tag>
              </Tooltip>
            </Space>
            <Space align="center" size="small">
              <ValidationRunActivityPopover
                environment={environment}
                runtimeSecrets={runtimeSecrets}
                onOpenRunWorkspace={openRunWorkspace}
                onOpenHistoryRunDetail={(runId) =>
                  navigate(`/validation/history/${encodeURIComponent(runId)}`)
                }
              />
              <EnvironmentScope
                value={environment}
                onChange={handleGnbEnvironmentChange}
                controlHeight={antdToken.controlHeight}
              />
              <Button
                type="default"
                size="middle"
                loading={isRefreshingAuth}
                onClick={() => void handleAuthRefresh()}
                icon={<SyncOutlined />}
              >
                세션 새로고침
              </Button>
              {LEGACY_CURL_LOGIN_ENABLED ? (
                <Button
                  type="default"
                  size="middle"
                  loading={isCheckingCurlStatus}
                  onClick={handleCurlStatusCheck}
                  icon={<SyncOutlined />}
                >
                  cURL 상태 체크
                </Button>
              ) : null}
              {LEGACY_CURL_LOGIN_ENABLED ? (
                <Button
                  type="default"
                  size="middle"
                  onClick={openCurlModal}
                  icon={<SafetyOutlined />}
                >
                  cURL 로그인
                </Button>
              ) : null}
              <Button
                type="default"
                size="middle"
                loading={isLoggingOut}
                onClick={() => void handleLogout()}
                icon={<LogoutOutlined />}
              >
                로그아웃
              </Button>
              <Tooltip title={`세션 만료 예정: ${authExpiresLabel}`}>
                <Tag color="blue">{authState.userId || 'unknown'}</Tag>
              </Tooltip>
            </Space>
          </div>
        </Header>

        {LEGACY_CURL_LOGIN_ENABLED ? (
          <StandardModal
            title="cURL 토큰 파싱"
            open={isCurlOpen}
            width={760}
            destroyOnHidden
            onCancel={closeCurlModal}
            footer={
              <Space>
                <Button onClick={closeCurlModal}>취소</Button>
                <Button
                  type="primary"
                  loading={isParsingCurl}
                  onClick={handleParseCurl}
                >
                  완료
                </Button>
              </Space>
            }
          >
            <StandardModalMetaBlock padding={0} gap={8} marginBottom={12}>
              <Typography.Text type="secondary">
                브라우저에서 복사한 전체 cURL 명령어를 넣어 주세요. 토큰은 이
                본문에서 추출됩니다.
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

              <Form.Item label="Bearer 토큰">
                <Input.Password value={parsedCurlPreview.bearer} readOnly />
              </Form.Item>
              <Form.Item label="CMS Access Token">
                <Input.Password value={parsedCurlPreview.cms} readOnly />
              </Form.Item>
              <Form.Item label="MRS Session">
                <Input.Password value={parsedCurlPreview.mrs} readOnly />
              </Form.Item>
            </Form>
          </StandardModal>
        ) : null}

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
                      label: '질문 결과',
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
              <Breadcrumb
                className="backoffice-page-breadcrumb"
                items={pageBreadcrumbItems}
              />
              {content}
            </Space>
          </Content>
        </Layout>
      </Layout>
    </StandardPaginationConfigContext.Provider>
  );
}
