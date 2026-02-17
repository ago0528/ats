import { describe, expect, it } from 'vitest';

import { ValidationSettingsPage } from '../ValidationSettingsPage';

describe('validation settings page', () => {
  it('exports component', () => {
    expect(typeof ValidationSettingsPage).toBe('function');
  });
});
