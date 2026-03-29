import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { disputeAPI, notificationAPI } from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import {
  ArrowRight, Shield, Clock, Loader2, Flame, Scale,
} from 'lucide-react';

const OUTCOME_CFG = {
  on_time: { label: 'Presence validee', className: 'bg-emerald-100 text-emerald-700', Icon: Shield },
  no_show: { label: 'Absence confirmee', className: 'bg-red-100 text-red-700', Icon: Flame },
  late_penalized: { label: 'Retard confirme', className: 'bg-amber-100 text-amber-700', Icon: Clock },
};

const FI_STYLES = {
  credit: 'bg-emerald-50 text-emerald-700',
  debit: 'bg-red-50 text-red-700',
  neutral: 'bg-slate-50 text-slate-600',
};

export default function DecisionsListPage() {
  const [decisions, setDecisions] = useState(null);
  const [loading, setLoading] = useState(true);
  const [unreadIds, setUnreadIds] = useState(new Set());

  useEffect(() => {
    const load = async () => {
      try {
        const [decRes, unreadRes] = await Promise.all([
          disputeAPI.getMyDecisions(),
          notificationAPI.getUnreadIds('decision'),
        ]);
        setDecisions(decRes.data.decisions || []);
        setUnreadIds(new Set(unreadRes.data.unread_ids || []));
      } catch (e) {
        console.error(e);
        setDecisions([]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <div className="max-w-4xl mx-auto px-4 md:px-6 py-6 md:py-8">
        <h1 className="text-xl font-bold text-slate-900 mb-1" data-testid="decisions-page-title">Decisions</h1>
        <p className="text-sm text-slate-500 mb-6">Historique des litiges resolus et leur impact financier</p>

        {loading ? (
          <div className="text-center py-16">
            <Loader2 className="w-8 h-8 text-slate-400 mx-auto mb-3 animate-spin" />
            <p className="text-slate-500">Chargement des decisions...</p>
          </div>
        ) : decisions && decisions.length > 0 ? (
          <div className="space-y-3" data-testid="decisions-list">
            {decisions.map((dec) => {
              const oc = OUTCOME_CFG[dec.final_outcome] || OUTCOME_CFG.no_show;
              const OIcon = oc.Icon;
              const fi = dec.financial_impact || {};
              const fiBg = FI_STYLES[fi.type] || FI_STYLES.neutral;
              const isUnread = unreadIds.has(dec.dispute_id);
              return (
                <Link
                  key={dec.dispute_id}
                  to={`/decisions/${dec.dispute_id}`}
                  className={`block border rounded-xl p-5 hover:border-slate-400 hover:shadow-sm transition-all ${isUnread ? 'bg-blue-50/40 border-blue-200' : 'bg-white border-slate-200'}`}
                  data-testid={`decision-card-${dec.dispute_id}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1.5">
                        {isUnread && (
                          <span className="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0" data-testid={`unread-dot-${dec.dispute_id}`} />
                        )}
                        <h3 className="text-sm font-semibold text-slate-900 truncate">{dec.appointment_title || 'Rendez-vous'}</h3>
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ${oc.className}`}>
                          <OIcon className="w-3 h-3" /> {oc.label}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mb-2">
                        {dec.appointment_date ? new Date(dec.appointment_date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' }) : ''}
                        {dec.target_name && <> — Concerne : <strong className="text-slate-700">{dec.target_name}</strong></>}
                      </p>
                      <p className={`text-xs font-medium px-2.5 py-1 rounded-lg inline-block ${fiBg}`} data-testid="financial-impact-badge">
                        {fi.label || 'Non concerne'}
                      </p>
                    </div>
                    <div className="flex-shrink-0 flex items-center gap-2">
                      <span className="hidden sm:inline text-xs font-medium text-slate-500">Voir le detail</span>
                      <ArrowRight className="w-4 h-4 text-slate-400" />
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-16" data-testid="no-decisions">
            <Scale className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500">Aucune decision rendue</p>
            <p className="text-sm text-slate-400 mt-1">Les decisions finales de vos litiges apparaitront ici</p>
          </div>
        )}
      </div>
    </div>
  );
}
