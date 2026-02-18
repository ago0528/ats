import { createContext, useContext } from 'react';

export const STANDARD_PAGE_SIZE_LIMIT_MIN = 50;
export const STANDARD_PAGE_SIZE_LIMIT_DEFAULT = 100;

export function normalizeStandardPageSizeLimit(value: number | null | undefined) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return STANDARD_PAGE_SIZE_LIMIT_DEFAULT;
  return Math.max(STANDARD_PAGE_SIZE_LIMIT_MIN, Math.trunc(parsed));
}

type StandardPaginationConfig = {
  pageSizeLimit: number;
};

const defaultConfig: StandardPaginationConfig = {
  pageSizeLimit: STANDARD_PAGE_SIZE_LIMIT_DEFAULT,
};

export const StandardPaginationConfigContext = createContext<StandardPaginationConfig>(defaultConfig);

export function useStandardPaginationConfig() {
  return useContext(StandardPaginationConfigContext);
}
