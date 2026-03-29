import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import {
  XCircle, ArrowLeft, Clock, CheckCircle, ChevronDown,
  Video, MapPin, UserCheck, UserX, Timer, CircleDot,
} from 'lucide-react';

// ── Human-readable wording maps ──

const POSITION_HUMAN = {
  confirmed_present: 'Il etait present',
  confirmed_absent: 'Il etait absent',
  confirmed_late_penalized: 'Il etait en retard',
};

const OUTCOME_OPTIONS = [
  { value: 'on_time', label: 'Present', subtitle: 'Aucune penalite', icon: CheckCircle, color: 'emerald' },
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
  const [showTechDetails, setShowTechDetails] = useState(false);
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
  const ps = td.proof_summary || {};
  const sa = dispute.system_analysis || {};
  const ds = dispute.declaration_summary || {};
  const hasDeclarants = (ds.declarants || []).length > 0;
  const hasEvidence = (dispute.evidence_submissions || []).length > 0;
  const hasWitnessContent = hasDeclarants || hasEvidence;

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

        {/* Tech details accordion */}
        <div className="mb-5">
          <button
            onClick={() => setShowTechDetails(!showTechDetails)}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 transition-colors"
            data-testid="toggle-tech-details"
          >
            <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showTechDetails ? 'rotate-180' : ''}`} />
            Voir le detail technique
          </button>
          {showTechDetails && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2" data-testid="tech-details-grid">
              <TechItem label="Connexion app" value={ps.nlyt_proof_score != null ? `${ps.nlyt_proof_score} pts` : 'Aucune'} active={ps.nlyt_proof_score != null} />
              <TechItem label="Visioconference" value={ps.video_api_outcome ? `${ps.video_provider}` : 'Aucune'} active={!!ps.video_api_outcome} />
              <TechItem label="Localisation GPS" value={ps.gps_evidence ? 'Confirmee' : 'Aucune'} active={ps.gps_evidence} />
              <TechItem label="Check-in QR" value={ps.qr_evidence ? 'Valide' : 'Aucun'} active={ps.qr_evidence} />
            </div>
          )}
        </div>

        {/* ════════ ZONE 2 — Ce que disent les parties ════════ */}
        <section className="rounded-xl border border-slate-200 bg-white p-5 mb-5" data-testid="positions-bloc">
          <h3 className="text-sm font-bold text-slate-700 mb-4">Ce que disent les parties</h3>
          <div className="flex items-stretch gap-3">
            <PositionCard
              role="Organisateur"
              name={dispute.organizer_name}
              position={dispute.organizer_position}
              positionAt={dispute.organizer_position_at}
            />
            <div className="flex items-center px-2">
              <span className="text-xs font-bold text-slate-300">VS</span>
            </div>
            <PositionCard
              role="Participant"
              name={dispute.target_name}
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
                    {(ds.declarants || []).map((dec, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm py-1.5">
                        {dec.declared_status === 'absent' ? (
                          <UserX className="w-4 h-4 text-red-500" />
                        ) : (
                          <UserCheck className="w-4 h-4 text-emerald-500" />
                        )}
                        <span className="text-slate-700 font-medium">{dec.first_name || 'Participant'}</span>
                        <span className="text-slate-400">dit :</span>
                        <span className={`font-medium ${dec.declared_status === 'absent' ? 'text-red-600' : 'text-emerald-600'}`}>
                          {dec.declared_status === 'absent' ? 'Il etait absent' : 'Il etait present'}
                        </span>
                      </div>
                    ))}
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

        {/* ════════ ZONE 4 — Votre decision ════════ */}
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

function PositionCard({ role, name, position, positionAt }) {
  const isPresent = position === 'confirmed_present';
  const isAbsent = position === 'confirmed_absent';
  const colors = isPresent ? 'bg-emerald-50 border-emerald-200' : isAbsent ? 'bg-red-50 border-red-200' : 'bg-slate-50 border-slate-200';
  const textColor = isPresent ? 'text-emerald-700' : isAbsent ? 'text-red-700' : 'text-amber-700';

  return (
    <div className={`flex-1 rounded-lg border p-4 ${colors}`} data-testid={`position-${role.toLowerCase()}`}>
      <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">{role}</p>
      <p className="text-sm font-medium text-slate-800 mt-1">{name || '—'}</p>
      <p className="text-xs text-slate-400 mt-0.5">dit :</p>
      <p className={`text-sm font-bold mt-0.5 ${textColor}`}>
        {POSITION_HUMAN[position] || 'Position non soumise'}
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

// ── Helpers ──

function TechItem({ label, value, active }) {
  return (
    <div className={`rounded-lg px-3 py-2 border ${active ? 'bg-emerald-50 border-emerald-200' : 'bg-slate-50 border-slate-100'}`}>
      <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">{label}</p>
      <p className={`text-xs font-medium mt-0.5 ${active ? 'text-emerald-700' : 'text-slate-400'}`}>{value}</p>
    </div>
  );
}

function buildDisagreementPhrase(dispute) {
  const org = dispute.organizer_position;
  const par = dispute.participant_position;
  if (!org || !par) return null;
  if (org === par) return 'Les deux parties sont d\'accord.';
  const orgSays = org === 'confirmed_absent' ? 'absent' : org === 'confirmed_present' ? 'present' : 'en retard';
  const parSays = par === 'confirmed_present' ? 'present' : par === 'confirmed_absent' ? 'absent' : 'en retard';
  return `Desaccord : l'organisateur estime que le participant etait ${orgSays}, le participant affirme qu'il etait ${parSays}.`;
}
