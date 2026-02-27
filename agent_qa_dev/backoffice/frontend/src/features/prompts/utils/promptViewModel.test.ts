import { describe, expect, it } from 'vitest';

import {
  buildPromptDiffModelPaths,
  buildPromptViewDiffModelPaths,
  buildWorkerLabel,
  filterPromptWorkers,
} from './promptViewModel';

describe('promptViewModel', () => {
  it('formats worker label', () => {
    expect(buildWorkerLabel({ workerType: 'W', description: 'desc' })).toBe(
      'W - desc',
    );
  });

  it('filters workers by type and description', () => {
    const rows = [
      { workerType: 'ATS', description: '채용' },
      { workerType: 'URL', description: '이동' },
    ];
    expect(filterPromptWorkers(rows, 'ats')).toHaveLength(1);
    expect(filterPromptWorkers(rows, '이동')).toHaveLength(1);
    expect(filterPromptWorkers(rows, '')).toHaveLength(2);
  });

  it('builds stable model paths', () => {
    expect(
      buildPromptDiffModelPaths({
        environment: 'dev',
        selectedWorker: 'ATS WORKER',
        editorSessionKey: 7,
      }).originalModelPath,
    ).toContain('ATS%20WORKER');

    expect(
      buildPromptViewDiffModelPaths({
        environment: 'dev',
        selectedWorker: 'ATS',
        editorSessionKey: 3,
      }).modifiedModelPath,
    ).toContain('/view-modified/3');
  });
});
