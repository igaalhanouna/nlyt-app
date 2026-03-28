import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle, Clock, ChevronRight, Loader2, Scale, AlertTriangle } from 'lucide-react';
import api from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';

const RESOLVED_DISPLAY_STATES = ['resolved'];

export default function DisputesListPage() {
  const [disputes, setDisputes] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchDisputes = useCallback(async () => {
    try {
      const res = await api.get('/api/disputes/mine');
      setDisputes(res.data.disputes || []);
    } catch (err) {
      console.error('Error fetching disputes:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDisputes(); }, [fetchDisputes]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
      </div>
    );
  }

  const active = disputes.filter(d => d.display_state !== 'resolved');

  return (
    <div className="min-h-screen bg-slate-50" data-testid="disputes-list-page">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Litiges' },
      ]} />
      <div className="max-w-2xl mx-auto p-4 sm:p-6">

        <div className="flex items-center gap-2 mb-6">
          <Scale className="w-5 h-5 text-slate-600" />
          <h1 className="text-xl font-semibold text-slate-800">Litiges</h1>
          {active.length > 0 && (
            <span className="ml-2 px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-xs font-medium">
              {active.length} en cours
            </span>
          )}
        </div>

        {active.length === 0 ? (
          <div className="bg-white rounded-xl border p-8 text-center">
            <CheckCircle className="w-8 h-8 text-emerald-400 mx-auto mb-3" />
            <p className="text-sm text-slate-500">Aucun litige en cours</p>
          </div>
        ) : (
          <div className="space-y-3">
            {active.map(d => <DisputeCard key={d.dispute_id} dispute={d} />)}
          </div>
        )}
      </div>
    </div>
  );
}

function DisputeCard({ dispute }) {
  const displayState = dispute.display_state || 'waiting_both';
  const badgeConfig = {
    waiting_both: { label: 'En attente', color: 'bg-amber-100 text-amber-700' },
    waiting_other: { label: 'En attente', color: 'bg-amber-100 text-amber-700' },
    arbitration: { label: 'En cours d\'arbitrage', color: 'bg-blue-100 text-blue-700' },
    resolved: { label: 'Résolu', color: 'bg-emerald-100 text-emerald-700' },
  };
  const badge = badgeConfig[displayState] || badgeConfig.waiting_both;
  const deadline = dispute.deadline ? new Date(dispute.deadline) : null;
  const isResolved = displayState === 'resolved';

  // Action hint based on display_state
  let actionHint = null;
  if (!isResolved) {
    if (dispute.can_submit_position) {
      actionHint = { text: 'Votre réponse est attendue', color: 'text-amber-600', icon: AlertTriangle };
    } else if (displayState === 'arbitration') {
      actionHint = { text: 'En cours d\'arbitrage', color: 'text-blue-500', icon: Scale };
    } else if (displayState === 'waiting_other' && dispute.my_position) {
      const other = dispute.other_party_name || 'l\'autre partie';
      actionHint = { text: `En attente de ${other}`, color: 'text-slate-400', icon: Clock };
    }
  }

  return (
    <Link
      to={`/litiges/${dispute.dispute_id}`}
      className="block bg-white rounded-xl border border-slate-200 hover:border-slate-300 transition-colors p-4"
      data-testid={`dispute-card-${dispute.dispute_id}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-slate-700 truncate">
            {dispute.appointment_title || 'Rendez-vous'}
          </p>
          {dispute.appointment_date && (
            <p className="text-xs text-slate-400 mt-0.5">
              {new Date(dispute.appointment_date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
            </p>
          )}
          <p className="text-xs text-slate-500 mt-1.5">
            {dispute.is_target
              ? <span className="font-medium">Votre présence est contestée</span>
              : <>Présence contestée : <span className="font-medium">{dispute.target_name || 'Participant'}</span></>
            }
          </p>
          {actionHint && (
            <div className="flex items-center gap-1.5 mt-2">
              <actionHint.icon className={`w-3 h-3 ${actionHint.color}`} />
              <p className={`text-xs font-medium ${actionHint.color}`}>{actionHint.text}</p>
            </div>
          )}
        </div>
        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${badge.color}`}>
            {badge.label}
          </span>
          {deadline && !isResolved && displayState !== 'arbitration' && (
            <span className="flex items-center gap-1 text-xs text-slate-400">
              <Clock className="w-3 h-3" />
              {deadline.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })}
            </span>
          )}
          <ChevronRight className="w-4 h-4 text-slate-300" />
        </div>
      </div>
    </Link>
  );
}
