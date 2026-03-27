import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Wallet, ArrowUpRight, AlertTriangle, ChevronRight, Clock, XCircle, Scale } from 'lucide-react';
import { walletAPI } from '../../services/api';

function fmt(cents, currency = 'eur') {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency }).format(cents / 100);
}

export default function WalletWidget() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      try {
        const [walletRes, distRes] = await Promise.all([
          walletAPI.get(),
          walletAPI.getDistributions().catch(() => ({ data: { distributions: [] } })),
        ]);
        const w = walletRes.data;
        const dists = distRes.data?.distributions || [];
        const contestedCount = dists.filter(d => d.status === 'contested').length;
        const failedPayouts = 0; // TODO: fetch from payouts API if needed

        setData({
          available: w.available_balance || 0,
          pending: w.pending_balance || 0,
          currency: w.currency || 'eur',
          connectStatus: w.stripe_connect_status || 'not_started',
          contestedCount,
          failedPayouts,
          hasParticipated: true, // simplified — widget only shown if wallet exists
        });
      } catch {
        setData(null);
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, []);

  if (loading || !data) return null;

  // Determine if widget should show
  const hasBalance = data.available > 0 || data.pending > 0;
  const needsConnect = data.connectStatus !== 'active' && data.hasParticipated;
  const hasContestation = data.contestedCount > 0;
  const hasFailedPayout = data.failedPayouts > 0;
  const shouldShow = hasBalance || needsConnect || hasContestation || hasFailedPayout;

  if (!shouldShow) return null;

  // Determine alert
  let alert = null;
  if (hasFailedPayout) {
    alert = { icon: XCircle, text: 'Un retrait a echoue', color: 'text-red-600', bg: 'bg-red-50' };
  } else if (hasContestation) {
    alert = { icon: Scale, text: `${data.contestedCount} contestation${data.contestedCount > 1 ? 's' : ''} en cours`, color: 'text-orange-600', bg: 'bg-orange-50' };
  } else if (needsConnect && hasBalance) {
    alert = { icon: AlertTriangle, text: 'Liez votre compte bancaire pour retirer vos fonds', color: 'text-amber-600', bg: 'bg-amber-50' };
  }

  return (
    <Link to="/wallet" data-testid="wallet-widget">
      <div className="mb-6 bg-white border border-slate-200 rounded-xl p-4 hover:border-slate-300 transition-colors cursor-pointer group">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Wallet className="w-4.5 h-4.5 text-slate-600" />
            <h3 className="text-sm font-semibold text-slate-900">Mon wallet</h3>
          </div>
          <div className="flex items-center gap-1 text-xs text-slate-400 group-hover:text-slate-600 transition-colors">
            Voir le wallet
            <ChevronRight className="w-3.5 h-3.5" />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-2">
          <div>
            <p className="text-[10px] font-medium text-emerald-700 uppercase tracking-wider mb-0.5">Disponible</p>
            <p className="text-lg font-bold text-slate-900" data-testid="widget-available">{fmt(data.available, data.currency)}</p>
          </div>
          <div>
            <p className="text-[10px] font-medium text-blue-700 uppercase tracking-wider mb-0.5">En verification</p>
            <p className="text-lg font-bold text-slate-700" data-testid="widget-pending">{fmt(data.pending, data.currency)}</p>
          </div>
        </div>

        {alert && (
          <div className={`mt-2 flex items-center gap-2 px-3 py-2 rounded-lg ${alert.bg}`} data-testid="wallet-widget-alert">
            <alert.icon className={`w-3.5 h-3.5 ${alert.color} flex-shrink-0`} />
            <span className={`text-xs font-medium ${alert.color}`}>{alert.text}</span>
          </div>
        )}
      </div>
    </Link>
  );
}
