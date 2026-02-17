import { describe, expect, it } from 'vitest';

import { TestSetManagementPage } from '../TestSetManagementPage';

describe('test set management page', () => {
  it('exports component', () => {
    expect(typeof TestSetManagementPage).toBe('function');
  });
});
