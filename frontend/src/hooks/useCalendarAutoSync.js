import { useEffect, useRef, useState, useCallback } from 'react';

const SYNC_INTERVAL_MS = 120_000; // 2 minutes
const MIN_DELAY_BEFORE_RESYNC_MS = 60_000; // 1 minute — cooldown au retour d'onglet

/**
 * useCalendarAutoSync — Hook centralisé pour l'auto-synchronisation des calendriers.
 *
 * @param {Object} opts
 * @param {boolean} opts.enabled    — Au moins un provider est activé
 * @param {boolean} opts.syncing    — Une sync manuelle est en cours (bouton "Actualiser")
 * @param {Function} opts.onSync    — Callback async exécutée à chaque tick de sync
 * @returns {{ lastAutoCheckAt: string|null }}
 */
export function useCalendarAutoSync({ enabled, syncing, onSync }) {
  const [lastAutoCheckAt, setLastAutoCheckAt] = useState(null);

  const syncInProgressRef = useRef(false);
  const syncingRef = useRef(false);
  const lastSyncTimeRef = useRef(0);
  const onSyncRef = useRef(onSync);

  // Keep refs fresh without re-triggering effects
  useEffect(() => { syncingRef.current = syncing; }, [syncing]);
  useEffect(() => { onSyncRef.current = onSync; }, [onSync]);

  const runSync = useCallback(async () => {
    if (syncInProgressRef.current || syncingRef.current || document.hidden) return;
    syncInProgressRef.current = true;
    try {
      await onSyncRef.current();
      lastSyncTimeRef.current = Date.now();
      setLastAutoCheckAt(new Date().toISOString());
    } catch { /* silent */ }
    finally { syncInProgressRef.current = false; }
  }, []);

  useEffect(() => {
    if (!enabled) return;

    // Interval — ticks every 2 min, skips if tab hidden or sync in progress
    const intervalId = setInterval(runSync, SYNC_INTERVAL_MS);

    // Visibility — sync immédiate au retour si cooldown écoulé
    const onVisibilityChange = () => {
      if (document.hidden) return;
      const elapsed = Date.now() - lastSyncTimeRef.current;
      if (elapsed >= MIN_DELAY_BEFORE_RESYNC_MS) {
        runSync();
      }
    };
    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      clearInterval(intervalId);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [enabled, runSync]);

  return { lastAutoCheckAt };
}
