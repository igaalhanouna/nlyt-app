import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import { Shield, Clock, CheckCircle, XCircle, Scale, ChevronRight, Video, MapPin } from 'lucide-react';

const POSITION_LABELS = {
  confirmed_present: 'Présent à l\'heure',
  confirmed_absent: 'Absent',
  confirmed_late_penalized: 'Retard penalise',
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

  // Initial load: stats + default filter
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

  // Filter change handler
  const handleFilterClick = useCallback(async (filterKey) => {
    if (filterKey === activeFilter) return; // Already selected
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
          <span className="text-xs text-slate-400">({disputes.length})</span>
          {filterLoading && <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-slate-400" />}
        </div>

        {/* Dispute list */}
        {disputes.length === 0 ? (
          <div className="text-center py-16 bg-white border border-slate-200 rounded-xl" data-testid="no-disputes">
            <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
            <p className="text-lg font-medium text-slate-700">{emptyMsg.title}</p>
            <p className="text-sm text-slate-400 mt-1">{emptyMsg.sub}</p>
          </div>
        ) : (
          <div className="space-y-3" data-testid="dispute-list">
            {disputes.map((d) => (
              <DisputeCard key={d.dispute_id} d={d} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function DisputeCard({ d }) {
  const statusBadge = STATUS_BADGES[d.status];

  return (
    <Link
      to={`/admin/arbitration/${d.dispute_id}`}
      className="block bg-white border border-slate-200 rounded-xl p-5 transition-all hover:border-slate-400 hover:shadow-sm cursor-pointer"
      data-testid={`dispute-card-${d.dispute_id}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            <h3 className="text-sm font-semibold text-slate-900 truncate">{d.appointment_title || 'Rendez-vous'}</h3>
            {statusBadge && (
              <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${statusBadge.cls}`} data-testid="status-badge">
                {statusBadge.label}
              </span>
            )}
            {d.status === 'escalated' && <AgeIndicator daysAgo={d.escalated_days_ago} hoursAgo={d.escalated_hours_ago} />}
          </div>

          <p className="text-xs text-slate-500 mb-2 flex items-center gap-2 flex-wrap">
            {d.appointment_type === 'video' ? (
              <span className="inline-flex items-center gap-1"><Video className="w-3 h-3" />{d.appointment_meeting_provider || 'Visio'}</span>
            ) : (
              <span className="inline-flex items-center gap-1"><MapPin className="w-3 h-3" />{d.appointment_location || 'Physique'}</span>
            )}
            <span>{d.appointment_date ? new Date(d.appointment_date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' }) : ''}</span>
          </p>

          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-medium text-slate-600">Cible : {d.target_name || 'Inconnu'}</span>
            {d.has_admissible_proof ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-700" data-testid="proof-badge-yes">
                <Shield className="w-3 h-3" /> Preuve detectee
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-red-100 text-red-700" data-testid="proof-badge-no">
                <XCircle className="w-3 h-3" /> Aucune preuve
              </span>
            )}
          </div>

          <div className="flex items-center gap-4 text-xs">
            <span className="text-slate-500">
              Organisateur : <strong className="text-slate-700">{POSITION_LABELS[d.positions?.organizer] || '—'}</strong>
            </span>
            <span className="text-slate-400">vs</span>
            <span className="text-slate-500">
              Participant : <strong className="text-slate-700">{POSITION_LABELS[d.positions?.participant] || '—'}</strong>
            </span>
          </div>

          {/* Financial summary for resolved/agreed disputes */}
          {d.financial_summary && (
            <p className={`text-xs font-medium mt-2 px-2.5 py-1 rounded-lg inline-block ${
              d.financial_summary === 'Aucune penalite'
                ? 'bg-emerald-50 text-emerald-700'
                : 'bg-red-50 text-red-700'
            }`} data-testid="financial-summary">
              {d.financial_summary}
            </p>
          )}
        </div>

        {/* Right: CTA */}
        <div className="flex-shrink-0 flex items-center gap-2">
          <span className="hidden sm:inline text-xs font-medium text-slate-500">
            {d.status === 'escalated' ? 'Arbitrer' : 'Voir la decision'}
          </span>
          <ChevronRight className="w-5 h-5 text-slate-400" />
        </div>
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
