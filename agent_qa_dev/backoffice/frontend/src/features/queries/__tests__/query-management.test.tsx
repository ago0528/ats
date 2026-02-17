import { describe, expect, it } from 'vitest';

import { QueryManagementPage } from '../QueryManagementPage';

describe('query management page', () => {
  it('exports component', () => {
    expect(typeof QueryManagementPage).toBe('function');
  });
});
