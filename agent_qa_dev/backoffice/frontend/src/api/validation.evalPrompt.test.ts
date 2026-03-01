import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockedApi = vi.hoisted(() => ({
  get: vi.fn(),
  patch: vi.fn(),
  post: vi.fn(),
}));

vi.mock('./client', () => ({
  api: mockedApi,
}));

import {
  getEvaluationScoringPrompt,
  resetEvaluationScoringPromptDefault,
  revertEvaluationScoringPromptPrevious,
  updateEvaluationScoringPrompt,
} from './validation';

describe('evaluation scoring prompt api', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('requests current evaluation scoring prompt snapshot', async () => {
    const payload = {
      promptKey: 'validation_scoring',
      currentPrompt: 'current',
      previousPrompt: 'previous',
      currentVersionLabel: 'v3.0.0',
      previousVersionLabel: 'v2.9.0',
    };
    mockedApi.get.mockResolvedValue({ data: payload });

    const result = await getEvaluationScoringPrompt();

    expect(mockedApi.get).toHaveBeenCalledWith('/prompts/evaluation/scoring');
    expect(result).toEqual(payload);
  });

  it('sends update payload with prompt and versionLabel', async () => {
    const payload = { prompt: 'next prompt', versionLabel: 'v3.1.0' };
    mockedApi.patch.mockResolvedValue({ data: { ok: true } });

    await updateEvaluationScoringPrompt(payload);

    expect(mockedApi.patch).toHaveBeenCalledWith('/prompts/evaluation/scoring', payload);
  });

  it('sends revert payload with versionLabel', async () => {
    const payload = { versionLabel: 'v3.1.1' };
    mockedApi.post.mockResolvedValue({ data: { ok: true } });

    await revertEvaluationScoringPromptPrevious(payload);

    expect(mockedApi.post).toHaveBeenCalledWith('/prompts/evaluation/scoring/revert-previous', payload);
  });

  it('sends reset payload with versionLabel', async () => {
    const payload = { versionLabel: 'v3.1.2' };
    mockedApi.post.mockResolvedValue({ data: { ok: true } });

    await resetEvaluationScoringPromptDefault(payload);

    expect(mockedApi.post).toHaveBeenCalledWith('/prompts/evaluation/scoring/reset-default', payload);
  });
});
