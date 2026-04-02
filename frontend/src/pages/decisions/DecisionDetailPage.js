import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { disputeAPI, notificationAPI } from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import { formatDateTimeFr } from '../../utils/dateFormat';
import {
  ArrowLeft, CheckCircle, UserX, Timer, Clock, Video, MapPin,
  Shield, XCircle, UserCheck, Eye, Navigation, QrCode, Monitor,
  LogIn, LogOut, AlertTriangle,
} from 'lucide-react';

const OUTCOME_CFG = {
  on_time: { label: (name) => `Presence validee de ${name}`, sub: (name) => `Aucune penalite appliquee a ${name}`, Icon: CheckCircle, color: 'emerald' },
  no_show: { label: (name) => `Absence confirmee de ${name}`, sub: (name) => `Penalite appliquee a ${name}`, Icon: UserX, color: 'red' },
  late_penalized: { label: (name) => `Retard confirme de ${name}`, sub: (name) => `Penalite partielle appliquee a ${name}`, Icon: Timer, color: 'amber' },
};

const STATUS_LABELS = {
  resolved: 'Arbitre par la plateforme',
  agreed_present: 'Accord mutuel — Present',
  agreed_absent: 'Accord mutuel — Absent',
  agreed_late_penalized: 'Accord mutuel — Retard',
};

const OPENED_REASON_LABELS = {
  contestant_contradiction: 'Le participant conteste et a lui-meme rempli sa feuille de presence.',
  tech_signal_contradiction: 'Un signal technique contredit les declarations.',
  collusion_signal: 'Les declarants sont aussi les beneficiaires financiers.',
  declarative_disagreement: 'Les declarations des participants ne concordent pas.',
  small_group_disagreement: 'Desaccord entre les participants du groupe.',
};

const BORDER = { emerald: 'border-emerald-300', red: 'border-red-300', amber: 'border-amber-300' };
const BG = { emerald: 'bg-emerald-50', red: 'bg-red-50', amber: 'bg-amber-50' };
const TEXT = { emerald: 'text-emerald-800', red: 'text-red-800', amber: 'text-amber-800' };

function formatTime(isoStr) {
  if (!isoStr) return null;
  try { return new Date(isoStr).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }); }
  catch { return null; }
}

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return null;
  const m = Math.round(seconds / 60);
  if (m < 1) return `${seconds}s`;
  return `${m} min`;
}

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
  const tes = data.tech_evidence_summary || {};

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

        {/* B. Decision finale */}
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

        {/* C. Preuves factuelles (NOUVEAU) */}
        <TechEvidenceSection tes={tes} targetName={targetName} appointmentType={data.appointment_type} />

        {/* D. Ce qui a ete declare */}
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
                    {dec.declared_status === 'absent' ? 'Absent' : dec.declared_status === 'present_late' ? 'Present en retard' : 'Present a l\'heure'}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400">Aucune declaration de tiers</p>
          )}

          {data.opened_reason && (
            <div className="mt-3 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg" data-testid="opened-reason">
              <p className="text-xs text-amber-800 flex items-center gap-1.5">
                <AlertTriangle className="w-3 h-3 flex-shrink-0" />
                {OPENED_REASON_LABELS[data.opened_reason] || `Raison : ${data.opened_reason.replace(/_/g, ' ')}`}
              </p>
            </div>
          )}
        </section>

        {/* E. Pieces jointes (enrichi) */}
        {data.evidence_submissions_count > 0 && (
          <section className="rounded-xl border border-slate-200 bg-white p-5 mb-5" data-testid="decision-evidence-bloc">
            <h3 className="text-sm font-bold text-slate-700 mb-2 flex items-center gap-2">
              <Shield className="w-4 h-4" /> Pieces jointes au dossier
            </h3>
            {(data.evidence_submissions || []).length > 0 ? (
              <div className="space-y-1.5">
                {data.evidence_submissions.map((ev, i) => (
                  <div key={ev.submission_id || i} className="flex items-center gap-2 text-sm text-slate-600">
                    <div className="w-1.5 h-1.5 rounded-full bg-slate-300 flex-shrink-0" />
                    <span className="capitalize">{(ev.evidence_type || 'document').replace(/_/g, ' ')}</span>
                    {ev.submitted_at && <span className="text-xs text-slate-400">— {new Date(ev.submitted_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })}</span>}
                    {ev.is_mine && <span className="text-[10px] font-medium text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">Vous</span>}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500">{data.evidence_submissions_count} piece{data.evidence_submissions_count > 1 ? 's' : ''} jointe{data.evidence_submissions_count > 1 ? 's' : ''} au dossier</p>
            )}
          </section>
        )}

        {/* F. Financial breakdown */}
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

        {/* G. Final status */}
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


/* ═══════════════════════════════════════════════════════════
   Bloc "Preuves factuelles" — Transparence sans surcharge
   ═══════════════════════════════════════════════════════════ */

function TechEvidenceSection({ tes, targetName, appointmentType }) {
  if (!tes || Object.keys(tes).length === 0) return null;

  const { video, gps, checkin, qr, nlyt, has_any_evidence } = tes;
  const name = targetName || 'Le participant';

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 mb-5" data-testid="decision-tech-evidence-bloc">
      <h3 className="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
        <Monitor className="w-4 h-4" /> Preuves factuelles
      </h3>
      <p className="text-xs text-slate-400 mb-4">
        Donnees techniques enregistrees par le systeme pour {name}.
      </p>

      {!has_any_evidence ? (
        <div className="flex items-center gap-2 px-3 py-3 bg-red-50 border border-red-200 rounded-lg" data-testid="no-evidence-banner">
          <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
          <p className="text-sm text-red-700">Aucune preuve de presence enregistree pour {name}.</p>
        </div>
      ) : (
        <div className="space-y-3" data-testid="evidence-list">
          {/* Video */}
          {video?.has_data && (
            <EvidenceRow
              icon={Video}
              iconColor="text-blue-500"
              label="Visioconference"
              testId="evidence-video"
            >
              {video.sessions.map((s, i) => (
                <div key={i} className="flex items-center gap-2 text-xs text-slate-600 mt-1">
                  <LogIn className="w-3 h-3 text-emerald-500" />
                  <span className="font-mono">{formatTime(s.joined_at) || '?'}</span>
                  <span className="text-slate-300">-</span>
                  <LogOut className="w-3 h-3 text-red-400" />
                  <span className="font-mono">{formatTime(s.left_at) || '?'}</span>
                  <span className="text-slate-400">({formatDuration(s.duration_seconds) || '?'})</span>
                  {s.provider && <span className="text-[10px] text-slate-400 capitalize">{s.provider}</span>}
                </div>
              ))}
              {video.total_duration_seconds > 0 && (
                <p className="text-xs text-slate-500 font-medium mt-1.5">
                  Total : {formatDuration(video.total_duration_seconds)}
                  {video.total_pct_of_rdv != null && <span className="text-slate-400"> ({video.total_pct_of_rdv}% du RDV)</span>}
                </p>
              )}
            </EvidenceRow>
          )}

          {/* GPS */}
          {gps?.has_data && (
            <EvidenceRow
              icon={Navigation}
              iconColor="text-teal-500"
              label="Localisation GPS"
              testId="evidence-gps"
            >
              <p className="text-xs text-slate-600 mt-1">
                {gps.within_radius ? (
                  <span className="text-emerald-600 font-medium">
                    A {gps.distance_meters != null ? `${Math.round(gps.distance_meters)}m` : '?'} du lieu (dans le perimetre)
                  </span>
                ) : (
                  <span className="text-red-600 font-medium">
                    Hors perimetre ({gps.distance_meters != null ? `${Math.round(gps.distance_meters)}m` : '?'})
                  </span>
                )}
              </p>
              {gps.geographic_detail && (
                <p className="text-[11px] text-slate-400 mt-0.5">{gps.geographic_detail}</p>
              )}
            </EvidenceRow>
          )}

          {/* NLYT Proof */}
          {nlyt?.has_data && (
            <EvidenceRow
              icon={Monitor}
              iconColor="text-sky-500"
              label="Preuve NLYT"
              testId="evidence-nlyt"
            >
              <div className="flex items-center gap-3 text-xs text-slate-600 mt-1">
                <span>Score : <strong className={nlyt.best_score >= 50 ? 'text-emerald-600' : 'text-amber-600'}>{nlyt.best_score}/100</strong></span>
                {nlyt.total_active_seconds > 0 && (
                  <span>Duree active : <strong>{formatDuration(nlyt.total_active_seconds)}</strong></span>
                )}
                {nlyt.session_count > 1 && (
                  <span className="text-slate-400">{nlyt.session_count} sessions</span>
                )}
              </div>
            </EvidenceRow>
          )}

          {/* Check-in */}
          {checkin?.has_data && (
            <EvidenceRow
              icon={UserCheck}
              iconColor="text-sky-500"
              label="Check-in"
              testId="evidence-checkin"
            >
              <p className="text-xs text-slate-600 mt-1">
                Heure : <span className="font-mono font-medium">{formatTime(checkin.timestamp) || '?'}</span>
                {checkin.temporal_detail && <span className="text-slate-400 ml-2">({checkin.temporal_detail})</span>}
              </p>
            </EvidenceRow>
          )}

          {/* QR */}
          {qr?.has_data && (
            <EvidenceRow
              icon={QrCode}
              iconColor="text-violet-500"
              label="QR Code"
              testId="evidence-qr"
            >
              <p className="text-xs text-slate-600 mt-1">
                Scanne a <span className="font-mono font-medium">{formatTime(qr.timestamp) || '?'}</span>
              </p>
            </EvidenceRow>
          )}

          {/* Aucun signal pour les types absents */}
          {!video?.has_data && !gps?.has_data && !nlyt?.has_data && !checkin?.has_data && !qr?.has_data && (
            <div className="flex items-center gap-2 text-xs text-slate-400" data-testid="no-evidence-line">
              <XCircle className="w-3.5 h-3.5" />
              <span>Aucune preuve technique enregistree</span>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function EvidenceRow({ icon: IconCmp, iconColor, label, testId, children }) {
  return (
    <div className="pl-1" data-testid={testId}>
      <div className="flex items-center gap-1.5 text-xs">
        <IconCmp className={`w-3.5 h-3.5 ${iconColor}`} />
        <span className="font-medium text-slate-700">{label}</span>
      </div>
      <div className="ml-5">{children}</div>
    </div>
  );
}
