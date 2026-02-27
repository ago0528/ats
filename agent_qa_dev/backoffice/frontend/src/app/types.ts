export type RuntimeSecrets = {
  bearer: string;
  cms: string;
  mrs: string;
};

export type AppEnvironment = 'dev' | 'st2' | 'st' | 'pr';

export type LoginPayload = {
  environment: AppEnvironment;
  userId: string;
  password: string;
};

export type LocalDevBypassPayload = {
  environment: AppEnvironment;
  backdoorKey: string;
};

export type AuthSessionResponse = {
  authenticated: boolean;
  environment: AppEnvironment;
  userId: string;
  runtimeSecrets: RuntimeSecrets;
  optionalTokens: {
    accAuthToken?: string;
  };
  expiresAt: string | null;
  agentAccessTokenExpiresAt?: string | null;
  cmsAccessTokenExpiresAt?: string | null;
  refreshedAt?: string | null;
};

export type AuthSessionState = {
  isAuthenticated: boolean;
  environment: AppEnvironment;
  userId: string;
  expiresAt: string | null;
  refreshedAt: string | null;
};
