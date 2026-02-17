import { describe, it, expect } from 'vitest';
import { ENV_OPTIONS } from '../EnvironmentScope';
import { appTheme } from '../../theme/theme';

describe('environment scope', () => {
  it('contains fixed env options and purple primary token', () => {
    expect(ENV_OPTIONS.map((x) => x.value)).toEqual(['dev', 'st2', 'st', 'pr']);
    expect(appTheme.token.colorPrimary).toBe('#7B5CF2');
  });
});
