import { describe, expect, it } from 'vitest';

import {
  isKnownPath,
  normalizePathname,
  resolveHistoryDetailTab,
  resolveHistoryRunId,
  resolveMenu,
  resolveValidationSection,
} from './validationNavigation';

describe('validation navigation helpers', () => {
  it('normalizes pathname', () => {
    expect(normalizePathname('/validation/run/')).toBe('/validation/run');
    expect(normalizePathname('/')).toBe('/');
  });

  it('resolves menu and section', () => {
    expect(resolveMenu('/validation-data/queries')).toBe('validation-data-queries');
    expect(resolveMenu('/queries')).toBe('validation-data-queries');
    expect(resolveMenu('/validation-data/query-groups')).toBe('validation-data-query-groups');
    expect(resolveMenu('/query-groups')).toBe('validation-data-query-groups');
    expect(resolveMenu('/validation-data/test-sets')).toBe('validation-data-test-sets');
    expect(resolveMenu('/prompt')).toBe('prompt-recruit-agent');
    expect(resolveMenu('/prompt/recruit-agent')).toBe('prompt-recruit-agent');
    expect(resolveMenu('/prompt/response-eval')).toBe('prompt-evaluation');
    expect(resolveMenu('/validation/history/abc')).toBe('validation-history');
    expect(resolveValidationSection('/validation/history')).toBe('history');
    expect(resolveValidationSection('/validation/history/abc')).toBe('history-detail');
  });

  it('resolves history run id safely', () => {
    expect(resolveHistoryRunId('/validation/history/run-1')).toBe('run-1');
    expect(resolveHistoryRunId('/validation/run')).toBeUndefined();
  });

  it('resolves history detail tab from query string', () => {
    expect(resolveHistoryDetailTab('?tab=history')).toBe('history');
    expect(resolveHistoryDetailTab('?tab=results')).toBe('results');
    expect(resolveHistoryDetailTab('?tab=RESULTS')).toBe('results');
    expect(resolveHistoryDetailTab('?tab=unknown')).toBe('history');
    expect(resolveHistoryDetailTab('')).toBe('history');
  });

  it('checks known paths', () => {
    expect(isKnownPath('/login')).toBe(true);
    expect(isKnownPath('/')).toBe(true);
    expect(isKnownPath('/validation-data/queries')).toBe(true);
    expect(isKnownPath('/validation-data/query-groups')).toBe(true);
    expect(isKnownPath('/validation-data/test-sets')).toBe(true);
    expect(isKnownPath('/prompt')).toBe(true);
    expect(isKnownPath('/prompt/recruit-agent')).toBe(true);
    expect(isKnownPath('/prompt/response-eval')).toBe(true);
    expect(isKnownPath('/queries')).toBe(true);
    expect(isKnownPath('/unknown')).toBe(false);
  });
});
