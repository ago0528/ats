import { describe, expect, it } from 'vitest';

import { AgentValidationManagementPage } from '../AgentValidationManagementPage';

describe('validation management page', () => {
  it('exports component', () => {
    expect(typeof AgentValidationManagementPage).toBe('function');
  });
});
