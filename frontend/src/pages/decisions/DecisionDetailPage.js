import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { disputeAPI, notificationAPI } from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import { formatDateTimeFr } from '../../utils/dateFormat';
import {
  ArrowLeft, CheckCircle, UserX, Timer, Clock, Video, MapPin,
  Shield, XCircle, UserCheck, Eye, Navigation, QrCode, Monitor,
  LogIn, LogOut, AlertTriangle, User,
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
        <DeclarationSection
          ds={ds}
          data={data}
          outcome={outcome}
        />

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


/* ═══════════════════════════════════════════════════════════
   Bloc "Ce qui a ete declare" — Vue par participant enrichie
   ═══════════════════════════════════════════════════════════ */

const DECL_STATUS = {
  present_on_time: 'Present a l\'heure',
  present_late: 'Present en retard',
  absent: 'Absent',
  unknown: 'Non renseigne',
};

const POSITION_LABELS = {
  confirmed_present: 'Maintient : Present',
  confirmed_absent: 'Maintient : Absent',
  confirmed_late_penalized: 'Maintient : Retard',
};

const CONTRADICTION_CFG = {
  unanimous_present: { label: 'Accord', cls: 'bg-emerald-50 border-emerald-200 text-emerald-800', icon: CheckCircle, iconCls: 'text-emerald-500' },
  unanimous_absent: { label: 'Accord', cls: 'bg-red-50 border-red-200 text-red-800', icon: XCircle, iconCls: 'text-red-500' },
  majority_present: { label: 'Majorite', cls: 'bg-blue-50 border-blue-200 text-blue-800', icon: Eye, iconCls: 'text-blue-500' },
  majority_absent: { label: 'Majorite', cls: 'bg-amber-50 border-amber-200 text-amber-800', icon: Eye, iconCls: 'text-amber-500' },
  disagreement: { label: 'Desaccord', cls: 'bg-amber-50 border-amber-200 text-amber-800', icon: AlertTriangle, iconCls: 'text-amber-500' },
  contradiction_with_proof: { label: 'Contradiction', cls: 'bg-red-50 border-red-200 text-red-800', icon: AlertTriangle, iconCls: 'text-red-500' },
  no_declarations: { label: 'Aucune declaration', cls: 'bg-slate-50 border-slate-200 text-slate-600', icon: Eye, iconCls: 'text-slate-400' },
};

const OUTCOME_PHRASES = {
  on_time: 'presence confirmee',
  no_show: 'absence confirmee',
  late_penalized: 'retard confirme',
};

function DeclarationSection({ ds, data, outcome }) {
  const level = ds.contradiction_level || 'no_declarations';
  const cfg = CONTRADICTION_CFG[level] || CONTRADICTION_CFG.no_declarations;
  const CIcon = cfg.icon;
  const selfDecl = ds.target_self_declaration;
  const targetName = ds.target_name || data.target_name || 'Le participant';
  const orgPos = data.organizer_position;
  const partPos = data.participant_position;
  const hasPositions = orgPos || partPos;
  const otherName = data.other_party_name || '';

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 mb-5" data-testid="decision-declarations-bloc">
      <h3 className="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
        <Eye className="w-4 h-4" /> Ce qui a ete declare
      </h3>

      {/* Résumé de synthèse */}
      {ds.summary_phrase && (
        <div className={`flex items-start gap-2 px-3 py-2.5 rounded-lg border mb-4 ${cfg.cls}`} data-testid="contradiction-summary">
          <CIcon className={`w-4 h-4 flex-shrink-0 mt-0.5 ${cfg.iconCls}`} />
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wide opacity-70">{cfg.label}</span>
            <p className="text-sm leading-snug">{ds.summary_phrase}</p>
          </div>
        </div>
      )}

      {/* Déclarations par participant */}
      <div className="space-y-2.5" data-testid="declarations-by-participant">
        {/* Cible en premier — sa propre déclaration */}
        {selfDecl && (
          <DeclarantRow
            name={targetName}
            roleLabel="Cible du litige"
            declaredStatus={selfDecl}
            isSelf
            testId="self-declaration"
          />
        )}

        {/* Déclarations de tiers */}
        {(ds.declarants || []).map((dec, i) => (
          <DeclarantRow
            key={i}
            name={dec.first_name || 'Participant'}
            roleLabel={dec.is_organizer ? 'Organisateur' : ''}
            declaredStatus={dec.declared_status}
            isMe={dec.is_me}
            testId={`declarant-${i}`}
          />
        ))}

        {!selfDecl && (ds.declarants || []).length === 0 && (
          <p className="text-xs text-slate-400" data-testid="no-declarations">Aucune declaration enregistree</p>
        )}
      </div>

      {/* Positions confirmées pendant le litige */}
      {hasPositions && (
        <div className="mt-4 pt-3 border-t border-slate-100" data-testid="dispute-positions">
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-2">Positions pendant le litige</p>
          <div className="space-y-1.5">
            {orgPos && (
              <div className="flex items-center gap-2 text-xs" data-testid="org-position">
                <Shield className="w-3 h-3 text-slate-400" />
                <span className="text-slate-500">Organisateur{otherName && data.my_role === 'participant' ? ` (${otherName})` : data.my_role === 'organizer' ? ' (Vous)' : ''}</span>
                <span className={`font-medium ${orgPos === 'confirmed_absent' ? 'text-red-600' : orgPos === 'confirmed_present' ? 'text-emerald-600' : 'text-amber-600'}`}>
                  {POSITION_LABELS[orgPos] || orgPos}
                </span>
              </div>
            )}
            {partPos && (
              <div className="flex items-center gap-2 text-xs" data-testid="part-position">
                <User className="w-3 h-3 text-slate-400" />
                <span className="text-slate-500">Participant{data.my_role === 'organizer' && otherName ? ` (${otherName})` : data.my_role === 'participant' ? ' (Vous)' : ''}</span>
                <span className={`font-medium ${partPos === 'confirmed_absent' ? 'text-red-600' : partPos === 'confirmed_present' ? 'text-emerald-600' : 'text-amber-600'}`}>
                  {POSITION_LABELS[partPos] || partPos}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Raison d'ouverture */}
      {data.opened_reason && (
        <div className="mt-3 px-3 py-2 bg-amber-50/60 border border-amber-200/60 rounded-lg" data-testid="opened-reason">
          <p className="text-xs text-amber-700 flex items-center gap-1.5">
            <AlertTriangle className="w-3 h-3 flex-shrink-0" />
            {OPENED_REASON_LABELS[data.opened_reason] || `Raison : ${data.opened_reason.replace(/_/g, ' ')}`}
          </p>
        </div>
      )}

      {/* Phrase de liaison vers la décision */}
      {data.status && OUTCOME_PHRASES[outcome] && (
        <p className="mt-3 text-xs text-slate-500 italic" data-testid="decision-link-phrase">
          Sur la base des preuves et declarations, la decision a ete : {OUTCOME_PHRASES[outcome]}.
        </p>
      )}
    </section>
  );
}

function DeclarantRow({ name, roleLabel, declaredStatus, isSelf, isMe, testId }) {
  const statusLabel = DECL_STATUS[declaredStatus] || declaredStatus;
  const isAbsent = declaredStatus === 'absent';
  const StatusIcon = isAbsent ? UserX : UserCheck;
  const statusColor = isAbsent ? 'text-red-600' : 'text-emerald-600';
  const iconColor = isAbsent ? 'text-red-500' : 'text-emerald-500';

  return (
    <div className="flex items-center gap-2 text-sm" data-testid={testId}>
      <StatusIcon className={`w-3.5 h-3.5 flex-shrink-0 ${iconColor}`} />
      <span className="text-slate-700 font-medium">{name}</span>
      {roleLabel && <span className="text-[10px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">{roleLabel}</span>}
      {isMe && <span className="text-[10px] font-medium text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">Vous</span>}
      <span className="text-slate-300 mx-0.5">:</span>
      <span className={`text-xs font-medium ${statusColor}`}>
        {isSelf ? `Se declare ${statusLabel.toLowerCase()}` : statusLabel}
      </span>
    </div>
  );
}
