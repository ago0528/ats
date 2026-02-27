import { describe, expect, it } from 'vitest';

import type { ValidationTestSet } from '../../../api/types/validation';
import { DEFAULT_AGENT_MODE_VALUE } from '../../validations/constants';
import {
  buildDefaultTestSetFormValues,
  buildTestSetConfig,
  normalizeQueryIds,
  toTestSetFormValues,
} from './testSetForm';

const baseTestSet = (partial?: Partial<ValidationTestSet>): ValidationTestSet =>
  ({
    id: 'ts-1',
    name: '테스트 세트',
    description: 'desc',
    itemCount: 1,
    config: {
      agentId: 'ORCHESTRATOR_WORKER_V3',
      evalModel: 'gpt-5.2',
      context: { recruitPlanId: 1 },
      repeatInConversation: 2,
      conversationRoomCount: 3,
      agentParallelCalls: 4,
      timeoutMs: 5000,
    },
    ...partial,
  }) as ValidationTestSet;

describe('testSetForm utils', () => {
  it('normalizes query ids', () => {
    expect(normalizeQueryIds([' a ', 'a', 'b', ''])).toEqual(['a', 'b']);
  });

  it('builds default form values', () => {
    const defaults = buildDefaultTestSetFormValues();
    expect(defaults.agentId).toBe(DEFAULT_AGENT_MODE_VALUE);
    expect(defaults.repeatInConversation).toBe(1);
  });

  it('maps test set detail to form values', () => {
    const values = toTestSetFormValues(baseTestSet());
    expect(values.agentId).toBe(DEFAULT_AGENT_MODE_VALUE);
    expect(values.contextJson).toContain('recruitPlanId');
    expect(values.repeatInConversation).toBe(2);
  });

  it('builds test set config and validates context', () => {
    const valid = buildTestSetConfig({
      ...buildDefaultTestSetFormValues(),
      contextJson: '{"a":1}',
    });
    expect(valid.config?.context).toEqual({ a: 1 });

    const invalid = buildTestSetConfig({
      ...buildDefaultTestSetFormValues(),
      contextJson: '[1,2]',
    });
    expect(invalid.parseError).toContain('JSON 객체');
  });
});
