export type PromptWorker = {
  workerType: string;
  description: string;
};

export function buildWorkerLabel(worker: PromptWorker): string {
  return `${worker.workerType} - ${worker.description}`;
}

export function filterPromptWorkers(
  workers: PromptWorker[],
  search: string,
): PromptWorker[] {
  const keyword = String(search || '').trim().toLowerCase();
  if (!keyword) return workers;

  return workers.filter(
    (worker) =>
      worker.workerType.toLowerCase().includes(keyword)
      || worker.description.toLowerCase().includes(keyword),
  );
}

export function buildPromptDiffModelPaths({
  environment,
  selectedWorker,
  editorSessionKey,
}: {
  environment: string;
  selectedWorker: string;
  editorSessionKey: number;
}) {
  const encodedWorker = encodeURIComponent(selectedWorker || 'unspecified');
  return {
    originalModelPath:
      `inmemory://prompt/${environment}/${encodedWorker}/original/${editorSessionKey}`,
    modifiedModelPath:
      `inmemory://prompt/${environment}/${encodedWorker}/modified/${editorSessionKey}`,
  };
}

export function buildPromptViewDiffModelPaths({
  environment,
  selectedWorker,
  editorSessionKey,
}: {
  environment: string;
  selectedWorker: string;
  editorSessionKey: number;
}) {
  const encodedWorker = encodeURIComponent(selectedWorker || 'unspecified');
  return {
    originalModelPath:
      `inmemory://prompt/${environment}/${encodedWorker}/view-original/${editorSessionKey}`,
    modifiedModelPath:
      `inmemory://prompt/${environment}/${encodedWorker}/view-modified/${editorSessionKey}`,
  };
}
