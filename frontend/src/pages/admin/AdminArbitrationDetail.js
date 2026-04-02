import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import {
  XCircle, ArrowLeft, Clock, CheckCircle, ChevronDown,
  Video, MapPin, UserCheck, UserX, Timer, CircleDot,
  Wifi, WifiOff, Navigation, QrCode, Monitor, LogIn, LogOut,
  AlertTriangle, Minus,
} from 'lucide-react';

// ── Human-readable wording maps ──

const POSITION_STATUS = {
  confirmed_present: 'présent à l\'heure',
  confirmed_absent: 'absent',
  confirmed_late_penalized: 'en retard',
};

const OUTCOME_OPTIONS = [
  { value: 'on_time', label: 'Présent à l\'heure', subtitle: 'Aucune pénalité', icon: CheckCircle, color: 'emerald' },
  { value: 'no_show', label: 'Absent', subtitle: 'Penalite appliquee', icon: UserX, color: 'red' },
  { value: 'late_penalized', label: 'En retard', subtitle: 'Penalite partielle', icon: Timer, color: 'amber' },
];

const CONTRADICTION_HUMAN = {
  contestant_contradiction: 'Le participant conteste a lui-meme rempli sa feuille de presence, ce qui contredit les declarations des autres.',
  tech_signal_contradiction: 'Le systeme a detecte une trace de connexion, mais les autres participants declarent une absence.',
  collusion_signal: 'Les personnes qui declarent l\'absence sont aussi celles qui beneficieraient financierement de cette decision.',
  declarative_disagreement: 'Les declarations des participants ne concordent pas entre elles.',
};

// ── Main Component ──

export default function AdminArbitrationDetail() {
  const { disputeId } = useParams();
  const navigate = useNavigate();
  const [dispute, setDispute] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedOutcome, setSelectedOutcome] = useState('');
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [showWitnesses, setShowWitnesses] = useState(false);

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await adminAPI.getDisputeForArbitration(disputeId);
        setDispute(res.data);
        if (res.data?.system_analysis?.suggested_outcome) {
          setSelectedOutcome(res.data.system_analysis.suggested_outcome);
        }
      } catch (e) {
        console.error('Fetch error:', e);
        toast.error('Impossible de charger le dossier');
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [disputeId]);

  const handleResolve = async () => {
    if (!selectedOutcome) { toast.error('Selectionnez un verdict'); return; }
    if (!note || note.trim().length < 5) { toast.error('Note obligatoire (min 5 caracteres)'); return; }
    setSubmitting(true);
    try {
      await adminAPI.resolveDispute(disputeId, { final_outcome: selectedOutcome, resolution_note: note.trim() });
      toast.success('Decision validee');
      navigate('/admin/arbitration');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Erreur');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (<><AppNavbar /><div className="flex items-center justify-center min-h-[60vh]"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-slate-900" /></div></>);
  }
  if (!dispute) {
    return (<><AppNavbar /><div className="max-w-4xl mx-auto px-4 py-8 text-center"><p className="text-slate-500">Dossier introuvable</p></div></>);
  }

  const td = dispute.tech_dossier || {};
  const sa = dispute.system_analysis || {};
  const ds = dispute.declaration_summary || {};
  const hasDeclarants = (ds.declarants || []).length > 0;
  const hasEvidence = (dispute.evidence_submissions || []).length > 0;
  const hasWitnessContent = hasDeclarants || hasEvidence;

  // Read-only mode: dispute is already resolved/agreed
  const isReadOnly = dispute.status !== 'escalated';
  const resolution = dispute.resolution || {};

  // Certainty level
  const certainty = sa.confidence === 'high' ? 'evident' : sa.confidence === 'medium' ? 'analyser' : 'ambigue';

  // Disagreement summary phrase
  const disagreementPhrase = buildDisagreementPhrase(dispute);

  return (
    <>
      <AppNavbar />
      <div className="max-w-3xl mx-auto px-4 py-8" data-testid="admin-arbitration-detail">
        {/* Back */}
        <button onClick={() => navigate('/admin/arbitration')} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-5" data-testid="back-btn">
          <ArrowLeft className="w-4 h-4" /> Retour a la liste
        </button>

        {/* Header: compact context */}
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <h1 className="text-lg font-bold text-slate-900" data-testid="dispute-title">{dispute.appointment_title || 'Rendez-vous'}</h1>
            <p className="text-sm text-slate-500 mt-0.5 flex items-center gap-2 flex-wrap">
              {dispute.appointment_type === 'video' ? (
                <span className="inline-flex items-center gap-1"><Video className="w-3.5 h-3.5" />{dispute.appointment_meeting_provider || 'Visio'}</span>
              ) : (
                <span className="inline-flex items-center gap-1"><MapPin className="w-3.5 h-3.5" />{dispute.appointment_location || 'Physique'}</span>
              )}
              <span>{dispute.appointment_date ? new Date(dispute.appointment_date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}</span>
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Cible : <strong className="text-slate-600">{dispute.target_name}</strong>
              {dispute.organizer_name && <> — Organisateur : <strong className="text-slate-600">{dispute.organizer_name}</strong></>}
            </p>
          </div>
          {dispute.escalated_days_ago != null && (
            <span className={`flex-shrink-0 inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium ${
              dispute.escalated_days_ago >= 3 ? 'bg-red-100 text-red-700' : dispute.escalated_days_ago >= 1 ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'
            }`}>
              <Clock className="w-3.5 h-3.5" />
              {dispute.escalated_days_ago >= 1 ? `Il y a ${dispute.escalated_days_ago}j` : 'Aujourd\'hui'}
            </span>
          )}
        </div>

        {/* ════════ ZONE 1 — Verdict immediat ════════ */}
        <VerdictBanner td={td} sa={sa} certainty={certainty} targetName={dispute.target_name} />

        {/* Tech dossier — per-participant view */}
        <TechnicalDossier
          td={td}
          durationMinutes={dispute.appointment_duration_minutes}
          appointmentType={dispute.appointment_type}
          meetingProvider={dispute.appointment_meeting_provider}
          startDatetime={dispute.appointment_date}
          defaultOpen={true}
        />

        {/* ════════ ZONE 2 — Ce que disent les parties ════════ */}
        <section className="rounded-xl border border-slate-200 bg-white p-5 mb-5" data-testid="positions-bloc">
          <h3 className="text-sm font-bold text-slate-700 mb-4">Ce que disent les parties</h3>
          <div className="flex items-stretch gap-3">
            <PositionCard
              role="Organisateur"
              declarantName={dispute.organizer_name}
              subjectName={dispute.target_name}
              isSelfDeclaration={dispute.organizer_name === dispute.target_name}
              position={dispute.organizer_position}
              positionAt={dispute.organizer_position_at}
            />
            <div className="flex items-center px-2">
              <span className="text-xs font-bold text-slate-300">VS</span>
            </div>
            <PositionCard
              role="Participant"
              declarantName={dispute.counterpart_name || '?'}
              subjectName={dispute.target_name}
              isSelfDeclaration={false}
              position={dispute.participant_position}
              positionAt={dispute.participant_position_at}
            />
          </div>
          {disagreementPhrase && (
            <p className="text-xs text-slate-500 mt-3 italic" data-testid="disagreement-phrase">{disagreementPhrase}</p>
          )}
        </section>

        {/* ════════ ZONE 3 — Temoignages (depliable) ════════ */}
        {hasWitnessContent && (
          <div className="mb-5">
            <button
              onClick={() => setShowWitnesses(!showWitnesses)}
              className="flex items-center justify-between w-full rounded-xl border border-slate-200 bg-white px-5 py-3.5 hover:bg-slate-50 transition-colors"
              data-testid="toggle-witnesses"
            >
              <span className="text-sm font-bold text-slate-700">Ce que disent les autres participants</span>
              <span className="flex items-center gap-2">
                {hasDeclarants && (
                  <WitnessSummaryBadge ds={ds} />
                )}
                <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${showWitnesses ? 'rotate-180' : ''}`} />
              </span>
            </button>
            {showWitnesses && (
              <div className="rounded-b-xl border border-t-0 border-slate-200 bg-white px-5 py-4 space-y-4" data-testid="witnesses-content">
                {/* Declarants */}
                {hasDeclarants && (
                  <div>
                    {(ds.declarants || []).map((dec, i) => {
                      const declName = dec.first_name || 'Un participant';
                      const statusLabel = dec.declared_status === 'absent' ? 'absent' : dec.declared_status === 'present_late' ? 'present en retard' : 'present a l\'heure';
                      const phrase = `${declName} declare que ${dispute.target_name || 'la cible'} est ${statusLabel}`;
                      return (
                        <div key={i} className="flex items-center gap-2 text-sm py-1.5">
                          {dec.declared_status === 'absent' ? (
                            <UserX className="w-4 h-4 text-red-500" />
                          ) : (
                            <UserCheck className="w-4 h-4 text-emerald-500" />
                          )}
                          <span className="text-slate-700">{phrase}</span>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Contradiction signal */}
                {dispute.opened_reason && (
                  <div className="px-3 py-2.5 bg-amber-50 border border-amber-200 rounded-lg">
                    <p className="text-xs text-amber-800">
                      {CONTRADICTION_HUMAN[dispute.opened_reason] || `Point d'attention : ${dispute.opened_reason.replace(/_/g, ' ')}`}
                    </p>
                  </div>
                )}

                {/* Evidence submissions */}
                {hasEvidence && (
                  <div>
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Pieces jointes ({dispute.evidence_submissions.length})</p>
                    {dispute.evidence_submissions.map((ev, i) => (
                      <div key={ev.submission_id || i} className="bg-slate-50 rounded-lg p-3 border border-slate-100 mb-2">
                        <p className="text-xs text-slate-500">{ev.evidence_type}{ev.submitted_at ? ` — ${new Date(ev.submitted_at).toLocaleDateString('fr-FR')}` : ''}</p>
                        {ev.text_content && <p className="text-sm text-slate-700 mt-1">{ev.text_content}</p>}
                        {ev.content_url && <a href={ev.content_url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 underline mt-1 inline-block">Voir le fichier</a>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ════════ ZONE 4 — Decision (active) or Resolution (read-only) ════════ */}
        {isReadOnly ? (
          <ResolutionReadOnly resolution={resolution} targetName={dispute.target_name} status={dispute.status} />
        ) : (
          <section className="rounded-xl border-2 border-slate-900 bg-white p-6" data-testid="arbitration-action-bloc">
            <h3 className="text-base font-bold text-slate-900 mb-1">Votre decision</h3>
            <p className="text-xs text-slate-500 mb-5">Cette decision est definitive. La consequence financiere sera appliquee immediatement.</p>

            {/* Outcome cards */}
            <div className="grid grid-cols-3 gap-3 mb-5" data-testid="outcome-options">
              {OUTCOME_OPTIONS.map((opt) => {
                const Icon = opt.icon;
                const selected = selectedOutcome === opt.value;
                const ring = {
                  emerald: selected ? 'border-emerald-500 bg-emerald-50 ring-2 ring-emerald-200' : 'border-slate-200 hover:border-emerald-300',
                  red: selected ? 'border-red-500 bg-red-50 ring-2 ring-red-200' : 'border-slate-200 hover:border-red-300',
                  amber: selected ? 'border-amber-500 bg-amber-50 ring-2 ring-amber-200' : 'border-slate-200 hover:border-amber-300',
                };
                return (
                  <button
                    key={opt.value}
                    onClick={() => setSelectedOutcome(opt.value)}
                    className={`rounded-xl border-2 p-4 text-center transition-all cursor-pointer ${ring[opt.color]}`}
                    data-testid={`outcome-${opt.value}`}
                  >
                    <Icon className={`w-6 h-6 mx-auto mb-1.5 ${selected ? `text-${opt.color}-600` : 'text-slate-400'}`} />
                    <p className={`text-sm font-semibold ${selected ? 'text-slate-900' : 'text-slate-600'}`}>{opt.label}</p>
                    <p className="text-[11px] text-slate-400 mt-0.5">{opt.subtitle}</p>
                  </button>
                );
              })}
            </div>

            {/* Note */}
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Justifiez votre decision en quelques mots..."
              className="w-full border border-slate-300 rounded-lg px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400 resize-none"
              rows={3}
              data-testid="arbitration-note"
            />

            <div className="flex items-center justify-end mt-4">
              <Button
                onClick={handleResolve}
                disabled={submitting || !selectedOutcome || !note || note.trim().length < 5}
                className="px-6"
                data-testid="submit-arbitration-btn"
              >
                {submitting ? 'Traitement...' : 'Valider la decision'}
              </Button>
            </div>
          </section>
        )}

        {/* ════════ ZONE 5 — Detail financier (bloc separe) ════════ */}
        {dispute.financial_context && (
          <FinancialPreview
            outcome={isReadOnly ? (resolution?.final_outcome || selectedOutcome) : selectedOutcome}
            fc={dispute.financial_context}
            targetName={dispute.target_name}
            organizerName={dispute.organizer_name}
          />
        )}
      </div>
    </>
  );
}

// ── Zone 1: Verdict Banner ──

function VerdictBanner({ td, sa, certainty, targetName }) {
  const hasProof = td.has_admissible_proof;
  const name = targetName || 'Ce participant';

  const CERT_CONFIG = {
    evident: { label: 'Decision evidente', dot: 'bg-red-500', bg: 'bg-red-50', text: 'text-red-700' },
    analyser: { label: 'Cas a analyser', dot: 'bg-amber-400', bg: 'bg-amber-50', text: 'text-amber-700' },
    ambigue: { label: 'Situation ambigue', dot: 'bg-blue-400', bg: 'bg-blue-50', text: 'text-blue-700' },
  };
  const cert = CERT_CONFIG[certainty] || CERT_CONFIG.ambigue;

  if (hasProof) {
    return (
      <section className="rounded-xl border-2 border-emerald-300 bg-emerald-50 p-5 mb-3" data-testid="verdict-bloc">
        <CertaintyBadge config={CERT_CONFIG.ambigue} label="Presence confirmee" />
        <h2 className="text-lg font-bold text-emerald-900 mt-2">Presence de {name} confirmee par le systeme.</h2>
        <p className="text-sm text-emerald-700 mt-1">
          Une preuve de connexion ou de localisation a ete validee automatiquement.
          Ce dossier n'aurait normalement pas du etre escalade.
        </p>
      </section>
    );
  }

  const nlytLevel = td.proof_summary?.nlyt_proof_level;
  const isPartial = nlytLevel === 'medium' || nlytLevel === 'weak';

  if (isPartial) {
    return (
      <section className="rounded-xl border-2 border-amber-300 bg-amber-50 p-5 mb-3" data-testid="verdict-bloc">
        <CertaintyBadge config={cert} />
        <h2 className="text-lg font-bold text-amber-900 mt-2">Presence de {name} partiellement detectee.</h2>
        <p className="text-sm text-amber-700 mt-1">
          Un signal de connexion a ete detecte mais il est insuffisant pour valider automatiquement.
          {name} n'a pas fourni d'element suffisant pour prouver sa presence de maniere certaine.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border-2 border-red-300 bg-red-50 p-5 mb-3" data-testid="verdict-bloc">
      <CertaintyBadge config={cert} />
      <h2 className="text-lg font-bold text-red-900 mt-2">{name} n'a pas prouve sa presence.</h2>
      <p className="text-sm text-red-700 mt-1">
        {name} n'a fourni aucun element pour prouver sa presence.
        Aucune preuve de connexion, de localisation ou de check-in n'a ete enregistree.
      </p>
      <p className="text-sm text-red-800 font-medium mt-2">
        Sans preuve, la regle du systeme est d'appliquer une penalite.
      </p>
    </section>
  );
}

function CertaintyBadge({ config, label }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold ${config.bg} ${config.text}`} data-testid="certainty-badge">
      <CircleDot className="w-3 h-3" />
      {label || config.label}
    </span>
  );
}

// ── Zone 2: Position Card ──

function PositionCard({ role, declarantName, subjectName, isSelfDeclaration, position, positionAt }) {
  const isPresent = position === 'confirmed_present';
  const isAbsent = position === 'confirmed_absent';
  const colors = isPresent ? 'bg-emerald-50 border-emerald-200' : isAbsent ? 'bg-red-50 border-red-200' : 'bg-slate-50 border-slate-200';
  const textColor = isPresent ? 'text-emerald-700' : isAbsent ? 'text-red-700' : 'text-amber-700';

  const statusLabel = POSITION_STATUS[position];
  let phrase;
  if (!statusLabel) {
    phrase = 'Position non soumise';
  } else if (isSelfDeclaration || declarantName === subjectName) {
    phrase = `${declarantName} maintient etre ${statusLabel}`;
  } else {
    phrase = `${declarantName} maintient que ${subjectName} est ${statusLabel}`;
  }

  return (
    <div className={`flex-1 rounded-lg border p-4 ${colors}`} data-testid={`position-${role.toLowerCase()}`}>
      <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">Position de {declarantName}</p>
      <p className={`text-sm font-bold mt-2 ${textColor}`}>
        {phrase}
      </p>
      {positionAt && (
        <p className="text-[10px] text-slate-400 mt-1.5">
          le {new Date(positionAt).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })}
        </p>
      )}
    </div>
  );
}

// ── Zone 3: Witness summary badge ──

function WitnessSummaryBadge({ ds }) {
  const present = ds.declared_present_count || 0;
  const absent = ds.declared_absent_count || 0;
  if (absent > 0 && present === 0) {
    return <span className="text-[11px] font-medium text-red-600 bg-red-50 px-2 py-0.5 rounded-full">{absent} confirme{absent > 1 ? 'nt' : ''} l'absence</span>;
  }
  if (present > 0 && absent === 0) {
    return <span className="text-[11px] font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">{present} confirme{present > 1 ? 'nt' : ''} la presence</span>;
  }
  if (present > 0 && absent > 0) {
    return <span className="text-[11px] font-medium text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">Avis partages</span>;
  }
  return null;
}

// ── Zone 4: Financial Preview ──

function FinancialPreview({ outcome, fc, targetName, organizerName }) {
  const name = targetName || 'Le participant';
  const orgName = organizerName || 'l\'organisateur';
  const cur = (fc.penalty_currency || 'eur').toUpperCase();
  const penalty = fc.penalty_amount || 0;

  if (!outcome) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-5 mt-5" data-testid="financial-preview">
        <h3 className="text-sm font-bold text-slate-700 mb-2">Detail financier</h3>
        <p className="text-sm text-slate-400">Selectionnez un verdict pour voir les consequences financieres.</p>
      </div>
    );
  }

  if (outcome === 'on_time') {
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5 mt-5" data-testid="financial-preview">
        <h3 className="text-sm font-bold text-emerald-800 mb-2">Detail financier</h3>
        <p className="text-sm text-emerald-700">Aucun prelevement. La garantie de {name} sera liberee.</p>
      </div>
    );
  }

  if (penalty === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-5 mt-5" data-testid="financial-preview">
        <h3 className="text-sm font-bold text-slate-700 mb-2">Detail financier</h3>
        <p className="text-sm text-slate-500">Aucune garantie financiere configuree pour ce rendez-vous.</p>
      </div>
    );
  }

  const platform = fc.platform_amount || 0;
  const charity = fc.charity_amount || 0;
  const compensation = fc.compensation_amount || 0;
  const isPartial = outcome === 'late_penalized';

  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-5 mt-5" data-testid="financial-preview">
      <h3 className="text-sm font-bold text-red-800 mb-3">
        Detail financier{isPartial ? ' (retard)' : ''}
      </h3>
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-700">Montant preleve a {name}</span>
          <span className="font-bold text-red-700">{penalty.toFixed(0)} {cur}</span>
        </div>
        {compensation > 0 && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-700">Montant recu par {orgName} (organisateur)</span>
            <span className="font-medium text-emerald-700">{compensation.toFixed(0)} {cur}</span>
          </div>
        )}
        {platform > 0 && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-700">Commission NLYT ({fc.platform_commission_percent}%)</span>
            <span className="font-medium text-slate-500">{platform.toFixed(0)} {cur}</span>
          </div>
        )}
        {charity > 0 && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-700">Montant reverse a l'association ({fc.charity_percent}%)</span>
            <span className="font-medium text-slate-500">{charity.toFixed(0)} {cur}</span>
          </div>
        )}
      </div>
    </div>
  );
}



// ── Zone 4 Read-Only: Resolution Summary ──

const OUTCOME_LABELS = {
  on_time: { label: 'Présent à l\'heure', subtitle: 'Aucune pénalité', color: 'emerald', Icon: CheckCircle },
  no_show: { label: 'Absent', subtitle: 'Penalite appliquee', color: 'red', Icon: UserX },
  late_penalized: { label: 'En retard', subtitle: 'Penalite partielle', color: 'amber', Icon: Timer },
};

const STATUS_LABELS_RESOLVED = {
  resolved: 'Arbitre par l\'admin',
  agreed_present: 'Accord mutuel : Présent à l\'heure',
  agreed_absent: 'Accord mutuel : Absent',
  agreed_late_penalized: 'Accord mutuel : Retard',
};

function ResolutionReadOnly({ resolution, targetName, status }) {
  const outcome = resolution?.final_outcome;
  const note = resolution?.resolution_note || '';
  const resolvedAt = resolution?.resolved_at;
  const resolvedBy = resolution?.resolved_by;
  const cfg = OUTCOME_LABELS[outcome] || OUTCOME_LABELS.no_show;
  const Icon = cfg.Icon;
  const name = targetName || 'Le participant';

  const borderColor = { emerald: 'border-emerald-300', red: 'border-red-300', amber: 'border-amber-300' };
  const bgColor = { emerald: 'bg-emerald-50', red: 'bg-red-50', amber: 'bg-amber-50' };
  const textColor = { emerald: 'text-emerald-800', red: 'text-red-800', amber: 'text-amber-800' };

  return (
    <section className={`rounded-xl border-2 ${borderColor[cfg.color]} ${bgColor[cfg.color]} p-6`} data-testid="resolution-readonly-bloc">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Decision rendue</span>
        <span className="text-[11px] text-slate-400 ml-auto">
          {STATUS_LABELS_RESOLVED[status] || 'Resolu'}
          {resolvedAt && <> — {new Date(resolvedAt).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}</>}
        </span>
      </div>

      {/* Outcome */}
      <div className="flex items-center gap-3 mt-3 mb-4">
        <div className={`w-12 h-12 rounded-xl ${bgColor[cfg.color]} border ${borderColor[cfg.color]} flex items-center justify-center`}>
          <Icon className={`w-6 h-6 ${textColor[cfg.color]}`} />
        </div>
        <div>
          <p className={`text-lg font-bold ${textColor[cfg.color]}`}>{cfg.label}</p>
          <p className="text-sm text-slate-500">{cfg.subtitle}</p>
        </div>
      </div>

      {/* Note */}
      {note && (
        <div className="bg-white/60 rounded-lg border border-white/80 px-4 py-3 mb-4">
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-1">Justification</p>
          <p className="text-sm text-slate-700">{note}</p>
        </div>
      )}
    </section>
  );
}

// ── Helpers ──

// ── Technical Dossier — Per-participant evidence view ──

function formatTime(isoStr) {
  if (!isoStr) return '—';
  try { return new Date(isoStr).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }); }
  catch { return '—'; }
}

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return '—';
  const m = Math.round(seconds / 60);
  if (m < 1) return `${seconds}s`;
  return `${m} min`;
}

function pctOfRdv(seconds, durationMinutes) {
  if (!seconds || !durationMinutes) return null;
  return Math.round((seconds / (durationMinutes * 60)) * 100);
}

function TechnicalDossier({ td, durationMinutes, appointmentType, meetingProvider, startDatetime, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  const dossiers = td?.participant_dossiers || [];

  if (dossiers.length === 0) return null;

  // Sort: target first, then organizer, then rest
  const sorted = [...dossiers].sort((a, b) => {
    if (a.is_target && !b.is_target) return -1;
    if (!a.is_target && b.is_target) return 1;
    if (a.is_organizer && !b.is_organizer) return -1;
    if (!a.is_organizer && b.is_organizer) return 1;
    return 0;
  });

  return (
    <section className="mb-5" data-testid="technical-dossier">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full rounded-xl border border-slate-200 bg-white px-5 py-3.5 hover:bg-slate-50 transition-colors"
        data-testid="toggle-tech-dossier"
      >
        <span className="text-sm font-bold text-slate-700">Dossier technique</span>
        <span className="flex items-center gap-2">
          <span className="text-[11px] text-slate-400">
            {dossiers.length} participant{dossiers.length > 1 ? 's' : ''}
            {durationMinutes ? ` · ${durationMinutes} min` : ''}
            {meetingProvider ? ` · ${meetingProvider.charAt(0).toUpperCase() + meetingProvider.slice(1)}` : ''}
          </span>
          <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
        </span>
      </button>

      {open && (
        <div className="rounded-b-xl border border-t-0 border-slate-200 bg-white px-5 py-4 space-y-4" data-testid="tech-dossier-content">
          {/* RDV context bar */}
          <div className="flex items-center gap-3 text-xs text-slate-400 pb-3 border-b border-slate-100">
            <span>{appointmentType === 'video' ? 'Visio' : 'Physique'}</span>
            <span>·</span>
            <span>{startDatetime ? formatTime(startDatetime) : '—'} → {startDatetime && durationMinutes ? formatTime(new Date(new Date(startDatetime).getTime() + durationMinutes * 60000).toISOString()) : '—'}</span>
            <span>·</span>
            <span>{durationMinutes} min</span>
          </div>

          {sorted.map((p) => (
            <ParticipantDossierCard key={p.participant_id} p={p} durationMinutes={durationMinutes} />
          ))}

          {/* Incoherence detection */}
          <IncoherenceSummary dossiers={sorted} />
        </div>
      )}
    </section>
  );
}

function ParticipantDossierCard({ p, durationMinutes }) {
  const hasVideo = p.video_sessions?.length > 0;
  const hasCheckin = !!p.checkin;
  const hasGps = !!p.gps;
  const hasQr = !!p.qr;
  const hasProofSessions = p.proof_sessions?.length > 0;
  const hasAnyEvidence = hasVideo || hasCheckin || hasGps || hasQr || hasProofSessions || p.evidence_count > 0;

  // Total video duration
  const totalVideoSeconds = hasVideo ? p.video_sessions.reduce((acc, s) => acc + (s.duration_seconds || 0), 0) : 0;
  const videoPct = pctOfRdv(totalVideoSeconds, durationMinutes);

  // Total proof session active duration
  const totalProofSeconds = hasProofSessions ? p.proof_sessions.reduce((acc, s) => acc + (s.active_duration_seconds || 0), 0) : 0;
  const totalProofHeartbeats = hasProofSessions ? p.proof_sessions.reduce((acc, s) => acc + (s.heartbeat_count || 0), 0) : 0;
  const bestScore = hasProofSessions ? Math.max(...p.proof_sessions.map(s => s.score || 0)) : 0;

  // Role label
  const roleLabel = p.is_organizer ? 'Organisateur' : 'Participant';
  const name = `${p.first_name || ''} ${p.last_name || ''}`.trim() || p.email;

  // Declaration context
  const declPresent = p.declarations_about?.declared_present || 0;
  const declAbsent = p.declarations_about?.declared_absent || 0;

  // Signal badge — factoring in both evidence_items AND proof_sessions
  let signalBadge;
  if (!hasAnyEvidence) {
    signalBadge = { label: 'Aucune trace', bg: 'bg-slate-100', text: 'text-slate-500', Icon: WifiOff };
  } else if (hasVideo && videoPct >= 70) {
    signalBadge = { label: `Signal fort (${videoPct}%)`, bg: 'bg-emerald-50', text: 'text-emerald-700', Icon: Wifi };
  } else if (hasVideo || hasGps || hasQr) {
    signalBadge = { label: 'Signal partiel', bg: 'bg-amber-50', text: 'text-amber-700', Icon: Wifi };
  } else if (hasProofSessions && bestScore >= 50) {
    signalBadge = { label: `NLYT score ${bestScore}`, bg: 'bg-sky-50', text: 'text-sky-700', Icon: Monitor };
  } else if (hasProofSessions) {
    signalBadge = { label: `NLYT faible (${bestScore})`, bg: 'bg-amber-50', text: 'text-amber-600', Icon: Monitor };
  } else {
    signalBadge = { label: 'Check-in seul', bg: 'bg-sky-50', text: 'text-sky-700', Icon: Monitor };
  }

  return (
    <div
      className={`rounded-lg border p-4 ${p.is_target ? 'border-blue-200 bg-blue-50/30' : 'border-slate-100 bg-slate-50/30'}`}
      data-testid={`dossier-${p.participant_id}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-900">{name}</span>
          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${p.is_target ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-500'}`}>
            {roleLabel}{p.is_target ? ' · cible' : ''}
          </span>
        </div>
        <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full ${signalBadge.bg} ${signalBadge.text}`}>
          <signalBadge.Icon className="w-3 h-3" />
          {signalBadge.label}
        </span>
      </div>

      {/* Declarations about this person */}
      {(declPresent > 0 || declAbsent > 0) && (
        <div className="flex items-center gap-3 text-xs mb-3 pb-2 border-b border-slate-100">
          {declPresent > 0 && <span className="text-emerald-600 font-medium">{declPresent} participant{declPresent > 1 ? 's' : ''} declare{declPresent > 1 ? 'nt' : ''} {name} present</span>}
          {declPresent > 0 && declAbsent > 0 && <span className="text-slate-300">|</span>}
          {declAbsent > 0 && <span className="text-red-600 font-medium">{declAbsent} participant{declAbsent > 1 ? 's' : ''} declare{declAbsent > 1 ? 'nt' : ''} {name} absent</span>}
        </div>
      )}

      {/* Evidence rows */}
      <div className="space-y-2">
        {/* Video sessions */}
        {hasVideo ? (
          <div data-testid={`evidence-video-${p.participant_id}`}>
            <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-1">
              <Video className="w-3.5 h-3.5" />
              <span className="font-medium">Visio</span>
              <span className="text-slate-400">· {p.video_sessions.length} session{p.video_sessions.length > 1 ? 's' : ''}</span>
            </div>
            {p.video_sessions.map((s, i) => (
              <div key={i} className="flex items-center gap-2 text-xs ml-5 py-0.5">
                <LogIn className="w-3 h-3 text-emerald-500" />
                <span className="text-slate-700 font-mono">{formatTime(s.joined_at)}</span>
                <span className="text-slate-300">→</span>
                <LogOut className="w-3 h-3 text-red-400" />
                <span className="text-slate-700 font-mono">{formatTime(s.left_at)}</span>
                <span className="text-slate-400">({formatDuration(s.duration_seconds)})</span>
                {s.identity_confidence && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${s.identity_confidence === 'high' ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600'}`}>
                    id: {s.identity_confidence}
                  </span>
                )}
              </div>
            ))}
            <div className="flex items-center gap-2 text-xs ml-5 pt-1 text-slate-500 font-medium">
              <span>Total : {formatDuration(totalVideoSeconds)}</span>
              {videoPct != null && <span className="text-slate-400">({videoPct}% du RDV)</span>}
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Video className="w-3.5 h-3.5" />
            <span>Visio : aucune donnee</span>
          </div>
        )}

        {/* Check-in NLYT */}
        {hasCheckin ? (
          <div className="flex items-center gap-1.5 text-xs" data-testid={`evidence-checkin-${p.participant_id}`}>
            <UserCheck className="w-3.5 h-3.5 text-sky-500" />
            <span className="text-slate-600">Check-in : <span className="font-mono font-medium">{formatTime(p.checkin.timestamp)}</span></span>
            {p.checkin.temporal_detail && <span className="text-slate-400">({p.checkin.temporal_detail})</span>}
          </div>
        ) : !hasProofSessions && (
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <UserCheck className="w-3.5 h-3.5" />
            <span>Check-in : —</span>
          </div>
        )}

        {/* NLYT Proof Sessions */}
        {hasProofSessions ? (
          <div data-testid={`evidence-nlyt-${p.participant_id}`}>
            <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-1">
              <Monitor className="w-3.5 h-3.5" />
              <span className="font-medium">Sessions NLYT</span>
              <span className="text-slate-400">· {p.proof_sessions.length} session{p.proof_sessions.length > 1 ? 's' : ''}</span>
            </div>
            {p.proof_sessions.map((s, i) => (
              <div key={i} className="flex items-center gap-2 text-xs ml-5 py-0.5">
                <LogIn className="w-3 h-3 text-sky-500" />
                <span className="text-slate-700 font-mono">{formatTime(s.checked_in_at)}</span>
                <span className="text-slate-300">→</span>
                <LogOut className="w-3 h-3 text-slate-400" />
                <span className="text-slate-700 font-mono">{formatTime(s.checked_out_at)}</span>
                <span className="text-slate-400">({formatDuration(s.active_duration_seconds)} actif)</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  s.score >= 50 ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600'
                }`}>
                  {s.score}/100
                </span>
                <span className="text-[10px] text-slate-400">{s.heartbeat_count} hb</span>
              </div>
            ))}
            <div className="flex items-center gap-3 text-xs ml-5 pt-1 text-slate-500 font-medium">
              <span>Total actif : {formatDuration(totalProofSeconds)}</span>
              <span className="text-slate-400">·</span>
              <span>{totalProofHeartbeats} heartbeats</span>
              <span className="text-slate-400">·</span>
              <span>Meilleur score : {bestScore}/100</span>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Monitor className="w-3.5 h-3.5" />
            <span>Sessions NLYT : —</span>
          </div>
        )}

        {/* GPS */}
        {hasGps ? (
          <div className="flex items-center gap-1.5 text-xs" data-testid={`evidence-gps-${p.participant_id}`}>
            <Navigation className="w-3.5 h-3.5 text-teal-500" />
            <span className="text-slate-600">
              GPS : {p.gps.within_radius ? (
                <span className="text-emerald-600 font-medium">a {p.gps.distance_meters != null ? `${Math.round(p.gps.distance_meters)}m` : '?'} du lieu</span>
              ) : (
                <span className="text-red-600 font-medium">hors zone ({p.gps.distance_meters != null ? `${Math.round(p.gps.distance_meters)}m` : '?'})</span>
              )}
            </span>
            {p.gps.geographic_detail && <span className="text-slate-400 truncate max-w-[180px]">({p.gps.geographic_detail})</span>}
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Navigation className="w-3.5 h-3.5" />
            <span>GPS : —</span>
          </div>
        )}

        {/* QR */}
        {hasQr ? (
          <div className="flex items-center gap-1.5 text-xs" data-testid={`evidence-qr-${p.participant_id}`}>
            <QrCode className="w-3.5 h-3.5 text-violet-500" />
            <span className="text-slate-600">QR : <span className="font-mono font-medium">{formatTime(p.qr.timestamp)}</span></span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <QrCode className="w-3.5 h-3.5" />
            <span>QR : —</span>
          </div>
        )}
      </div>
    </div>
  );
}

function IncoherenceSummary({ dossiers }) {
  const flags = [];

  for (const p of dossiers) {
    const name = `${p.first_name || ''}`.trim() || 'Un participant';
    const hasAnySignal = p.video_sessions?.length > 0 || p.checkin || p.gps || p.qr || p.proof_sessions?.length > 0;
    const declAbsent = p.declarations_about?.declared_absent || 0;
    const declPresent = p.declarations_about?.declared_present || 0;

    // Signal technique present mais declare absent par d'autres
    if (hasAnySignal && declAbsent > 0) {
      const totalSec = (p.video_sessions || []).reduce((a, s) => a + (s.duration_seconds || 0), 0);
      const proofSec = (p.proof_sessions || []).reduce((a, s) => a + (s.active_duration_seconds || 0), 0);
      const detail = totalSec > 0 ? ` (${Math.round(totalSec / 60)} min de visio)` : proofSec > 0 ? ` (${Math.round(proofSec / 60)} min actif NLYT)` : '';
      flags.push({
        type: 'contradiction',
        text: `${name} a une trace technique${detail}, mais est declare absent par ${declAbsent} participant${declAbsent > 1 ? 's' : ''}.`,
      });
    }

    // Aucun signal mais declare present par tous
    if (!hasAnySignal && declPresent > 0 && declAbsent === 0) {
      flags.push({
        type: 'missing_proof',
        text: `${name} est déclaré présent à l'heure, mais aucune trace technique n'a été enregistrée.`,
      });
    }
  }

  if (flags.length === 0) return null;

  return (
    <div className="mt-2 space-y-2" data-testid="incoherence-summary">
      {flags.map((f, i) => (
        <div key={i} className={`flex items-start gap-2 rounded-lg px-3 py-2 text-xs ${
          f.type === 'contradiction' ? 'bg-amber-50 border border-amber-200 text-amber-800' : 'bg-blue-50 border border-blue-200 text-blue-800'
        }`}>
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
          <span>{f.text}</span>
        </div>
      ))}
    </div>
  );
}

function buildDisagreementPhrase(dispute) {
  const org = dispute.organizer_position;
  const par = dispute.participant_position;
  if (!org || !par) return null;
  if (org === par) return 'Les deux parties sont d\'accord.';
  const orgName = dispute.organizer_name || 'L\'organisateur';
  const cpName = dispute.counterpart_name || 'Le participant';
  const targetName = dispute.target_name || 'la cible';
  const orgSays = POSITION_STATUS[org] || '?';
  const parSays = POSITION_STATUS[par] || '?';
  const orgPhrase = orgName === targetName
    ? `${orgName} maintient etre ${orgSays}`
    : `${orgName} maintient que ${targetName} est ${orgSays}`;
  const cpPhrase = cpName === targetName
    ? `${cpName} maintient etre ${parSays}`
    : `${cpName} maintient que ${targetName} est ${parSays}`;
  return `Desaccord : ${orgPhrase}. ${cpPhrase}.`;
}
