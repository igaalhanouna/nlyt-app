import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { calendarAPI, videoEvidenceAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { ArrowLeft, Calendar, CheckCircle, XCircle, Loader2, ExternalLink, Unlink, Zap, ZapOff, Video, Monitor, Shield, Users, ChevronDown, ChevronUp, AlertTriangle, Settings2, Info } from 'lucide-react';
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

  // Video provider states
  const [videoProviders, setVideoProviders] = useState(null);
  const [expandedProvider, setExpandedProvider] = useState(null);
  const [connectingZoom, setConnectingZoom] = useState(false);
  const [connectingTeams, setConnectingTeams] = useState(false);
  const [zoomForm, setZoomForm] = useState({ zoom_email: '' });
  const [teamsForm, setTeamsForm] = useState({ azure_user_id: '', teams_email: '' });

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
      const [connRes, syncRes, videoRes] = await Promise.all([
        calendarAPI.listConnections(),
        calendarAPI.getAutoSyncSettings(),
        videoEvidenceAPI.providerStatus().catch(() => ({ data: null })),
      ]);
      const connections = connRes.data.connections || [];
      setGoogleConnection(connections.find(c => c.provider === 'google') || null);
      setOutlookConnection(connections.find(c => c.provider === 'outlook') || null);
      setAutoSyncEnabled(syncRes.data.auto_sync_enabled || false);
      setAutoSyncProvider(syncRes.data.auto_sync_provider || null);
      if (videoRes.data) setVideoProviders(videoRes.data);
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
      if (provider === 'google') {
        await calendarAPI.disconnectGoogle();
        setGoogleConnection(null);
        toast.success('Google Calendar déconnecté');
      } else if (provider === 'outlook') {
        await calendarAPI.disconnectOutlook();
        setOutlookConnection(null);
        toast.success('Outlook Calendar déconnecté');
      } else if (provider === 'zoom') {
        await videoEvidenceAPI.disconnectZoom();
        toast.success('Zoom déconnecté');
        loadAll();
      } else if (provider === 'teams') {
        await videoEvidenceAPI.disconnectTeams();
        toast.success('Microsoft Teams déconnecté');
        loadAll();
      }
    } catch (error) {
      toast.error('Erreur lors de la déconnexion');
    } finally {
      setDisconnecting(null);
    }
  };

  const handleConnectZoom = async () => {
    setConnectingZoom(true);
    try {
      await videoEvidenceAPI.connectZoom({ zoom_email: zoomForm.zoom_email || undefined });
      toast.success('Zoom configuré avec succès');
      setExpandedProvider(null);
      loadAll();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Erreur de configuration Zoom');
    } finally {
      setConnectingZoom(false);
    }
  };

  const handleConnectTeams = async () => {
    if (!teamsForm.azure_user_id?.trim()) {
      toast.error('L\'identifiant utilisateur Azure AD est requis');
      return;
    }
    setConnectingTeams(true);
    try {
      await videoEvidenceAPI.connectTeams({
        azure_user_id: teamsForm.azure_user_id.trim(),
        teams_email: teamsForm.teams_email || undefined,
      });
      toast.success('Microsoft Teams configuré avec succès');
      setExpandedProvider(null);
      loadAll();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Erreur de configuration Teams');
    } finally {
      setConnectingTeams(false);
    }
  };

  // =========================================================
  //  Calendar Provider Card (Google / Outlook — existing logic)
  // =========================================================
  const renderCalendarCard = (provider, connection, connectingState) => {
    const isGoogle = provider === 'google';
    const label = isGoogle ? 'Google Calendar' : 'Outlook / Microsoft 365';
    const email = isGoogle ? connection?.google_email : connection?.outlook_email;
    const testId = isGoogle ? 'google-calendar-card' : 'outlook-calendar-card';
    const isConnected = connection?.status === 'connected';
    const isExpired = connection?.status === 'expired';
    const meetConnected = isGoogle && isConnected;

    return (
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden" data-testid={testId} key={provider}>
        <div className="p-5">
          <div className="flex items-start gap-4">
            <div className={`w-11 h-11 rounded-lg flex items-center justify-center flex-shrink-0 ${isGoogle ? 'bg-blue-50' : 'bg-sky-50'}`}>
              <Calendar className={`w-5 h-5 ${isGoogle ? 'text-blue-600' : 'text-sky-600'}`} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-base font-semibold text-slate-900">{label}</h3>
                {isConnected && <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />}
              </div>
              <p className="text-sm text-slate-500">
                Synchronisez vos rendez-vous avec {isGoogle ? 'votre agenda Google' : 'votre calendrier Outlook'}.
              </p>
              {/* Capabilities badges */}
              <div className="flex flex-wrap gap-1.5 mt-2">
                <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-medium">
                  <Calendar className="w-3 h-3" /> Calendrier
                </span>
                {isGoogle && (
                  <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${meetConnected ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-400'}`} data-testid="meet-badge">
                    <Video className="w-3 h-3" /> Google Meet
                    {meetConnected && <CheckCircle className="w-3 h-3" />}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {isConnected ? (
          <div className="border-t border-slate-100 bg-slate-50/50 px-5 py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-slate-800" data-testid={`${provider}-connected-email`}>{email || 'Compte connecté'}</p>
                  <p className="text-xs text-slate-400">Connecté le {formatDateLongFr(connection.connected_at)}</p>
                </div>
              </div>
              <Button
                variant="outline" size="sm"
                onClick={() => handleDisconnect(provider)}
                disabled={disconnecting === provider}
                className="text-red-500 border-red-200 hover:bg-red-50 hover:text-red-600 h-8 text-xs"
                data-testid={`disconnect-${provider}-btn`}
              >
                {disconnecting === provider ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Unlink className="w-3.5 h-3.5 mr-1" />}
                Déconnecter
              </Button>
            </div>
            {isGoogle && meetConnected && (
              <div className="mt-2 pt-2 border-t border-slate-100">
                <p className="text-xs text-emerald-700 flex items-center gap-1">
                  <Video className="w-3 h-3" />
                  Création de liens Google Meet activée via cette connexion.
                </p>
              </div>
            )}
            {!isGoogle && provider === 'outlook' && !connection?.has_online_meetings_scope && (
              <div className="mt-2 pt-2 border-t border-orange-100" data-testid="outlook-upgrade-scope-banner">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-orange-700">
                    <span className="font-medium">Mise à jour recommandée :</span> Reconnectez votre compte Outlook pour créer les réunions Teams directement sous votre propre identité.
                  </p>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleConnect(provider)}
                    disabled={connectingState}
                    className="h-7 text-xs border-orange-300 text-orange-700 hover:bg-orange-50 shrink-0"
                    data-testid="upgrade-outlook-scope-btn"
                  >
                    {connectingState ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <ExternalLink className="w-3 h-3 mr-1" />}
                    Mettre à jour
                  </Button>
                </div>
              </div>
            )}
            {!isGoogle && provider === 'outlook' && connection?.has_online_meetings_scope && (
              <div className="mt-2 pt-2 border-t border-slate-100">
                <p className="text-xs text-emerald-700 flex items-center gap-1">
                  <Video className="w-3 h-3" />
                  Création de réunions Teams activée sous votre propre identité.
                </p>
              </div>
            )}
          </div>
        ) : isExpired ? (
          <div className="border-t border-amber-100 bg-amber-50/50 px-5 py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <XCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-slate-800">Session expirée</p>
                  <p className="text-xs text-slate-400">{email || 'Reconnectez votre compte'}</p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={() => handleConnect(provider)} disabled={connectingState} className="h-8 text-xs" data-testid={`reconnect-${provider}-btn`}>
                  {connectingState ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <ExternalLink className="w-3.5 h-3.5 mr-1" />}
                  Reconnecter
                </Button>
                <Button variant="outline" size="sm" onClick={() => handleDisconnect(provider)} disabled={disconnecting === provider}
                  className="text-red-500 border-red-200 hover:bg-red-50 h-8 text-xs">
                  <Unlink className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <div className="border-t border-slate-100 px-5 py-3">
            <Button onClick={() => handleConnect(provider)} disabled={connectingState} size="sm" className="h-8 text-xs" data-testid={`connect-${provider}-btn`}>
              {connectingState ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <ExternalLink className="w-3.5 h-3.5 mr-1" />}
              Connecter {label}
            </Button>
          </div>
        )}
      </div>
    );
  };

  // =========================================================
  //  Video Provider Card (Zoom / Teams)
  // =========================================================
  const renderVideoProviderCard = (providerKey) => {
    const info = videoProviders?.[providerKey];
    if (!info) return null;

    const isZoom = providerKey === 'zoom';
    const isTeams = providerKey === 'teams';
    const isMeet = providerKey === 'meet';

    // Google Meet: handled by calendar card above
    if (isMeet) return null;

    const label = info.label || (isZoom ? 'Zoom' : 'Microsoft Teams');
    const isConnected = info.connected;
    const isPlatformConfigured = info.configured;
    const email = info.email;
    const isExpanded = expandedProvider === providerKey;

    const features = info.features || [];
    const canCreate = features.includes('create_meeting');
    const canAttendance = features.includes('fetch_attendance');

    const accentColor = isZoom ? 'blue' : 'violet';
    const iconBg = isZoom ? 'bg-blue-50' : 'bg-violet-50';
    const iconColor = isZoom ? 'text-blue-600' : 'text-violet-600';

    return (
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden" data-testid={`${providerKey}-card`} key={providerKey}>
        <div className="p-5">
          <div className="flex items-start gap-4">
            <div className={`w-11 h-11 rounded-lg flex items-center justify-center flex-shrink-0 ${iconBg}`}>
              <Monitor className={`w-5 h-5 ${iconColor}`} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-base font-semibold text-slate-900">{label}</h3>
                {isConnected && <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />}
              </div>
              <p className="text-sm text-slate-500">
                {isZoom
                  ? 'Créez des réunions Zoom et récupérez les présences directement depuis NLYT.'
                  : 'Créez des réunions Teams et récupérez les présences via Microsoft Graph.'
                }
              </p>
              {/* Feature badges */}
              <div className="flex flex-wrap gap-1.5 mt-2">
                {canCreate && (
                  <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${isConnected ? `bg-${accentColor === 'blue' ? 'blue' : 'violet'}-50 text-${accentColor === 'blue' ? 'blue' : 'violet'}-700` : 'bg-slate-100 text-slate-500'}`}>
                    <Video className="w-3 h-3" /> Création de réunion
                  </span>
                )}
                {canAttendance && (
                  <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${isConnected ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                    <Users className="w-3 h-3" /> Présences auto
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {isConnected ? (
          <div className="border-t border-slate-100 bg-slate-50/50 px-5 py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-slate-800" data-testid={`${providerKey}-connected-email`}>
                    {email || (isPlatformConfigured ? 'Configuré (niveau plateforme)' : 'Connecté')}
                  </p>
                  {info.connected_at && (
                    <p className="text-xs text-slate-400">Connecté le {formatDateLongFr(info.connected_at)}</p>
                  )}
                  {isPlatformConfigured && !email && (
                    <p className="text-xs text-slate-400">Configuration serveur active</p>
                  )}
                </div>
              </div>
              <Button
                variant="outline" size="sm"
                onClick={() => handleDisconnect(providerKey)}
                disabled={disconnecting === providerKey}
                className="text-red-500 border-red-200 hover:bg-red-50 hover:text-red-600 h-8 text-xs"
                data-testid={`disconnect-${providerKey}-btn`}
              >
                {disconnecting === providerKey ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Unlink className="w-3.5 h-3.5 mr-1" />}
                Déconnecter
              </Button>
            </div>
          </div>
        ) : (
          <div className="border-t border-slate-100 px-5 py-3">
            {!isExpanded ? (
              <Button
                onClick={() => setExpandedProvider(providerKey)}
                size="sm" className="h-8 text-xs"
                data-testid={`connect-${providerKey}-btn`}
              >
                <Settings2 className="w-3.5 h-3.5 mr-1" />
                Configurer {label}
              </Button>
            ) : (
              <div className="space-y-3" data-testid={`${providerKey}-config-form`}>
                <p className="text-xs text-slate-600">
                  {isZoom
                    ? 'Configurez votre intégration Zoom. Les credentials serveur (Account ID, Client ID, Client Secret) doivent être configurés par un administrateur.'
                    : 'Configurez votre intégration Microsoft Teams. Renseignez votre identifiant Azure AD pour permettre la création de réunions Teams.'
                  }
                </p>

                {isZoom && (
                  <div className="space-y-2">
                    <div>
                      <Label htmlFor="zoom-email" className="text-xs text-slate-600">Email Zoom (optionnel)</Label>
                      <Input
                        id="zoom-email"
                        type="email"
                        value={zoomForm.zoom_email}
                        onChange={(e) => setZoomForm({ ...zoomForm, zoom_email: e.target.value })}
                        placeholder="votre@email.com"
                        className="mt-1 h-8 text-sm"
                        data-testid="zoom-email-input"
                      />
                    </div>
                    {!isPlatformConfigured && (
                      <div className="flex items-start gap-2 p-2 bg-amber-50 border border-amber-200 rounded-md">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-600 mt-0.5 flex-shrink-0" />
                        <p className="text-xs text-amber-700">
                          Les credentials Zoom (Account ID, Client ID, Secret) ne sont pas encore configurés sur le serveur.
                          Contactez votre administrateur ou ajoutez-les dans les variables d'environnement.
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {isTeams && (
                  <div className="space-y-2">
                    <div>
                      <Label htmlFor="teams-azure-id" className="text-xs text-slate-600">Identifiant utilisateur Azure AD</Label>
                      <Input
                        id="teams-azure-id"
                        value={teamsForm.azure_user_id}
                        onChange={(e) => setTeamsForm({ ...teamsForm, azure_user_id: e.target.value })}
                        placeholder="ex: user@votredomaine.com ou UUID Azure AD"
                        className="mt-1 h-8 text-sm"
                        data-testid="teams-azure-id-input"
                      />
                      <p className="text-xs text-slate-400 mt-1">Email Microsoft ou Object ID Azure AD (portal.azure.com)</p>
                    </div>
                    <div>
                      <Label htmlFor="teams-email" className="text-xs text-slate-600">Email Teams (optionnel)</Label>
                      <Input
                        id="teams-email"
                        type="email"
                        value={teamsForm.teams_email}
                        onChange={(e) => setTeamsForm({ ...teamsForm, teams_email: e.target.value })}
                        placeholder="votre@entreprise.com"
                        className="mt-1 h-8 text-sm"
                        data-testid="teams-email-input"
                      />
                    </div>
                    {!isPlatformConfigured && (
                      <div className="flex items-start gap-2 p-2 bg-amber-50 border border-amber-200 rounded-md">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-600 mt-0.5 flex-shrink-0" />
                        <p className="text-xs text-amber-700">
                          Les credentials Azure (Tenant ID, Client ID, Secret) ne sont pas encore configurés sur le serveur.
                          Contactez votre administrateur.
                        </p>
                      </div>
                    )}
                  </div>
                )}

                <div className="flex gap-2 pt-1">
                  <Button
                    size="sm" className="h-8 text-xs"
                    onClick={isZoom ? handleConnectZoom : handleConnectTeams}
                    disabled={isZoom ? connectingZoom : connectingTeams}
                    data-testid={`submit-connect-${providerKey}-btn`}
                  >
                    {(isZoom ? connectingZoom : connectingTeams) ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <CheckCircle className="w-3.5 h-3.5 mr-1" />}
                    Enregistrer
                  </Button>
                  <Button
                    variant="outline" size="sm" className="h-8 text-xs"
                    onClick={() => setExpandedProvider(null)}
                  >
                    Annuler
                  </Button>
                </div>
              </div>
            )}
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

        <h1 className="text-2xl font-bold text-slate-900 mb-1" data-testid="integrations-title">Intégrations</h1>
        <p className="text-sm text-slate-500 mb-8">
          Connectez vos services pour synchroniser vos calendriers et gérer vos visioconférences.
        </p>

        {/* ========= SECTION: Calendriers ========= */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Calendar className="w-4 h-4 text-slate-400" />
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider" data-testid="section-calendriers">Calendriers</h2>
          </div>
          <div className="space-y-3">
            {renderCalendarCard('google', googleConnection, connectingGoogle)}
            {renderCalendarCard('outlook', outlookConnection, connectingOutlook)}
          </div>
        </div>

        {/* ========= SECTION: Visioconférence ========= */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Monitor className="w-4 h-4 text-slate-400" />
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider" data-testid="section-visio">Visioconférence</h2>
          </div>

          {/* Explanation */}
          <div className="flex items-start gap-2.5 p-3 bg-indigo-50/50 border border-indigo-100 rounded-lg mb-3">
            <Info className="w-4 h-4 text-indigo-500 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-indigo-700">
              Connectez un provider de visioconférence pour créer des réunions directement depuis NLYT
              et récupérer automatiquement les rapports de présence après chaque réunion.
            </p>
          </div>

          <div className="space-y-3">
            {renderVideoProviderCard('zoom')}
            {renderVideoProviderCard('teams')}
          </div>

          {/* Google Meet note — tied to Calendar */}
          <div className="mt-3 flex items-start gap-2.5 p-3 bg-emerald-50/50 border border-emerald-100 rounded-lg" data-testid="meet-calendar-note">
            <Video className="w-4 h-4 text-emerald-600 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-xs text-emerald-800 font-medium">Google Meet</p>
              <p className="text-xs text-emerald-700 mt-0.5">
                {googleConnection?.status === 'connected'
                  ? 'Activé via votre connexion Google Calendar. Les liens Google Meet sont créés automatiquement pour vos RDV visio Google.'
                  : 'Connectez Google Calendar ci-dessus pour activer la création automatique de liens Google Meet.'
                }
              </p>
              {googleConnection?.status === 'connected' && (
                <div className="flex items-center gap-1.5 mt-1">
                  <CheckCircle className="w-3 h-3 text-emerald-600" />
                  <span className="text-xs text-emerald-600 font-medium">Création de liens Meet active</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ========= Auto-Sync Section ========= */}
        {(googleConnection?.status === 'connected' || outlookConnection?.status === 'connected') && (
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden mb-8" data-testid="auto-sync-section">
            <div className="p-5">
              <div className="flex items-start gap-4">
                <div className="w-11 h-11 rounded-lg bg-violet-50 flex items-center justify-center flex-shrink-0">
                  <Zap className="w-5 h-5 text-violet-600" />
                </div>
                <div className="flex-1">
                  <h3 className="text-base font-semibold text-slate-900 mb-1">Auto-sync calendrier</h3>
                  <p className="text-sm text-slate-500">
                    Chaque nouveau rendez-vous sera automatiquement ajouté à votre calendrier (NLYT vers calendrier).
                  </p>
                </div>
              </div>
            </div>

            <div className="border-t border-slate-100 px-5 py-4 space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-2">Calendrier préféré</label>
                <div className="flex gap-2">
                  {googleConnection?.status === 'connected' && (
                    <button
                      onClick={() => !savingAutoSync && handleSaveAutoSync(true, 'google')}
                      disabled={savingAutoSync}
                      className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-xs font-medium transition-all ${
                        autoSyncEnabled && autoSyncProvider === 'google'
                          ? 'border-violet-300 bg-violet-50 text-violet-800 ring-1 ring-violet-200'
                          : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50'
                      }`}
                      data-testid="auto-sync-google-btn"
                    >
                      <Calendar className="w-3.5 h-3.5" />
                      Google Calendar
                      {autoSyncEnabled && autoSyncProvider === 'google' && <Zap className="w-3 h-3 text-violet-600" />}
                    </button>
                  )}
                  {outlookConnection?.status === 'connected' && (
                    <button
                      onClick={() => !savingAutoSync && handleSaveAutoSync(true, 'outlook')}
                      disabled={savingAutoSync}
                      className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-xs font-medium transition-all ${
                        autoSyncEnabled && autoSyncProvider === 'outlook'
                          ? 'border-violet-300 bg-violet-50 text-violet-800 ring-1 ring-violet-200'
                          : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50'
                      }`}
                      data-testid="auto-sync-outlook-btn"
                    >
                      <Calendar className="w-3.5 h-3.5" />
                      Outlook
                      {autoSyncEnabled && autoSyncProvider === 'outlook' && <Zap className="w-3 h-3 text-violet-600" />}
                    </button>
                  )}
                </div>
              </div>

              {autoSyncEnabled && (
                <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                  <div className="flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-violet-600" />
                    <span className="text-xs text-slate-600">
                      Auto-sync actif vers <strong>{autoSyncProvider === 'google' ? 'Google Calendar' : 'Outlook'}</strong>
                    </span>
                  </div>
                  <Button
                    variant="outline" size="sm"
                    onClick={() => handleSaveAutoSync(false, null)}
                    disabled={savingAutoSync}
                    className="text-slate-500 h-7 text-xs"
                    data-testid="disable-auto-sync-btn"
                  >
                    {savingAutoSync ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <ZapOff className="w-3.5 h-3.5 mr-1" />}
                    Désactiver
                  </Button>
                </div>
              )}

              {!autoSyncEnabled && (
                <p className="text-xs text-slate-400">
                  Sélectionnez un calendrier pour activer l'ajout automatique.
                </p>
              )}
            </div>
          </div>
        )}

        <div className="p-3 bg-amber-50 border border-amber-100 rounded-lg">
          <p className="text-xs text-amber-700">
            <strong>Alternative :</strong> Exportez chaque rendez-vous en fichier ICS depuis la page de détail (compatible avec tous les calendriers).
          </p>
        </div>
      </div>
    </div>
  );
}
