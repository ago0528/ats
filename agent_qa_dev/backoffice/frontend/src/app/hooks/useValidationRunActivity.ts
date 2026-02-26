import { useCallback, useEffect, useState } from 'react';

import {
  listValidationRunActivity,
  markValidationRunActivityRead,
} from '../../api/validation';
import type { ValidationRunActivityItem } from '../../api/types/validation';
import type { Environment } from '../EnvironmentScope';
import type { RuntimeSecrets } from '../types';
import { buildRuntimeActorKey } from '../utils/runtimeSecrets';

type UseValidationRunActivityParams = {
  environment: Environment;
  runtimeSecrets: RuntimeSecrets;
  pollingMs?: number;
};

export function useValidationRunActivity({
  environment,
  runtimeSecrets,
  pollingMs = 5000,
}: UseValidationRunActivityParams) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [actorKey, setActorKey] = useState('');
  const [items, setItems] = useState<ValidationRunActivityItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    let active = true;
    const resolveActorKey = async () => {
      const nextActorKey = await buildRuntimeActorKey(runtimeSecrets);
      if (!active) return;
      setActorKey(nextActorKey);
    };
    void resolveActorKey();
    return () => {
      active = false;
    };
  }, [runtimeSecrets.bearer, runtimeSecrets.cms, runtimeSecrets.mrs]);

  const refresh = useCallback(async () => {
    if (!actorKey) {
      setItems([]);
      setUnreadCount(0);
      return;
    }
    setLoading(true);
    try {
      const data = await listValidationRunActivity({
        environment,
        actorKey,
        limit: 20,
      });
      setItems(data.items || []);
      setUnreadCount(Math.max(0, Number(data.unreadCount || 0)));
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, [actorKey, environment]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!actorKey) return;
    const timer = window.setInterval(() => {
      void refresh();
    }, Math.max(1000, pollingMs));
    return () => window.clearInterval(timer);
  }, [actorKey, pollingMs, refresh]);

  const markRunRead = useCallback(async (runId: string) => {
    if (!actorKey || !runId) return;
    try {
      await markValidationRunActivityRead({
        environment,
        actorKey,
        runIds: [runId],
      });
      await refresh();
    } catch (error) {
      console.error(error);
    }
  }, [actorKey, environment, refresh]);

  const markAllRead = useCallback(async () => {
    if (!actorKey) return;
    try {
      await markValidationRunActivityRead({
        environment,
        actorKey,
        markAll: true,
      });
      await refresh();
    } catch (error) {
      console.error(error);
    }
  }, [actorKey, environment, refresh]);

  return {
    open,
    setOpen,
    loading,
    items,
    unreadCount,
    markRunRead,
    markAllRead,
    refresh,
    hasActorKey: Boolean(actorKey),
  };
}
