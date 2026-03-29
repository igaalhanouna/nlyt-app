import React, { useState, useEffect } from 'react';
import { useWorkspace } from '../../contexts/WorkspaceContext';
import { appointmentAPI } from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';
import { Loader2, Eye } from 'lucide-react';

export default function StatisticsPage() {
  const { currentWorkspace } = useWorkspace();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!currentWorkspace) return;
    const load = async () => {
      setLoading(true);
      try {
        const res = await appointmentAPI.analyticsStats(currentWorkspace.workspace_id);
        setAnalytics(res.data);
      } catch (e) {
        console.error('Analytics load error:', e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [currentWorkspace]);

  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Parametres', href: '/settings' },
        { label: 'Statistiques' },
      ]} />

      <div className="max-w-4xl mx-auto px-6 pb-16">
        <h1 className="text-2xl font-bold text-slate-900 mb-1" data-testid="statistics-page-title">Statistiques</h1>
        <p className="text-sm text-slate-500 mb-8">Vue d'ensemble de vos engagements et performances</p>

        {loading ? (
          <div className="text-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-slate-400 mx-auto" />
          </div>
        ) : analytics ? (
          <div className="space-y-5">
            <div className={`px-4 py-3 rounded-lg text-sm font-medium ${
              analytics.global_tone === 'positive' ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' :
              analytics.global_tone === 'warning' ? 'bg-amber-50 text-amber-800 border border-amber-200' :
              'bg-slate-50 text-slate-600 border border-slate-200'
            }`} data-testid="analytics-global-message">
              {analytics.global_message}
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
              <div className="bg-slate-50 rounded-lg p-4 border border-slate-100" data-testid="kpi-engagements">
                <p className="text-2xl font-bold text-slate-900">{analytics.total_engagements}</p>
                <p className="text-xs text-slate-500 mt-1">Engagements crees</p>
              </div>
              <div className="bg-slate-50 rounded-lg p-4 border border-slate-100" data-testid="kpi-presence">
                <p className="text-2xl font-bold text-slate-900">
                  {analytics.presence_rate !== null ? `${analytics.presence_rate}%` : '—'}
                </p>
                <p className="text-xs text-slate-500 mt-1">Taux de presence</p>
              </div>
              <div className="bg-slate-50 rounded-lg p-4 border border-slate-100" data-testid="kpi-acceptance">
                <p className="text-2xl font-bold text-slate-900">
                  {analytics.acceptance_rate !== null ? `${analytics.acceptance_rate}%` : '—'}
                </p>
                <p className="text-xs text-slate-500 mt-1">Taux d'acceptation</p>
              </div>
              <div className="bg-slate-50 rounded-lg p-4 border border-slate-100" data-testid="kpi-compensation">
                <p className="text-2xl font-bold text-slate-900">
                  {(analytics.personal_compensation_cents / 100).toFixed(0)} €
                </p>
                <p className="text-xs text-slate-500 mt-1">Dedommagement personnel</p>
              </div>
              <div className="bg-slate-50 rounded-lg p-4 border border-slate-100" data-testid="kpi-charity">
                <p className="text-2xl font-bold text-emerald-700">
                  {(analytics.charity_total_cents / 100).toFixed(0)} €
                </p>
                <p className="text-xs text-slate-500 mt-1">Reverses a des associations</p>
              </div>
              <div className="bg-slate-50 rounded-lg p-4 border border-slate-100" data-testid="kpi-defaults">
                <p className={`text-2xl font-bold ${analytics.organizer_defaults > 0 ? 'text-amber-600' : 'text-slate-900'}`}>
                  {analytics.organizer_defaults}
                </p>
                {analytics.organizer_penalties_cents > 0 && (
                  <p className="text-sm font-semibold text-amber-600 mt-0.5">
                    {(analytics.organizer_penalties_cents / 100).toFixed(0)} €
                  </p>
                )}
                <p className="text-xs text-slate-500 mt-1">Engagements non honores</p>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-16">
            <Eye className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500">Aucune donnee disponible</p>
          </div>
        )}
      </div>
    </div>
  );
}
