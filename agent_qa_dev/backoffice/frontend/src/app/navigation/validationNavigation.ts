import type { ValidationSection } from '../../features/validations/types';

const HISTORY_DETAIL_TAB_VALUES = new Set(['history', 'results']);

export type MenuKey =
  | 'validation-run'
  | 'validation-history'
  | 'validation-dashboard'
  | 'validation-data-queries'
  | 'validation-data-query-groups'
  | 'validation-data-test-sets'
  | 'validation-settings'
  | 'generic-legacy'
  | 'prompt';

export const MENU_KEYS: MenuKey[] = [
  'validation-run',
  'validation-history',
  'validation-dashboard',
  'validation-data-queries',
  'validation-data-query-groups',
  'validation-data-test-sets',
  'validation-settings',
  'generic-legacy',
  'prompt',
];

export const MENU_PATHS: Record<MenuKey, string> = {
  'validation-run': '/validation/run',
  'validation-history': '/validation/history',
  'validation-dashboard': '/validation/dashboard',
  'validation-data-queries': '/validation-data/queries',
  'validation-data-query-groups': '/validation-data/query-groups',
  'validation-data-test-sets': '/validation-data/test-sets',
  'validation-settings': '/validation-settings',
  'generic-legacy': '/generic-legacy',
  prompt: '/prompt',
};

export function normalizePathname(pathname: string) {
  const normalized = pathname.replace(/\/+$/, '');
  return normalized || '/';
}

export function resolveMenu(pathname: string): MenuKey {
  if (pathname === '/validation-data/queries' || pathname === '/queries') return 'validation-data-queries';
  if (pathname === '/validation-data/query-groups' || pathname === '/query-groups') return 'validation-data-query-groups';
  if (pathname === '/validation-data/test-sets') return 'validation-data-test-sets';
  if (pathname === '/validation-settings') return 'validation-settings';
  if (pathname === '/prompt') return 'prompt';
  if (pathname === '/generic-legacy') return 'generic-legacy';
  if (pathname === '/validation/dashboard') return 'validation-dashboard';
  if (pathname === '/validation/history' || pathname.startsWith('/validation/history/')) return 'validation-history';
  return 'validation-run';
}

export function resolveValidationSection(pathname: string): ValidationSection {
  if (pathname === '/validation/dashboard') return 'dashboard';
  if (pathname === '/validation/history') return 'history';
  if (pathname.startsWith('/validation/history/')) return 'history-detail';
  return 'run';
}

export function resolveHistoryRunId(pathname: string) {
  const prefix = '/validation/history/';
  if (!pathname.startsWith(prefix)) return undefined;
  const encodedId = pathname.slice(prefix.length).split('/')[0];
  if (!encodedId) return undefined;
  try {
    return decodeURIComponent(encodedId);
  } catch {
    return encodedId;
  }
}

export function resolveHistoryDetailTab(search: string) {
  const params = new URLSearchParams(search);
  const tab = String(params.get('tab') || '').trim().toLowerCase();
  if (HISTORY_DETAIL_TAB_VALUES.has(tab)) {
    return tab as 'history' | 'results';
  }
  return 'history' as const;
}

export function isKnownPath(pathname: string) {
  return (
    pathname === '/login'
    || pathname === '/'
    || pathname === '/validation/run'
    || pathname === '/validation/history'
    || pathname.startsWith('/validation/history/')
    || pathname === '/validation/dashboard'
    || pathname === '/validation-data/queries'
    || pathname === '/validation-data/query-groups'
    || pathname === '/validation-data/test-sets'
    || pathname === '/queries'
    || pathname === '/query-groups'
    || pathname === '/validation-settings'
    || pathname === '/prompt'
    || pathname === '/generic-legacy'
  );
}
