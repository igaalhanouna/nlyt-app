import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  CheckCircle, Clock, ChevronRight, Loader2, Scale, AlertTriangle,
  MapPin, Video, Calendar, ArrowRight, User
} from 'lucide-react';
import api from '../../services/api';
import { notificationAPI } from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';
import { formatDateTimeCompactFr } from '../../utils/dateFormat';

const REASON_LABELS = {
  contestant_contradiction: 'Contestation des declarations',
  tiers_disagreement: 'Declarations contradictoires',
  coherence_failure: 'Incoherence des declarations',
  collusion_signal: 'Suspicion de conflit d\'interet',
  tech_signal_contradiction: 'Signal technique contradictoire',
  no_declarations_received: 'Aucune declaration recue',
  small_group_disagreement: 'Declarations contradictoires',
};

function getGlobalStatus(disputes) {
  const hasActionNeeded = disputes.some(d => d.can_submit_position);
  if (hasActionNeeded) return { key: 'action', label: 'Votre reponse attendue', color: 'bg-amber-100 text-amber-700', icon: AlertTriangle };
  const hasArbitration = disputes.some(d => d.display_state === 'arbitration');
  if (hasArbitration) return { key: 'arbitration', label: 'En cours d\'arbitrage', color: 'bg-blue-100 text-blue-700', icon: Scale };
  return { key: 'waiting', label: 'En attente', color: 'bg-slate-100 text-slate-600', icon: Clock };
}

function groupByAppointment(disputes) {
  const groups = {};
  for (const d of disputes) {
    const aptId = d.appointment_id;
    if (!groups[aptId]) {
      groups[aptId] = {
        appointment_id: aptId,
        appointment_title: d.appointment_title || 'Rendez-vous',
        appointment_date: d.appointment_date,
        appointment_type: d.appointment_type,
        appointment_location: d.appointment_location,
        appointment_meeting_provider: d.appointment_meeting_provider,
        appointment_duration_minutes: d.appointment_duration_minutes,
        disputes: [],
      };
    }
    groups[aptId].disputes.push(d);
  }
  return Object.values(groups).sort((a, b) => (b.appointment_date || '').localeCompare(a.appointment_date || ''));
}

export default function DisputesListPage() {
  const [disputes, setDisputes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [unreadIds, setUnreadIds] = useState(new Set());

  const fetchDisputes = useCallback(async () => {
    try {
      const [res, unreadRes] = await Promise.all([
        api.get('/api/disputes/mine'),
        notificationAPI.getUnreadIds('dispute_update'),
      ]);
      setDisputes(res.data.disputes || []);
      setUnreadIds(new Set(unreadRes.data.unread_ids || []));
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
  const groups = groupByAppointment(active);

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
            <span className="ml-2 px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-xs font-medium" data-testid="active-disputes-count">
              {active.length} en cours
            </span>
          )}
        </div>

        {groups.length === 0 ? (
          <div className="bg-white rounded-xl border p-8 text-center" data-testid="no-disputes-message">
            <CheckCircle className="w-8 h-8 text-emerald-400 mx-auto mb-3" />
            <p className="text-sm text-slate-500">Aucun litige en cours</p>
          </div>
        ) : (
          <div className="space-y-4">
            {groups.map(group => (
              <AppointmentDisputeCard key={group.appointment_id} group={group} unreadIds={unreadIds} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AppointmentDisputeCard({ group, unreadIds }) {
  const { disputes } = group;
  const globalStatus = getGlobalStatus(disputes);
  const GlobalIcon = globalStatus.icon;
  const isPhysical = group.appointment_type === 'physical';
  const locationLabel = isPhysical
    ? (group.appointment_location || 'Physique')
    : (group.appointment_meeting_provider || 'Visioconference');
  const hasUnread = disputes.some(d => unreadIds.has(d.dispute_id));

  return (
    <div
      className={`rounded-xl border overflow-hidden ${hasUnread ? 'bg-blue-50/30 border-blue-200' : 'bg-white border-slate-200'}`}
      data-testid={`dispute-group-${group.appointment_id}`}
    >
      {/* ── Header: RDV context ── */}
      <div className="px-4 pt-4 pb-3 border-b border-slate-100">
        <div className="flex items-start justify-between gap-3 mb-2">
          <h3 className="text-sm font-semibold text-slate-800 leading-tight" data-testid={`group-title-${group.appointment_id}`}>
            {group.appointment_title}
          </h3>
          <div className="flex items-center gap-2 flex-shrink-0">
            {disputes.length > 1 && (
              <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 text-[11px] font-medium" data-testid={`group-count-${group.appointment_id}`}>
                {disputes.length} litiges
              </span>
            )}
            <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${globalStatus.color}`} data-testid={`group-status-${group.appointment_id}`}>
              <GlobalIcon className="w-3 h-3" />
              {globalStatus.label}
            </span>
          </div>
        </div>

        {/* Metadata row */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
          {group.appointment_date && (
            <span className="flex items-center gap-1">
              <Calendar className="w-3 h-3 text-slate-400" />
              {formatDateTimeCompactFr(group.appointment_date)}
            </span>
          )}
          {group.appointment_duration_minutes > 0 && (
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3 text-slate-400" />
              {group.appointment_duration_minutes} min
            </span>
          )}
          <span className="flex items-center gap-1">
            {isPhysical
              ? <><MapPin className="w-3 h-3 text-slate-400" /> <span className="truncate max-w-[180px]">{locationLabel}</span></>
              : <><Video className="w-3 h-3 text-slate-400" /> {locationLabel}</>
            }
          </span>
        </div>
      </div>

      {/* ── Sub-cards: individual disputes ── */}
      <div className="divide-y divide-slate-50">
        {disputes.map(d => (
          <DisputeSubCard key={d.dispute_id} dispute={d} isUnread={unreadIds.has(d.dispute_id)} />
        ))}
      </div>

      {/* ── Footer: link to appointment ── */}
      <div className="px-4 py-2.5 bg-slate-50/60 border-t border-slate-100">
        <Link
          to={`/appointments/${group.appointment_id}`}
          className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800 font-medium transition-colors"
          data-testid={`view-appointment-${group.appointment_id}`}
        >
          Voir le rendez-vous
          <ArrowRight className="w-3 h-3" />
        </Link>
      </div>
    </div>
  );
}

function DisputeSubCard({ dispute, isUnread }) {
  const displayState = dispute.display_state || 'waiting_both';
  const badgeConfig = {
    waiting_both: { label: 'En attente', color: 'bg-amber-50 text-amber-600 border-amber-200' },
    waiting_other: { label: 'En attente', color: 'bg-amber-50 text-amber-600 border-amber-200' },
    arbitration: { label: 'Arbitrage', color: 'bg-blue-50 text-blue-600 border-blue-200' },
    resolved: { label: 'Resolu', color: 'bg-emerald-50 text-emerald-600 border-emerald-200' },
  };
  const badge = badgeConfig[displayState] || badgeConfig.waiting_both;

  let actionHint = null;
  if (dispute.can_submit_position) {
    actionHint = { text: 'Votre reponse est attendue', color: 'text-amber-600', icon: AlertTriangle };
  } else if (displayState === 'arbitration') {
    actionHint = { text: 'Positions divergentes — arbitre saisi', color: 'text-blue-500', icon: Scale };
  } else if (displayState === 'waiting_other' && dispute.my_position) {
    const other = dispute.other_party_name || 'l\'autre partie';
    actionHint = { text: `En attente de ${other}`, color: 'text-slate-400', icon: Clock };
  }

  const reason = dispute.opened_reason ? (REASON_LABELS[dispute.opened_reason] || null) : null;

  return (
    <Link
      to={`/litiges/${dispute.dispute_id}`}
      className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50/80 transition-colors group"
      data-testid={`dispute-sub-card-${dispute.dispute_id}`}
    >
      <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center flex-shrink-0 relative">
        <User className="w-3.5 h-3.5 text-slate-400" />
        {isUnread && (
          <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-blue-500 border border-white" data-testid={`unread-dot-${dispute.dispute_id}`} />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-700 font-medium truncate">
          {dispute.is_target
            ? 'Votre presence est contestee'
            : <>Presence contestee : <span className="font-semibold">{dispute.target_name || 'Participant'}</span></>
          }
        </p>
        {reason && (
          <p className="text-[11px] text-slate-400 mt-0.5 truncate">{reason}</p>
        )}
        {actionHint && (
          <div className="flex items-center gap-1 mt-1">
            <actionHint.icon className={`w-3 h-3 ${actionHint.color}`} />
            <p className={`text-xs font-medium ${actionHint.color}`}>{actionHint.text}</p>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium border ${badge.color}`}>
          {badge.label}
        </span>
        <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-500 transition-colors" />
      </div>
    </Link>
  );
}
