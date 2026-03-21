import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { calendarAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { ArrowLeft, Calendar, CheckCircle, XCircle, Loader2, ExternalLink, Unlink } from 'lucide-react';
import { toast } from 'sonner';

export default function Integrations() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [googleConnection, setGoogleConnection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  useEffect(() => {
    loadConnections();
  }, []);

  // Handle OAuth redirect result
  useEffect(() => {
    const googleResult = searchParams.get('google');
    if (googleResult === 'connected') {
      toast.success('Google Calendar connecté avec succès');
      searchParams.delete('google');
      setSearchParams(searchParams, { replace: true });
      loadConnections();
    } else if (googleResult === 'error') {
      const reason = searchParams.get('reason') || 'unknown';
      toast.error(`Échec de la connexion Google Calendar (${reason})`);
      searchParams.delete('google');
      searchParams.delete('reason');
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const loadConnections = async () => {
    try {
      const response = await calendarAPI.listConnections();
      const connections = response.data.connections || [];
      const google = connections.find(c => c.provider === 'google');
      setGoogleConnection(google || null);
    } catch (error) {
      console.error('Error loading connections:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleConnectGoogle = async () => {
    setConnecting(true);
    try {
      const response = await calendarAPI.connectGoogle();
      const authUrl = response.data.authorization_url;
      if (authUrl) {
        window.location.href = authUrl;
      }
    } catch (error) {
      const detail = error.response?.data?.detail || "Erreur lors de la connexion";
      toast.error(detail);
      setConnecting(false);
    }
  };

  const handleDisconnectGoogle = async () => {
    setDisconnecting(true);
    try {
      await calendarAPI.disconnectGoogle();
      toast.success('Google Calendar déconnecté');
      setGoogleConnection(null);
    } catch (error) {
      toast.error("Erreur lors de la déconnexion");
    } finally {
      setDisconnecting(false);
    }
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

        {/* Google Calendar */}
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="google-calendar-card">
          <div className="p-6">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0">
                <Calendar className="w-6 h-6 text-blue-600" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-lg font-semibold text-slate-900 mb-1">Google Calendar</h3>
                <p className="text-sm text-slate-600">
                  Synchronisez automatiquement vos rendez-vous NLYT avec votre agenda Google.
                </p>
              </div>
            </div>
          </div>

          {googleConnection && googleConnection.status === 'connected' ? (
            <div className="border-t border-slate-200 bg-slate-50 px-6 py-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-slate-900" data-testid="google-connected-email">
                      {googleConnection.google_email || 'Compte Google connecté'}
                    </p>
                    <p className="text-xs text-slate-500">
                      Connecté le {new Date(googleConnection.connected_at).toLocaleDateString('fr-FR')}
                      {!googleConnection.google_email && ' — Reconnectez pour afficher l\'email'}
                    </p>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDisconnectGoogle}
                  disabled={disconnecting}
                  className="text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700"
                  data-testid="disconnect-google-btn"
                >
                  {disconnecting ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-1" />
                  ) : (
                    <Unlink className="w-4 h-4 mr-1" />
                  )}
                  Déconnecter
                </Button>
              </div>
            </div>
          ) : (
            <div className="border-t border-slate-200 px-6 py-4">
              <Button
                onClick={handleConnectGoogle}
                disabled={connecting}
                className="w-full sm:w-auto"
                data-testid="connect-google-btn"
              >
                {connecting ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <ExternalLink className="w-4 h-4 mr-2" />
                )}
                Connecter Google Calendar
              </Button>
            </div>
          )}
        </div>

        {/* Outlook — coming soon */}
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden mt-4 opacity-60" data-testid="outlook-card">
          <div className="p-6">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-lg bg-sky-50 flex items-center justify-center flex-shrink-0">
                <Calendar className="w-6 h-6 text-sky-600" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="text-lg font-semibold text-slate-900">Outlook / Microsoft 365</h3>
                  <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-500 rounded-full">Bientôt</span>
                </div>
                <p className="text-sm text-slate-600">
                  Synchronisez avec votre calendrier Outlook ou Microsoft 365.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* ICS info */}
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
