import type { Environment } from '../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../app/types';

export function createMockRuntimeSecrets(overrides?: Partial<RuntimeSecrets>): RuntimeSecrets {
  return {
    bearer: 'mock-bearer',
    cms: 'mock-cms',
    mrs: 'mock-mrs',
    ...overrides,
  };
}

export function createMockEnvironment(next: Environment = 'dev'): Environment {
  return next;
}
