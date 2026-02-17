import { describe, expect, it } from 'vitest';

import { QueryGroupManagementPage } from '../QueryGroupManagementPage';

describe('query group management page', () => {
  it('exports component', () => {
    expect(typeof QueryGroupManagementPage).toBe('function');
  });
});
