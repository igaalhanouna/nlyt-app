import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import { Shield, Clock, CheckCircle, XCircle, Scale, ChevronRight, Video, MapPin, Calendar, User } from 'lucide-react';

const POSITION_LABELS = {
  confirmed_present: 'present',
  confirmed_absent: 'absent',
  confirmed_late_penalized: 'en retard',
};

const STATUS_BADGES = {
  escalated: { label: 'Escalade', cls: 'bg-red-100 text-red-700' },
  awaiting_positions: { label: 'Positions en cours', cls: 'bg-amber-100 text-amber-700' },
  resolved: { label: 'Resolu', cls: 'bg-emerald-100 text-emerald-700' },
  agreed_present: { label: 'Accord: Present', cls: 'bg-blue-100 text-blue-700' },
  agreed_absent: { label: 'Accord: Absent', cls: 'bg-blue-100 text-blue-700' },
  agreed_late_penalized: { label: 'Accord: Retard', cls: 'bg-blue-100 text-blue-700' },
};

const FILTERS = [
  { key: 'escalated', label: 'En attente d\'arbitrage', statKey: 'escalated_pending', color: 'red' },
  { key: 'awaiting', label: 'Positions en cours', statKey: 'awaiting_positions', color: 'amber' },
  { key: 'resolved', label: 'Resolus (total)', statKey: 'total_resolved', color: 'emerald' },
  { key: 'agreed', label: 'Accords mutuels', statKey: 'total_agreed_by_parties', color: 'blue' },
];

const EMPTY_MESSAGES = {
  escalated: { title: 'Aucun litige en attente', sub: 'Tous les litiges escalades ont ete traites' },
  awaiting: { title: 'Aucun litige en attente de positions', sub: 'Toutes les parties ont soumis leurs positions' },
  resolved: { title: 'Aucun litige resolu', sub: 'Les litiges resolus apparaitront ici' },
  agreed: { title: 'Aucun accord mutuel', sub: 'Les accords entre parties apparaitront ici' },
};

function groupByAppointment(disputes) {
  const map = new Map();
  for (const d of disputes) {
    const aptId = d.appointment_id;
    if (!map.has(aptId)) {
      map.set(aptId, {
        appointment_id: aptId,
        appointment_title: d.appointment_title || 'Rendez-vous',
        appointment_date: d.appointment_date || '',
        appointment_type: d.appointment_type || '',
        appointment_location: d.appointment_location || '',
        appointment_meeting_provider: d.appointment_meeting_provider || '',
        disputes: [],
      });
    }
    map.get(aptId).disputes.push(d);
  }
  return Array.from(map.values());
}

function AgeIndicator({ daysAgo, hoursAgo }) {
  if (daysAgo == null && hoursAgo == null) return null;
  const urgent = daysAgo >= 3;
  const warning = daysAgo >= 1;
  const label = daysAgo >= 1
    ? `Il y a ${daysAgo}j`
    : `Il y a ${hoursAgo || '<1'}h`;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${
      urgent ? 'bg-red-100 text-red-700' : warning ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'
    }`} data-testid="age-indicator">
      <Clock className="w-3 h-3" />
      {label}
    </span>
  );
}

export default function AdminArbitrationList() {
  const [disputes, setDisputes] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState('escalated');
  const [filterLoading, setFilterLoading] = useState(false);

  useEffect(() => {
    const init = async () => {
      try {
        const [dRes, sRes] = await Promise.all([
          adminAPI.getEscalatedDisputes('escalated'),
          adminAPI.getArbitrationStats(),
        ]);
        setDisputes(dRes.data.disputes || []);
        setStats(sRes.data);
      } catch (e) {
        console.error('Admin fetch error:', e);
      } finally {
        setLoading(false);
      }
    };
    init();
  }, []);

  const handleFilterClick = useCallback(async (filterKey) => {
    if (filterKey === activeFilter) return;
    setActiveFilter(filterKey);
    setFilterLoading(true);
    try {
      const res = await adminAPI.getEscalatedDisputes(filterKey);
      setDisputes(res.data.disputes || []);
    } catch (e) {
      console.error('Filter error:', e);
    } finally {
      setFilterLoading(false);
    }
  }, [activeFilter]);

  if (loading) {
    return (
      <>
        <AppNavbar />
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-slate-900" />
        </div>
      </>
    );
  }

  const groups = groupByAppointment(disputes);
  const emptyMsg = EMPTY_MESSAGES[activeFilter] || EMPTY_MESSAGES.escalated;

  return (
    <>
      <AppNavbar />
      <div className="max-w-5xl mx-auto px-4 py-8" data-testid="admin-arbitration-page">
        {/* Header */}
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-lg bg-slate-900 flex items-center justify-center">
            <Scale className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Arbitrage des litiges</h1>
            <p className="text-sm text-slate-500">Trancher dans le cadre des regles systeme</p>
          </div>
        </div>

        {/* Clickable KPI Stats */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6 mb-8" data-testid="arbitration-stats">
            {FILTERS.map((f) => (
              <StatCard
                key={f.key}
                label={f.label}
                value={stats[f.statKey] ?? 0}
                color={f.color}
                active={activeFilter === f.key}
                onClick={() => handleFilterClick(f.key)}
                filterKey={f.key}
              />
            ))}
          </div>
        )}

        {/* Active filter label */}
        <div className="flex items-center gap-2 mb-4">
          <p className="text-sm font-medium text-slate-700">
            {FILTERS.find(f => f.key === activeFilter)?.label}
          </p>
          <span className="text-xs text-slate-400">
            ({groups.length} RDV{groups.length > 1 ? 's' : ''}, {disputes.length} litige{disputes.length > 1 ? 's' : ''})
          </span>
          {filterLoading && <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-slate-400" />}
        </div>

        {/* Grouped dispute list */}
        {groups.length === 0 ? (
          <div className="text-center py-16 bg-white border border-slate-200 rounded-xl" data-testid="no-disputes">
            <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
            <p className="text-lg font-medium text-slate-700">{emptyMsg.title}</p>
            <p className="text-sm text-slate-400 mt-1">{emptyMsg.sub}</p>
          </div>
        ) : (
          <div className="space-y-4" data-testid="dispute-list">
            {groups.map((group) => (
              <AppointmentArbitrationCard key={group.appointment_id} group={group} activeFilter={activeFilter} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function AppointmentArbitrationCard({ group, activeFilter }) {
  const { disputes } = group;
  const isPhysical = group.appointment_type === 'physical';
  const locationLabel = isPhysical
    ? (group.appointment_location || 'Physique')
    : (group.appointment_meeting_provider || 'Visioconference');
  const LocationIcon = isPhysical ? MapPin : Video;

  return (
    <div
      className="rounded-xl border border-slate-200 bg-white overflow-hidden"
      data-testid={`arbitration-group-${group.appointment_id}`}
    >
      {/* Header: appointment context */}
      <div className="px-5 pt-4 pb-3 border-b border-slate-100">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5">
              <h3 className="text-sm font-semibold text-slate-900 truncate">{group.appointment_title}</h3>
              {disputes.length > 1 && (
                <span className="px-1.5 py-0.5 rounded-md bg-slate-100 text-[10px] font-bold text-slate-500">
                  {disputes.length} litiges
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
        </div>
      </div>

      {/* Dispute sub-rows */}
      <div className="divide-y divide-slate-50">
        {disputes.map((d) => (
          <DisputeSubRow key={d.dispute_id} d={d} activeFilter={activeFilter} />
        ))}
      </div>
    </div>
  );
}

function DisputeSubRow({ d, activeFilter }) {
  const statusBadge = STATUS_BADGES[d.status];

  return (
    <Link
      to={`/admin/arbitration/${d.dispute_id}`}
      className="flex items-center gap-3 px-5 py-3.5 hover:bg-slate-50/50 transition-colors"
      data-testid={`dispute-card-${d.dispute_id}`}
    >
      {/* Avatar placeholder */}
      <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center flex-shrink-0">
        <User className="w-4 h-4 text-slate-400" />
      </div>

      {/* Main content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <span className="text-sm font-medium text-slate-700 truncate">
            Cible : {d.target_name || 'Inconnu'}
          </span>
          {statusBadge && (
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${statusBadge.cls}`} data-testid="status-badge">
              {statusBadge.label}
            </span>
          )}
          {d.status === 'escalated' && <AgeIndicator daysAgo={d.escalated_days_ago} hoursAgo={d.escalated_hours_ago} />}
          {d.has_admissible_proof ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-700" data-testid="proof-badge-yes">
              <Shield className="w-2.5 h-2.5" /> Preuve
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-100 text-red-700" data-testid="proof-badge-no">
              <XCircle className="w-2.5 h-2.5" /> Sans preuve
            </span>
          )}
        </div>

        {/* Positions — full phrases */}
        <div className="flex items-center gap-1 text-xs flex-wrap">
          {d.positions?.organizer ? (
            <span className="text-slate-600">
              {d.organizer_name || 'L\'organisateur'} <span className="text-slate-400">(org.)</span> maintient {d.target_name || 'la cible'} <strong className={d.positions.organizer === 'confirmed_absent' ? 'text-red-600' : d.positions.organizer === 'confirmed_present' ? 'text-emerald-600' : 'text-amber-600'}>{POSITION_LABELS[d.positions.organizer] || '?'}</strong>
            </span>
          ) : (
            <span className="text-slate-400">Org. : position non soumise</span>
          )}
          <span className="text-slate-200 mx-1">|</span>
          {d.positions?.participant ? (
            <span className="text-slate-600">
              {d.target_name || 'La cible'} se maintient <strong className={d.positions.participant === 'confirmed_absent' ? 'text-red-600' : d.positions.participant === 'confirmed_present' ? 'text-emerald-600' : 'text-amber-600'}>{POSITION_LABELS[d.positions.participant] || '?'}</strong>
            </span>
          ) : (
            <span className="text-slate-400">Cible : position non soumise</span>
          )}
        </div>

        {/* Financial summary for resolved/agreed */}
        {d.financial_summary && (
          <p className={`text-[11px] font-medium mt-1.5 px-2 py-0.5 rounded-lg inline-block ${
            d.financial_summary === 'Aucune penalite'
              ? 'bg-emerald-50 text-emerald-700'
              : 'bg-red-50 text-red-700'
          }`} data-testid="financial-summary">
            {d.financial_summary}
          </p>
        )}
      </div>

      {/* CTA */}
      <div className="flex-shrink-0 flex items-center gap-1">
        <span className="hidden sm:inline text-xs font-medium text-slate-500">
          {d.status === 'escalated' ? 'Arbitrer' : 'Voir'}
        </span>
        <ChevronRight className="w-4 h-4 text-slate-400" />
      </div>
    </Link>
  );
}

function StatCard({ label, value, color, active, onClick, filterKey }) {
  const baseColors = {
    red: 'bg-red-50 text-red-700 border-red-100',
    amber: 'bg-amber-50 text-amber-700 border-amber-100',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-100',
    blue: 'bg-blue-50 text-blue-700 border-blue-100',
  };
  const activeRings = {
    red: 'ring-2 ring-red-400 border-red-300',
    amber: 'ring-2 ring-amber-400 border-amber-300',
    emerald: 'ring-2 ring-emerald-400 border-emerald-300',
    blue: 'ring-2 ring-blue-400 border-blue-300',
  };

  return (
    <button
      onClick={onClick}
      className={`rounded-xl border p-4 text-left cursor-pointer transition-all hover:shadow-sm ${baseColors[color]} ${active ? activeRings[color] : 'hover:opacity-90'}`}
      data-testid={`stat-${filterKey}`}
    >
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-[11px] font-medium mt-1 opacity-80">{label}</p>
    </button>
  );
}
