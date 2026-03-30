import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';
import { AlertTriangle, ExternalLink, RefreshCw, Clock, Wallet } from 'lucide-react';
import { Button } from '../../components/ui/button';
import api from '../../services/api';

function formatCents(cents, currency = 'eur') {
  return (cents / 100).toFixed(2).replace('.', ',') + ' ' + currency.toUpperCase();
}

function timeAgo(isoDate) {
  if (!isoDate) return '—';
  const diff = Date.now() - new Date(isoDate).getTime();
  const hours = Math.floor(diff / 3600000);
  if (hours < 1) return 'moins d\'1h';
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}j ${hours % 24}h`;
}

export default function AdminStalePayouts() {
  const [payouts, setPayouts] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/api/admin/stale-payouts');
      setPayouts(data.stale_payouts || []);
    } catch {
      setPayouts([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Administration', href: '/admin' },
        { label: 'Payouts bloqués' },
      ]} />

      <div className="max-w-5xl mx-auto px-6 pb-16">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900" data-testid="stale-payouts-title">Payouts bloqués</h1>
            <p className="text-sm text-slate-500 mt-1">Payouts en processing depuis plus de 24h — nécessitent une vérification manuelle dans Stripe</p>
          </div>
          <Button variant="outline" size="sm" onClick={load} disabled={loading} data-testid="refresh-stale-payouts">
            <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Actualiser
          </Button>
        </div>

        {loading ? (
          <div className="text-center py-16 text-slate-400">Chargement...</div>
        ) : payouts.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-xl border border-slate-200" data-testid="no-stale-payouts">
            <Wallet className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
            <p className="font-medium text-slate-700">Aucun payout bloqué</p>
            <p className="text-sm text-slate-400 mt-1">Tous les payouts se sont terminés normalement.</p>
          </div>
        ) : (
          <div className="space-y-3" data-testid="stale-payouts-list">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2 mb-4">
              <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
              <p className="text-sm text-amber-800">
                <strong>{payouts.length} payout{payouts.length > 1 ? 's' : ''}</strong> en attente depuis plus de 24h.
                Vérifiez dans le <a href="https://dashboard.stripe.com/test/balance/overview" target="_blank" rel="noopener noreferrer" className="underline font-medium">Dashboard Stripe</a> si le transfert a bien été traité.
              </p>
            </div>

            {payouts.map((p) => (
              <div
                key={p.payout_id}
                className="bg-white border border-slate-200 rounded-xl p-4 flex flex-col md:flex-row md:items-center gap-3"
                data-testid={`stale-payout-${p.payout_id}`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700">
                      <Clock className="w-3 h-3" /> STALE
                    </span>
                    <span className="text-sm font-bold text-slate-900">{formatCents(p.amount_cents, p.currency)}</span>
                  </div>
                  <p className="text-sm text-slate-600 truncate" data-testid={`stale-user-${p.payout_id}`}>{p.user_email || p.user_id}</p>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5 text-xs text-slate-400">
                    <span>Créé : {new Date(p.requested_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                    <span>Bloqué depuis : {timeAgo(p.stale_detected_at || p.updated_at)}</span>
                    {p.stripe_transfer_id && <span className="font-mono text-slate-500">{p.stripe_transfer_id}</span>}
                  </div>
                </div>
                {p.stripe_transfer_id && (
                  <a
                    href={`https://dashboard.stripe.com/test/connect/transfers/${p.stripe_transfer_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0"
                    data-testid={`stripe-link-${p.payout_id}`}
                  >
                    <Button variant="outline" size="sm" className="text-xs">
                      <ExternalLink className="w-3.5 h-3.5 mr-1.5" /> Voir dans Stripe
                    </Button>
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
