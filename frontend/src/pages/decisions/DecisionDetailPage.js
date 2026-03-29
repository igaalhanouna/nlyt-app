import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { disputeAPI, notificationAPI } from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import { formatDateTimeFr } from '../../utils/dateFormat';
import {
  ArrowLeft, CheckCircle, UserX, Timer, Clock, Video, MapPin,
  Shield, XCircle, UserCheck, Eye,
} from 'lucide-react';

const OUTCOME_CFG = {
  on_time: { label: (name) => `Presence validee de ${name}`, sub: 'Aucune penalite', Icon: CheckCircle, color: 'emerald' },
  no_show: { label: (name) => `Absence confirmee de ${name}`, sub: (name) => `Penalite appliquee a ${name}`, Icon: UserX, color: 'red' },
  late_penalized: { label: (name) => `Retard confirme de ${name}`, sub: (name) => `Penalite partielle appliquee a ${name}`, Icon: Timer, color: 'amber' },
};

const STATUS_LABELS = {
  resolved: 'Arbitre par la plateforme',
  agreed_present: 'Accord mutuel — Present',
  agreed_absent: 'Accord mutuel — Absent',
  agreed_late_penalized: 'Accord mutuel — Retard',
};

const BORDER = { emerald: 'border-emerald-300', red: 'border-red-300', amber: 'border-amber-300' };
const BG = { emerald: 'bg-emerald-50', red: 'bg-red-50', amber: 'bg-amber-50' };
const TEXT = { emerald: 'text-emerald-800', red: 'text-red-800', amber: 'text-amber-800' };

export default function DecisionDetailPage() {
  const { disputeId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await disputeAPI.get(disputeId);
        setData(res.data);
        // Mark decision notification as read
        notificationAPI.markRead('decision', disputeId).catch(() => {});
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [disputeId]);

  if (loading) {
    return (<><AppNavbar /><div className="flex items-center justify-center min-h-[60vh]"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-slate-900" /></div></>);
  }
  if (!data) {
    return (<><AppNavbar /><div className="max-w-3xl mx-auto px-4 py-8 text-center text-slate-500">Decision introuvable</div></>);
  }

  const resolution = data.resolution || {};
  const outcome = resolution.final_outcome || '';
  const cfg = OUTCOME_CFG[outcome] || OUTCOME_CFG.no_show;
  const Icon = cfg.Icon;
  const targetName = data.target_name || 'le participant';
  const outcomeLabel = typeof cfg.label === 'function' ? cfg.label(targetName) : cfg.label;
  const outcomeSub = typeof cfg.sub === 'function' ? cfg.sub(targetName) : cfg.sub;
  const fc = data.financial_context || {};
  const ds = data.declaration_summary || {};

  return (
    <>
      <AppNavbar />
      <div className="max-w-3xl mx-auto px-4 py-8" data-testid="decision-detail-page">
        <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-5" data-testid="back-btn">
          <ArrowLeft className="w-4 h-4" /> Retour
        </button>

        {/* A. Appointment context */}
        <div className="mb-6">
          <h1 className="text-lg font-bold text-slate-900">{data.appointment_title || 'Rendez-vous'}</h1>
          <p className="text-sm text-slate-500 flex items-center gap-2 mt-1">
            {data.appointment_type === 'video' ? (
              <span className="inline-flex items-center gap-1"><Video className="w-3.5 h-3.5" />{data.appointment_meeting_provider || 'Visio'}</span>
            ) : (
              <span className="inline-flex items-center gap-1"><MapPin className="w-3.5 h-3.5" />{data.appointment_location || 'Physique'}</span>
            )}
            <span>{data.appointment_date ? formatDateTimeFr(data.appointment_date) : ''}</span>
          </p>
          <p className="text-xs text-slate-400 mt-1">
            Participant concerne : <strong className="text-slate-600">{data.target_name}</strong>
          </p>
        </div>

        {/* C. Decision finale */}
        <section className={`rounded-xl border-2 ${BORDER[cfg.color]} ${BG[cfg.color]} p-5 mb-5`} data-testid="decision-outcome-bloc">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Decision finale</span>
          <span className="text-[11px] text-slate-400 ml-2">
            {STATUS_LABELS[data.status] || ''}
            {resolution.resolved_at && <> — {new Date(resolution.resolved_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}</>}
          </span>

          <div className="flex items-center gap-3 mt-3 mb-3">
            <div className={`w-11 h-11 rounded-xl ${BG[cfg.color]} border ${BORDER[cfg.color]} flex items-center justify-center`}>
              <Icon className={`w-6 h-6 ${TEXT[cfg.color]}`} />
            </div>
            <div>
              <p className={`text-lg font-bold ${TEXT[cfg.color]}`}>{outcomeLabel}</p>
              <p className="text-sm text-slate-500">{outcomeSub}</p>
            </div>
          </div>

          {resolution.resolution_note && (
            <div className="bg-white/60 rounded-lg border border-white/80 px-4 py-3">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-1">Justification</p>
              <p className="text-sm text-slate-700">{resolution.resolution_note}</p>
            </div>
          )}
        </section>

        {/* D. Financial breakdown */}
        {fc.penalty_amount != null && (
          <section className="rounded-xl border border-slate-200 bg-white p-5 mb-5" data-testid="decision-financial-bloc">
            <h3 className="text-sm font-bold text-slate-700 mb-3">Detail financier</h3>
            {outcome === 'on_time' ? (
              <p className="text-sm text-emerald-700">Aucun prelevement. La garantie a ete liberee.</p>
            ) : fc.penalty_amount > 0 ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-600">Montant preleve</span>
                  <span className="font-bold text-red-700">{fc.penalty_amount.toFixed(0)} {(fc.penalty_currency || 'eur').toUpperCase()}</span>
                </div>
                {fc.compensation_amount > 0 && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-600">Verse a l'organisateur</span>
                    <span className="font-medium text-slate-800">{fc.compensation_amount.toFixed(0)} {(fc.penalty_currency || 'eur').toUpperCase()}</span>
                  </div>
                )}
                {fc.platform_amount > 0 && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-600">Commission plateforme ({fc.platform_commission_percent}%)</span>
                    <span className="font-medium text-slate-500">{fc.platform_amount.toFixed(0)} {(fc.penalty_currency || 'eur').toUpperCase()}</span>
                  </div>
                )}
                {fc.charity_amount > 0 && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-600">Reversement association ({fc.charity_percent}%)</span>
                    <span className="font-medium text-slate-500">{fc.charity_amount.toFixed(0)} {(fc.penalty_currency || 'eur').toUpperCase()}</span>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-slate-500">Aucune garantie financiere configuree.</p>
            )}
          </section>
        )}

        {/* B. Dispute summary — What was declared */}
        <section className="rounded-xl border border-slate-200 bg-white p-5 mb-5" data-testid="decision-declarations-bloc">
          <h3 className="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
            <Eye className="w-4 h-4" /> Ce qui a ete declare
          </h3>
          <div className="flex items-center gap-4 text-sm mb-3">
            <span className="text-emerald-700 font-medium">{ds.declared_present_count || 0} present</span>
            <span className="text-red-700 font-medium">{ds.declared_absent_count || 0} absent</span>
          </div>
          {(ds.declarants || []).length > 0 ? (
            <div className="space-y-1.5">
              {ds.declarants.map((dec, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  {dec.declared_status === 'absent' ? (
                    <UserX className="w-3.5 h-3.5 text-red-500" />
                  ) : (
                    <UserCheck className="w-3.5 h-3.5 text-emerald-500" />
                  )}
                  <span className="text-slate-600">{dec.first_name || 'Participant'}</span>
                  <span className={`text-xs font-medium ${dec.declared_status === 'absent' ? 'text-red-600' : 'text-emerald-600'}`}>
                    {dec.declared_status === 'absent' ? 'Absent' : 'Present'}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400">Aucune declaration de tiers</p>
          )}
        </section>

        {/* Proof summary (light) */}
        {data.evidence_submissions_count > 0 && (
          <section className="rounded-xl border border-slate-200 bg-white p-5 mb-5" data-testid="decision-evidence-bloc">
            <h3 className="text-sm font-bold text-slate-700 mb-2 flex items-center gap-2">
              <Shield className="w-4 h-4" /> Preuves utilisees
            </h3>
            <p className="text-sm text-slate-500">{data.evidence_submissions_count} piece{data.evidence_submissions_count > 1 ? 's' : ''} jointe{data.evidence_submissions_count > 1 ? 's' : ''} au dossier</p>
          </section>
        )}

        {/* E. Final status */}
        <div className="text-center py-4">
          <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-slate-100 text-sm font-medium text-slate-600" data-testid="decision-status">
            <Clock className="w-4 h-4" />
            Decision executee
          </span>
        </div>
      </div>
    </>
  );
}
