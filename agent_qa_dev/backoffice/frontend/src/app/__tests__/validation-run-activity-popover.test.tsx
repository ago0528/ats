import { describe, expect, it } from 'vitest';

import { ValidationRunActivityPopover } from '../components/ValidationRunActivityPopover';

describe('validation run activity popover', () => {
  it('exports component', () => {
    expect(typeof ValidationRunActivityPopover).toBe('function');
  });
});

