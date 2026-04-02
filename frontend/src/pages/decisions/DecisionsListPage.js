import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { disputeAPI, notificationAPI } from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import {
  ArrowRight, Shield, Clock, Loader2, Flame, Scale,
  MapPin, Video, Calendar, User,
} from 'lucide-react';

const OUTCOME_CFG = {
  on_time: { label: 'Presence validee', className: 'bg-emerald-100 text-emerald-700', Icon: Shield },
  no_show: { label: 'Absence confirmee', className: 'bg-red-100 text-red-700', Icon: Flame },
  late_penalized: { label: 'Retard confirme', className: 'bg-amber-100 text-amber-700', Icon: Clock },
  waived: { label: 'Classe sans suite', className: 'bg-slate-100 text-slate-600', Icon: Shield },
};

const FI_STYLES = {
  credit: 'bg-emerald-50 text-emerald-700',
  debit: 'bg-red-50 text-red-700',
  neutral: 'bg-slate-50 text-slate-600',
};

function groupByAppointment(decisions) {
  const map = new Map();
  for (const dec of decisions) {
    const aptId = dec.appointment_id || dec.dispute_id;
    if (!map.has(aptId)) {
      map.set(aptId, {
        appointment_id: aptId,
        appointment_title: dec.appointment_title || 'Rendez-vous',
        appointment_date: dec.appointment_date || '',
        appointment_type: dec.appointment_type || '',
        appointment_location: dec.appointment_location || '',
        appointment_meeting_provider: dec.appointment_meeting_provider || '',
        decisions: [],
      });
    }
    map.get(aptId).decisions.push(dec);
  }
  return Array.from(map.values());
}

function getGlobalImpact(decisions) {
  let totalAmount = 0;
  let hasDebit = false;
  let hasCredit = false;
  for (const d of decisions) {
    const fi = d.financial_impact || {};
    if (fi.type === 'debit') { hasDebit = true; totalAmount -= (fi.amount || 0); }
    if (fi.type === 'credit') { hasCredit = true; totalAmount += (fi.amount || 0); }
  }
  if (hasDebit && !hasCredit) return { type: 'debit', label: `${Math.abs(totalAmount).toFixed(0)}EUR debite` };
  if (hasCredit && !hasDebit) return { type: 'credit', label: `+${totalAmount.toFixed(0)}EUR recu` };
  if (hasDebit && hasCredit) return { type: 'neutral', label: 'Impact mixte' };
  return { type: 'neutral', label: 'Aucune penalite' };
}

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

  const groups = decisions ? groupByAppointment(decisions) : [];

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
        ) : groups.length > 0 ? (
          <div className="space-y-4" data-testid="decisions-list">
            {groups.map((group) => (
              <AppointmentDecisionCard
                key={group.appointment_id}
                group={group}
                unreadIds={unreadIds}
              />
            ))}
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

function AppointmentDecisionCard({ group, unreadIds }) {
  const { decisions } = group;
  const hasUnread = decisions.some((d) => unreadIds.has(d.dispute_id));
  const isPhysical = group.appointment_type === 'physical';
  const locationLabel = isPhysical
    ? (group.appointment_location || 'Physique')
    : (group.appointment_meeting_provider || 'Visioconference');
  const LocationIcon = isPhysical ? MapPin : Video;
  const globalImpact = getGlobalImpact(decisions);
  const globalImpactStyle = FI_STYLES[globalImpact.type] || FI_STYLES.neutral;

  return (
    <div
      className={`rounded-xl border overflow-hidden ${hasUnread ? 'bg-blue-50/30 border-blue-200' : 'bg-white border-slate-200'}`}
      data-testid={`decision-group-${group.appointment_id}`}
    >
      {/* Header: appointment context */}
      <div className="px-5 pt-4 pb-3 border-b border-slate-100">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5">
              {hasUnread && (
                <span className="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0" data-testid={`unread-dot-group-${group.appointment_id}`} />
              )}
              <h3 className="text-sm font-semibold text-slate-900 truncate">{group.appointment_title}</h3>
              {decisions.length > 1 && (
                <span className="px-1.5 py-0.5 rounded-md bg-slate-100 text-[10px] font-bold text-slate-500">
                  {decisions.length} decisions
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-500">
              <span className="flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                {group.appointment_date
                  ? new Date(group.appointment_date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
                  : ''}
              </span>
              <span className="flex items-center gap-1">
                <LocationIcon className="w-3 h-3" />
                {locationLabel}
              </span>
            </div>
          </div>
          <span className={`text-xs font-medium px-2.5 py-1 rounded-lg whitespace-nowrap ${globalImpactStyle}`}>
            {globalImpact.label}
          </span>
        </div>
      </div>

      {/* Decision sub-cards */}
      <div className="divide-y divide-slate-50">
        {decisions.map((dec) => (
          <DecisionSubCard key={dec.dispute_id} decision={dec} isUnread={unreadIds.has(dec.dispute_id)} />
        ))}
      </div>
    </div>
  );
}

function DecisionSubCard({ decision, isUnread }) {
  const oc = OUTCOME_CFG[decision.final_outcome] || OUTCOME_CFG.no_show;
  const OIcon = oc.Icon;
  const fi = decision.financial_impact || {};
  const fiBg = FI_STYLES[fi.type] || FI_STYLES.neutral;

  return (
    <Link
      to={`/decisions/${decision.dispute_id}`}
      className="flex items-center gap-3 px-5 py-3 hover:bg-slate-50/50 transition-colors"
      data-testid={`decision-card-${decision.dispute_id}`}
    >
      <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center flex-shrink-0 relative">
        <User className="w-3.5 h-3.5 text-slate-400" />
        {isUnread && (
          <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-blue-500 border border-white" data-testid={`unread-dot-${decision.dispute_id}`} />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm text-slate-700 font-medium truncate">
            {decision.target_name || 'Participant'}
          </span>
          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold ${oc.className}`}>
            <OIcon className="w-2.5 h-2.5" /> {oc.label}
          </span>
        </div>
      </div>

      <span className={`text-[11px] font-medium px-2 py-0.5 rounded-md whitespace-nowrap ${fiBg}`} data-testid="financial-impact-badge">
        {fi.label || 'Non concerne'}
      </span>
      <ArrowRight className="w-3.5 h-3.5 text-slate-300 flex-shrink-0" />
    </Link>
  );
}
