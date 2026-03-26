import React, { useState, useEffect } from 'react';
import { RefreshCw, Loader2 } from 'lucide-react';
import { externalEventsAPI } from '../../services/api';
import { toast } from 'sonner';

const PROVIDER_CONFIG = {
  google: {
    label: 'Google Calendar',
    color: 'bg-blue-50 border-blue-200',
    dotOn: 'bg-[#4285F4]',
    dotOff: 'bg-slate-300',
    textOn: 'text-[#4285F4]',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none">
        <rect x="3" y="3" width="18" height="18" rx="3" stroke="#4285F4" strokeWidth="1.5" fill="#EFF3FF"/>
        <path d="M8 12h8M12 8v8" stroke="#4285F4" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  outlook: {
    label: 'Outlook Calendar',
    color: 'bg-sky-50 border-sky-200',
    dotOn: 'bg-[#0078D4]',
    dotOff: 'bg-slate-300',
    textOn: 'text-[#0078D4]',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none">
        <rect x="3" y="3" width="18" height="18" rx="3" stroke="#0078D4" strokeWidth="1.5" fill="#EFF6FF"/>
        <circle cx="12" cy="12" r="4" stroke="#0078D4" strokeWidth="1.5"/>
        <path d="M12 10v2l1.5 1" stroke="#0078D4" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
};

function formatTimeAgo(isoStr) {
  if (!isoStr) return null;
  const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
  if (diff < 60) return 'à l\'instant';
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)}h`;
  return `il y a ${Math.floor(diff / 86400)}j`;
}

export default function CalendarSyncPanel({ importSettings, onSettingChange, onSync, syncing, lastAutoCheckAt }) {
  const [togglingProvider, setTogglingProvider] = useState(null);
  // Live "time ago" ticker — re-renders every 30s
  const [, setTick] = useState(0);

  const providers = importSettings?.providers || {};
  const connectedProviders = Object.keys(providers);
  const hasAnyEnabled = connectedProviders.some(p => providers[p]?.import_enabled);

  useEffect(() => {
    if (!hasAnyEnabled) return;
    const id = setInterval(() => setTick(t => t + 1), 30_000);
    return () => clearInterval(id);
  }, [hasAnyEnabled]);

  if (connectedProviders.length === 0) return null;

  const handleToggle = async (provider, currentEnabled) => {
    setTogglingProvider(provider);
    try {
      await onSettingChange(provider, !currentEnabled);
      toast.success(!currentEnabled
        ? `Synchronisation ${PROVIDER_CONFIG[provider]?.label} activée`
        : `Synchronisation ${PROVIDER_CONFIG[provider]?.label} désactivée`
      );
    } catch {
      toast.error('Erreur lors du changement de paramètre');
    } finally {
      setTogglingProvider(null);
    }
  };

  return (
    <div className="mb-6" data-testid="calendar-sync-panel">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-slate-700 tracking-wide uppercase">Calendriers</h3>
          {hasAnyEnabled && lastAutoCheckAt && (
            <span className="text-[11px] text-slate-400" data-testid="auto-check-indicator">
              Contrôle auto : {formatTimeAgo(lastAutoCheckAt)}
            </span>
          )}
        </div>
        {hasAnyEnabled && (
          <button
            onClick={() => onSync(true)}
            disabled={syncing}
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 transition-colors disabled:opacity-50"
            data-testid="sync-refresh-btn"
          >
            {syncing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            Actualiser
          </button>
        )}
      </div>

      <div className="space-y-2">
        {connectedProviders.map(provider => {
          const config = PROVIDER_CONFIG[provider];
          if (!config) return null;
          const info = providers[provider];
          const enabled = info?.import_enabled;
          const isToggling = togglingProvider === provider;

          return (
            <div
              key={provider}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg border transition-all ${
                enabled ? config.color : 'bg-slate-50 border-slate-200'
              }`}
              data-testid={`sync-provider-${provider}`}
            >
              <div className="flex-shrink-0">{config.icon}</div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-medium ${enabled ? config.textOn : 'text-slate-500'}`}>
                    {config.label}
                  </span>
                  <span className={`w-2 h-2 rounded-full ${enabled ? config.dotOn : config.dotOff}`} />
                  <span className={`text-xs ${enabled ? config.textOn : 'text-slate-400'}`}>
                    {enabled ? 'Synchronisé' : 'Désactivé'}
                  </span>
                </div>
                {enabled && (
                  <p className="text-xs text-slate-400 mt-0.5">
                    {info.event_count > 0 && `${info.event_count} événement${info.event_count > 1 ? 's' : ''}`}
                    {info.event_count > 0 && info.last_synced_at && ' · '}
                    {info.last_synced_at && `Dernière sync : ${formatTimeAgo(info.last_synced_at)}`}
                  </p>
                )}
              </div>

              <button
                onClick={() => handleToggle(provider, enabled)}
                disabled={isToggling}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
                  enabled ? 'bg-emerald-500' : 'bg-slate-300'
                } ${isToggling ? 'opacity-50' : ''}`}
                data-testid={`sync-toggle-${provider}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  enabled ? 'translate-x-6' : 'translate-x-1'
                }`} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
