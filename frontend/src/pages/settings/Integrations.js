import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { calendarAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { ArrowLeft, Calendar, CheckCircle, XCircle, Loader2, ExternalLink, Unlink, Zap, ZapOff } from 'lucide-react';
import { toast } from 'sonner';
import { formatDateLongFr } from '../../utils/dateFormat';

export default function Integrations() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [googleConnection, setGoogleConnection] = useState(null);
  const [outlookConnection, setOutlookConnection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [connectingGoogle, setConnectingGoogle] = useState(false);
  const [connectingOutlook, setConnectingOutlook] = useState(false);
  const [disconnecting, setDisconnecting] = useState(null);
  const [autoSyncEnabled, setAutoSyncEnabled] = useState(false);
  const [autoSyncProvider, setAutoSyncProvider] = useState(null);
  const [savingAutoSync, setSavingAutoSync] = useState(false);

  useEffect(() => { loadAll(); }, []);

  useEffect(() => {
    const googleResult = searchParams.get('google');
    const outlookResult = searchParams.get('outlook');
    if (googleResult === 'connected') {
      toast.success('Google Calendar connecté avec succès');
      loadAll();
    } else if (googleResult === 'error') {
      toast.error(`Échec Google Calendar (${searchParams.get('reason') || 'erreur'})`);
    }
    if (outlookResult === 'connected') {
      toast.success('Outlook Calendar connecté avec succès');
      loadAll();
    } else if (outlookResult === 'error') {
      toast.error(`Échec Outlook Calendar (${searchParams.get('reason') || 'erreur'})`);
    }
    if (googleResult || outlookResult) {
      searchParams.delete('google'); searchParams.delete('outlook'); searchParams.delete('reason');
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const loadAll = async () => {
    try {
      const [connRes, syncRes] = await Promise.all([
        calendarAPI.listConnections(),
        calendarAPI.getAutoSyncSettings()
      ]);
      const connections = connRes.data.connections || [];
      setGoogleConnection(connections.find(c => c.provider === 'google') || null);
      setOutlookConnection(connections.find(c => c.provider === 'outlook') || null);
      setAutoSyncEnabled(syncRes.data.auto_sync_enabled || false);
      setAutoSyncProvider(syncRes.data.auto_sync_provider || null);
    } catch (error) {
      console.error('Error loading:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveAutoSync = async (enabled, provider) => {
    setSavingAutoSync(true);
    try {
      await calendarAPI.updateAutoSyncSettings({
        auto_sync_enabled: enabled,
        auto_sync_provider: provider
      });
      setAutoSyncEnabled(enabled);
      setAutoSyncProvider(enabled ? provider : null);
      toast.success(enabled ? 'Auto-sync activé' : 'Auto-sync désactivé');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Erreur lors de la sauvegarde');
    } finally {
      setSavingAutoSync(false);
    }
  };

  const handleConnect = async (provider) => {
    const setConnecting = provider === 'google' ? setConnectingGoogle : setConnectingOutlook;
    setConnecting(true);
    try {
      const fn = provider === 'google' ? calendarAPI.connectGoogle : calendarAPI.connectOutlook;
      const response = await fn();
      if (response.data.authorization_url) {
        window.location.href = response.data.authorization_url;
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Erreur lors de la connexion');
      setConnecting(false);
    }
  };

  const handleDisconnect = async (provider) => {
    setDisconnecting(provider);
    try {
      const fn = provider === 'google' ? calendarAPI.disconnectGoogle : calendarAPI.disconnectOutlook;
      await fn();
      toast.success(`${provider === 'google' ? 'Google' : 'Outlook'} Calendar déconnecté`);
      if (provider === 'google') setGoogleConnection(null);
      else setOutlookConnection(null);
    } catch (error) {
      toast.error('Erreur lors de la déconnexion');
    } finally {
      setDisconnecting(null);
    }
  };

  const renderProviderCard = (provider, connection, connectingState) => {
    const isGoogle = provider === 'google';
    const label = isGoogle ? 'Google Calendar' : 'Outlook / Microsoft 365';
    const email = isGoogle ? connection?.google_email : connection?.outlook_email;
    const accentColor = isGoogle ? 'blue' : 'sky';
    const testId = isGoogle ? 'google-calendar-card' : 'outlook-calendar-card';

    return (
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid={testId} key={provider}>
        <div className="p-6">
          <div className="flex items-start gap-4">
            <div className={`w-12 h-12 rounded-lg bg-${accentColor}-50 flex items-center justify-center flex-shrink-0`}>
              <Calendar className={`w-6 h-6 text-${accentColor}-600`} />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-lg font-semibold text-slate-900 mb-1">{label}</h3>
              <p className="text-sm text-slate-600">
                Synchronisez vos rendez-vous NLYT avec {isGoogle ? 'votre agenda Google' : 'votre calendrier Outlook'}.
              </p>
            </div>
          </div>
        </div>

        {connection && connection.status === 'connected' ? (
          <div className="border-t border-slate-200 bg-slate-50 px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-slate-900" data-testid={`${provider}-connected-email`}>
                    {email || 'Compte connecté'}
                  </p>
                  <p className="text-xs text-slate-500">
                    Connecté le {formatDateLongFr(connection.connected_at)}
                  </p>
                </div>
              </div>
              <Button
                variant="outline" size="sm"
                onClick={() => handleDisconnect(provider)}
                disabled={disconnecting === provider}
                className="text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700"
                data-testid={`disconnect-${provider}-btn`}
              >
                {disconnecting === provider ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Unlink className="w-4 h-4 mr-1" />}
                Déconnecter
              </Button>
            </div>
          </div>
        ) : connection && connection.status === 'expired' ? (
          <div className="border-t border-slate-200 bg-amber-50 px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <XCircle className="w-5 h-5 text-amber-600 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-slate-900">Session expirée</p>
                  <p className="text-xs text-slate-500">{email || 'Reconnectez pour restaurer la synchronisation'}</p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={() => handleConnect(provider)} disabled={connectingState} data-testid={`reconnect-${provider}-btn`}>
                  {connectingState ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <ExternalLink className="w-4 h-4 mr-1" />}
                  Reconnecter
                </Button>
                <Button variant="outline" size="sm" onClick={() => handleDisconnect(provider)} disabled={disconnecting === provider}
                  className="text-red-600 border-red-200 hover:bg-red-50">
                  <Unlink className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <div className="border-t border-slate-200 px-6 py-4">
            <Button onClick={() => handleConnect(provider)} disabled={connectingState} className="w-full sm:w-auto" data-testid={`connect-${provider}-btn`}>
              {connectingState ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <ExternalLink className="w-4 h-4 mr-2" />}
              Connecter {label}
            </Button>
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background py-8 px-4">
      <div className="max-w-3xl mx-auto">
        <Link to="/settings">
          <Button variant="ghost" className="mb-6">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Retour aux paramètres
          </Button>
        </Link>

        <h1 className="text-3xl font-bold text-slate-900 mb-2">Intégrations</h1>
        <p className="text-slate-600 mb-8">
          Connectez vos services externes pour synchroniser vos rendez-vous.
        </p>

        <div className="space-y-4">
          {renderProviderCard('google', googleConnection, connectingGoogle)}
          {renderProviderCard('outlook', outlookConnection, connectingOutlook)}
        </div>

        {/* Auto-Sync Section */}
        {(googleConnection?.status === 'connected' || outlookConnection?.status === 'connected') && (
          <div className="mt-8 bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="auto-sync-section">
            <div className="p-6">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-lg bg-violet-50 flex items-center justify-center flex-shrink-0">
                  <Zap className="w-6 h-6 text-violet-600" />
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-slate-900 mb-1">Auto-sync calendrier</h3>
                  <p className="text-sm text-slate-600">
                    Chaque nouveau rendez-vous créé dans NLYT sera automatiquement ajouté à votre calendrier connecté (sens unique : NLYT vers votre calendrier).
                  </p>
                </div>
              </div>
            </div>

            <div className="border-t border-slate-200 px-6 py-4 space-y-4">
              {/* Provider selector */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Calendrier préféré pour l'auto-sync
                </label>
                <div className="flex gap-3">
                  {googleConnection?.status === 'connected' && (
                    <button
                      onClick={() => !savingAutoSync && handleSaveAutoSync(true, 'google')}
                      disabled={savingAutoSync}
                      className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-all ${
                        autoSyncEnabled && autoSyncProvider === 'google'
                          ? 'border-violet-300 bg-violet-50 text-violet-800 ring-2 ring-violet-200'
                          : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50'
                      }`}
                      data-testid="auto-sync-google-btn"
                    >
                      <Calendar className="w-4 h-4" />
                      Google Calendar
                      {autoSyncEnabled && autoSyncProvider === 'google' && <Zap className="w-3.5 h-3.5 text-violet-600" />}
                    </button>
                  )}
                  {outlookConnection?.status === 'connected' && (
                    <button
                      onClick={() => !savingAutoSync && handleSaveAutoSync(true, 'outlook')}
                      disabled={savingAutoSync}
                      className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-all ${
                        autoSyncEnabled && autoSyncProvider === 'outlook'
                          ? 'border-violet-300 bg-violet-50 text-violet-800 ring-2 ring-violet-200'
                          : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50'
                      }`}
                      data-testid="auto-sync-outlook-btn"
                    >
                      <Calendar className="w-4 h-4" />
                      Outlook Calendar
                      {autoSyncEnabled && autoSyncProvider === 'outlook' && <Zap className="w-3.5 h-3.5 text-violet-600" />}
                    </button>
                  )}
                </div>
              </div>

              {/* Status + disable */}
              {autoSyncEnabled && (
                <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-violet-600" />
                    <span className="text-sm text-slate-700">
                      Auto-sync actif vers <strong>{autoSyncProvider === 'google' ? 'Google Calendar' : 'Outlook Calendar'}</strong>
                    </span>
                  </div>
                  <Button
                    variant="outline" size="sm"
                    onClick={() => handleSaveAutoSync(false, null)}
                    disabled={savingAutoSync}
                    className="text-slate-600"
                    data-testid="disable-auto-sync-btn"
                  >
                    {savingAutoSync ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <ZapOff className="w-4 h-4 mr-1" />}
                    Désactiver
                  </Button>
                </div>
              )}

              {!autoSyncEnabled && (
                <p className="text-xs text-slate-500 pt-1">
                  Cliquez sur un calendrier ci-dessus pour activer l'auto-sync. Chaque nouveau rendez-vous sera automatiquement ajouté à ce calendrier.
                </p>
              )}
            </div>
          </div>
        )}

        <div className="mt-8 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <p className="text-sm text-amber-800">
            <strong>Alternative :</strong> Vous pouvez aussi exporter chaque rendez-vous en fichier ICS
            depuis la page de détail du rendez-vous (compatible avec tous les calendriers).
          </p>
        </div>
      </div>
    </div>
  );
}
