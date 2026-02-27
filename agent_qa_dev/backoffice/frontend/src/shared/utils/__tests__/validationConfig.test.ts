import { describe, expect, it } from 'vitest';

import {
  CONTEXT_SAMPLE,
  normalizeAgentModeValue,
  parseContextJson,
  stringifyContext,
} from '../validationConfig';

describe('validationConfig utils', () => {
  it('normalizes agent mode values with legacy fallback', () => {
    expect(normalizeAgentModeValue('')).toBe('AUTO');
    expect(normalizeAgentModeValue('ORCHESTRATOR_WORKER_V3', 'AUTO')).toBe('AUTO');
    expect(normalizeAgentModeValue('RECRUIT_PLAN_ASSISTANT', 'AUTO')).toBe('RECRUIT_PLAN_ASSISTANT');
  });

  it('parses context json object and handles errors', () => {
    expect(parseContextJson('').parsedContext).toBeUndefined();
    expect(parseContextJson('{"a":1}')).toEqual({ parsedContext: { a: 1 } });
    expect(parseContextJson('[1,2]').parseError).toContain('JSON 객체');
    expect(parseContextJson('{a:1}').parseError).toContain('context JSON 형식이 올바르지 않습니다');
  });

  it('stringifies context value safely', () => {
    expect(stringifyContext(undefined)).toBe('');
    expect(stringifyContext('  raw  ')).toBe('raw');
    expect(stringifyContext({ a: 1 })).toBe('{\n  "a": 1\n}');
  });

  it('keeps context sample text stable', () => {
    expect(CONTEXT_SAMPLE).toContain('recruitPlanId');
  });
});
