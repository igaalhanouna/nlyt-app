import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import { Shield, AlertTriangle, Clock, CheckCircle, XCircle, Scale, ChevronRight, Video, MapPin } from 'lucide-react';

const POSITION_LABELS = {
  confirmed_present: 'Present',
  confirmed_absent: 'Absent',
  confirmed_late_penalized: 'Retard penalise',
};

function AgeIndicator({ daysAgo, hoursAgo }) {
  if (daysAgo == null && hoursAgo == null) return null;
  const urgent = daysAgo >= 3;
  const warning = daysAgo >= 1;
  const label = daysAgo >= 1
    ? `Escalade il y a ${daysAgo}j`
    : `Escalade il y a ${hoursAgo || '<1'}h`;
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${
        urgent ? 'bg-red-100 text-red-700' : warning ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'
      }`}
      data-testid="age-indicator"
    >
      <Clock className="w-3 h-3" />
      {label}
    </span>
  );
}

export default function AdminArbitrationList() {
  const [disputes, setDisputes] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const [dRes, sRes] = await Promise.all([
          adminAPI.getEscalatedDisputes(),
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
    fetch();
  }, []);

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

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6 mb-8" data-testid="arbitration-stats">
            <StatCard label="En attente d'arbitrage" value={stats.escalated_pending} color="red" />
            <StatCard label="Positions en cours" value={stats.awaiting_positions} color="amber" />
            <StatCard label="Resolus (total)" value={stats.total_resolved} color="emerald" />
            <StatCard label="Accords mutuels" value={stats.total_agreed_by_parties} color="blue" />
          </div>
        )}

        {/* List */}
        {disputes.length === 0 ? (
          <div className="text-center py-16 bg-white border border-slate-200 rounded-xl" data-testid="no-disputes">
            <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
            <p className="text-lg font-medium text-slate-700">Aucun litige en attente</p>
            <p className="text-sm text-slate-400 mt-1">Tous les litiges escalades ont ete traites</p>
          </div>
        ) : (
          <div className="space-y-3" data-testid="dispute-list">
            {disputes.map((d) => (
              <Link
                key={d.dispute_id}
                to={`/admin/arbitration/${d.dispute_id}`}
                className="block bg-white border border-slate-200 rounded-xl p-5 hover:border-slate-400 hover:shadow-sm transition-all"
                data-testid={`dispute-card-${d.dispute_id}`}
              >
                <div className="flex items-start justify-between gap-4">
                  {/* Left: info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1.5">
                      <h3 className="text-sm font-semibold text-slate-900 truncate">{d.appointment_title || 'Rendez-vous'}</h3>
                      <AgeIndicator daysAgo={d.escalated_days_ago} hoursAgo={d.escalated_hours_ago} />
                    </div>

                    <p className="text-xs text-slate-500 mb-2 flex items-center gap-2 flex-wrap">
                      {d.appointment_type === 'video' ? (
                        <span className="inline-flex items-center gap-1"><Video className="w-3 h-3" />{d.appointment_meeting_provider || 'Visio'}</span>
                      ) : (
                        <span className="inline-flex items-center gap-1"><MapPin className="w-3 h-3" />{d.appointment_location || 'Physique'}</span>
                      )}
                      <span>{d.appointment_date ? new Date(d.appointment_date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' }) : ''}</span>
                    </p>

                    {/* Target + Proof badge */}
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

                    {/* Positions */}
                    <div className="flex items-center gap-4 text-xs">
                      <span className="text-slate-500">
                        Organisateur : <strong className="text-slate-700">{POSITION_LABELS[d.positions?.organizer] || '—'}</strong>
                      </span>
                      <span className="text-slate-400">vs</span>
                      <span className="text-slate-500">
                        Participant : <strong className="text-slate-700">{POSITION_LABELS[d.positions?.participant] || '—'}</strong>
                      </span>
                    </div>
                  </div>

                  {/* Right: CTA */}
                  <div className="flex-shrink-0 flex items-center gap-2">
                    <span className="hidden sm:inline text-xs font-medium text-slate-500">Arbitrer</span>
                    <ChevronRight className="w-5 h-5 text-slate-400" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function StatCard({ label, value, color }) {
  const colors = {
    red: 'bg-red-50 text-red-700 border-red-100',
    amber: 'bg-amber-50 text-amber-700 border-amber-100',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-100',
    blue: 'bg-blue-50 text-blue-700 border-blue-100',
  };
  return (
    <div className={`rounded-xl border p-4 ${colors[color]}`} data-testid={`stat-${color}`}>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-[11px] font-medium mt-1 opacity-80">{label}</p>
    </div>
  );
}
