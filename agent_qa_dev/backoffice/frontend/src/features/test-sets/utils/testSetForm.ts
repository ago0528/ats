import type { ValidationTestSet, ValidationTestSetConfig } from '../../../api/types/validation';
import {
  DEFAULT_AGENT_MODE_VALUE,
  DEFAULT_EVAL_MODEL_VALUE,
} from '../../validations/constants';
import {
  normalizeAgentModeValue,
  parseContextJson,
  stringifyContext,
} from '../../../shared/utils/validationConfig';

export type TestSetFormValues = {
  name: string;
  description: string;
  agentId?: string;
  contextJson?: string;
  evalModel?: string;
  repeatInConversation?: number;
  conversationRoomCount?: number;
  agentParallelCalls?: number;
  timeoutMs?: number;
};

export const QUERY_PICKER_PAGE_SIZE_DEFAULT = 50;

export function normalizeQueryIds(queryIds: string[]): string[] {
  return Array.from(
    new Set(queryIds.map((queryId) => String(queryId).trim()).filter(Boolean)),
  );
}

export function buildDefaultTestSetFormValues(): TestSetFormValues {
  return {
    name: '',
    description: '',
    agentId: DEFAULT_AGENT_MODE_VALUE,
    contextJson: '',
    evalModel: DEFAULT_EVAL_MODEL_VALUE,
    repeatInConversation: 1,
    conversationRoomCount: 1,
    agentParallelCalls: 3,
    timeoutMs: 120000,
  };
}

export function toTestSetFormValues(detail: ValidationTestSet): TestSetFormValues {
  return {
    name: detail.name,
    description: detail.description,
    agentId: normalizeAgentModeValue(
      detail.config.agentId,
      DEFAULT_AGENT_MODE_VALUE,
    ),
    contextJson: stringifyContext(detail.config.context),
    evalModel: detail.config.evalModel || DEFAULT_EVAL_MODEL_VALUE,
    repeatInConversation: detail.config.repeatInConversation ?? 1,
    conversationRoomCount: detail.config.conversationRoomCount ?? 1,
    agentParallelCalls: detail.config.agentParallelCalls ?? 3,
    timeoutMs: detail.config.timeoutMs ?? 120000,
  };
}

export function buildTestSetConfig(
  values: TestSetFormValues,
): {
  config?: ValidationTestSetConfig;
  parseError?: string;
} {
  const parsedContext = parseContextJson(values.contextJson || '');
  if (parsedContext.parseError) {
    return { parseError: parsedContext.parseError };
  }

  return {
    config: {
      agentId: normalizeAgentModeValue(
        values.agentId,
        DEFAULT_AGENT_MODE_VALUE,
      ),
      context: parsedContext.parsedContext,
      evalModel: values.evalModel || undefined,
      repeatInConversation: values.repeatInConversation,
      conversationRoomCount: values.conversationRoomCount,
      agentParallelCalls: values.agentParallelCalls,
      timeoutMs: values.timeoutMs,
    },
  };
}
