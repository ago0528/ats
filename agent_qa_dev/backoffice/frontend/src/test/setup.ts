import { afterEach, vi } from 'vitest';

afterEach(() => {
  // Keep tests isolated from each other by resetting timers and modules.
  vi.useRealTimers();
});
