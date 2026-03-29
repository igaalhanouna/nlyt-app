import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { AlertTriangle, CheckCircle, Clock, Upload, FileText, Loader2, Scale, MessageSquare, UserCheck, UserX, Timer, MapPin, Video, Calendar, ArrowRight } from 'lucide-react';
import api from '../../services/api';
import { notificationAPI } from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';
import { formatDateTimeCompactFr } from '../../utils/dateFormat';

const STATUS_CONFIG = {
  waiting_both: { label: 'En attente de réponse', color: 'bg-amber-100 text-amber-700', icon: Clock },
  waiting_other: { label: 'En attente de réponse', color: 'bg-amber-100 text-amber-700', icon: Clock },
  arbitration: { label: 'En cours d\'arbitrage', color: 'bg-blue-100 text-blue-700', icon: Scale },
  resolved: { label: 'Résolu', color: 'bg-emerald-100 text-emerald-700', icon: CheckCircle },
};

const REASON_LABELS = {
  contestant_contradiction: 'Le participant concerné conteste les déclarations',
  tiers_disagreement: 'Les déclarations des participants se contredisent',
  coherence_failure: 'Incohérence globale des déclarations',
  collusion_signal: 'Suspicion de conflit d\'intérêt',
  tech_signal_contradiction: 'Signal technique contradictoire',
  no_declarations_received: 'Aucune déclaration reçue dans les délais',
  small_group_disagreement: 'Les déclarations du groupe se contredisent',
};

const DECLARATION_LABELS = {
  present_on_time: 'présent(e)',
  present_late: 'présent(e) (en retard)',
  absent: 'absent(e)',
  unknown: 'ne sait pas',
};

export default function DisputeDetailPage() {
  const { id: disputeId } = useParams();
  const navigate = useNavigate();
  const [dispute, setDispute] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showEvidenceForm, setShowEvidenceForm] = useState(false);
  const [evidenceText, setEvidenceText] = useState('');
  const [submittingEvidence, setSubmittingEvidence] = useState(false);
  const [submittingPosition, setSubmittingPosition] = useState(null);
  const [confirmPosition, setConfirmPosition] = useState(null);

  const fetchDispute = useCallback(async () => {
    try {
      const res = await api.get(`/api/disputes/${disputeId}`);
      setDispute(res.data);
      // Mark dispute notification as read
      notificationAPI.markRead('dispute_update', disputeId).catch(() => {});
    } catch (err) {
      console.error('Error fetching dispute:', err);
    } finally {
      setLoading(false);
    }
  }, [disputeId]);

  useEffect(() => { fetchDispute(); }, [fetchDispute]);

  const handleSubmitEvidence = async () => {
    if (!evidenceText.trim() || submittingEvidence) return;
    setSubmittingEvidence(true);
    try {
      await api.post(`/api/disputes/${disputeId}/evidence`, {
        evidence_type: 'text_statement',
        text_content: evidenceText.trim(),
      });
      setEvidenceText('');
      setShowEvidenceForm(false);
      fetchDispute();
    } catch (err) {
      console.error('Error submitting evidence:', err);
    } finally {
      setSubmittingEvidence(false);
    }
  };

  const handleSubmitPosition = async (position) => {
    if (submittingPosition) return;
    setSubmittingPosition(position);
    try {
      await api.post(`/api/disputes/${disputeId}/position`, { position });
      setConfirmPosition(null);
      fetchDispute();
    } catch (err) {
      console.error('Error submitting position:', err);
    } finally {
      setSubmittingPosition(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (!dispute) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <div className="max-w-lg mx-auto bg-white rounded-xl border p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-amber-500 mx-auto mb-3" />
          <p className="text-slate-600">Litige introuvable</p>
          <button onClick={() => navigate('/litiges')} className="mt-4 text-sm text-blue-600 underline" data-testid="back-to-list">Retour</button>
        </div>
      </div>
    );
  }

  const s = STATUS_CONFIG[dispute.display_state] || STATUS_CONFIG.waiting_both;
  const StatusIcon = s.icon;
  const deadline = dispute.deadline ? new Date(dispute.deadline) : null;
  const summary = dispute.declaration_summary || {};
  const resolution = dispute.resolution || {};
  const isTarget = dispute.is_target === true;
  const targetFirstName = dispute.target_name?.split(' ')[0] || 'Le participant';

  return (
    <div className="min-h-screen bg-slate-50" data-testid="dispute-detail-page">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Litiges', href: '/litiges' },
        { label: dispute.appointment_title || 'Litige' },
      ]} />
      <div className="max-w-2xl mx-auto p-4 sm:p-6">

        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">

          {/* ─── BLOC 1: Titre RDV + statut + contexte ─── */}
          <div className="p-5 border-b border-slate-100">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h1 className="text-lg font-semibold text-slate-800" data-testid="dispute-title">
                  {dispute.appointment_title || 'Rendez-vous'}
                </h1>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1.5">
                  {dispute.appointment_date && (
                    <span className="flex items-center gap-1 text-xs text-slate-500">
                      <Calendar className="w-3 h-3 text-slate-400" />
                      {formatDateTimeCompactFr(dispute.appointment_date)}
                    </span>
                  )}
                  {dispute.appointment_duration_minutes > 0 && (
                    <span className="flex items-center gap-1 text-xs text-slate-500">
                      <Clock className="w-3 h-3 text-slate-400" />
                      {dispute.appointment_duration_minutes} min
                    </span>
                  )}
                  {dispute.appointment_type && (
                    <span className="flex items-center gap-1 text-xs text-slate-500">
                      {dispute.appointment_type === 'physical'
                        ? <><MapPin className="w-3 h-3 text-slate-400" /> {dispute.appointment_location || 'Physique'}</>
                        : <><Video className="w-3 h-3 text-slate-400" /> {dispute.appointment_meeting_provider || 'Visioconference'}</>
                      }
                    </span>
                  )}
                </div>
              </div>
              <span className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium whitespace-nowrap ${s.color}`} data-testid="dispute-status-badge">
                <StatusIcon className="w-3.5 h-3.5" />
                {s.label}
              </span>
            </div>
            {dispute.appointment_id && (
              <Link
                to={`/appointments/${dispute.appointment_id}`}
                className="inline-flex items-center gap-1 mt-3 text-xs text-blue-600 hover:text-blue-800 font-medium transition-colors"
                data-testid="dispute-detail-view-appointment-link"
              >
                Voir le rendez-vous
                <ArrowRight className="w-3 h-3" />
              </Link>
            )}
          </div>

          {/* ─── BLOC 2: Ce qui s'est passé ─── */}
          <div className="p-5 border-b border-slate-100" data-testid="dispute-summary">
            <h2 className="text-sm font-semibold text-slate-700 mb-3">Ce qui s'est passé</h2>
            <p className="text-sm text-slate-600 mb-3">
              {isTarget
                ? 'Votre présence n\'a pas pu être vérifiée automatiquement. Les déclarations des participants se contredisent.'
                : `La présence de ${targetFirstName} n'a pas pu être vérifiée automatiquement. Les déclarations des participants se contredisent.`
              }
            </p>
            <DeclarationSummaryBlock summary={summary} isTarget={isTarget} targetFirstName={targetFirstName} />
          </div>

          {/* ─── BLOC 3: Votre déclaration ─── */}
          <div className="p-5 border-b border-slate-100" data-testid="dispute-my-declaration">
            <h2 className="text-sm font-semibold text-slate-700 mb-2">Votre déclaration sur les présences</h2>
            {dispute.my_declaration ? (
              <p className="text-sm text-slate-600">
                {isTarget
                  ? `Vous avez déclaré que vous étiez ${DECLARATION_LABELS[dispute.my_declaration] || dispute.my_declaration}.`
                  : `Vous avez déclaré ${targetFirstName} ${DECLARATION_LABELS[dispute.my_declaration] || dispute.my_declaration}.`
                }
              </p>
            ) : (
              <p className="text-sm text-slate-500">
                {isTarget
                  ? 'Aucune déclaration enregistrée de votre part.'
                  : `Vous n'avez pas soumis de déclaration pour ${targetFirstName}.`
                }
              </p>
            )}
          </div>

          {/* ─── BLOC 4: Votre position (décision) ─── */}
          {dispute.can_submit_position && (
            <div className="p-5 border-b border-slate-100" data-testid="dispute-position-block">
              <h2 className="text-sm font-semibold text-slate-700 mb-2">Votre position sur le litige</h2>
              <p className="text-xs text-slate-500 mb-4">
                Pour résoudre ce désaccord, confirmez votre position sur ce litige. Si les positions divergent, un arbitre neutre de la plateforme tranchera.
              </p>

              {confirmPosition === null ? (
                <div className="flex flex-col gap-2.5">
                  <button
                    onClick={() => setConfirmPosition('confirmed_present')}
                    className="flex items-center gap-2.5 px-4 py-3 border-2 border-emerald-200 bg-emerald-50 text-emerald-700 text-sm font-medium rounded-lg hover:bg-emerald-100 transition-colors text-left"
                    data-testid="position-present-btn"
                  >
                    <UserCheck className="w-4.5 h-4.5 flex-shrink-0" />
                    {isTarget ? 'Je confirme ma présence' : `Je confirme la présence de ${targetFirstName}`}
                  </button>
                  <button
                    onClick={() => setConfirmPosition('confirmed_absent')}
                    className="flex items-center gap-2.5 px-4 py-3 border-2 border-red-200 bg-red-50 text-red-700 text-sm font-medium rounded-lg hover:bg-red-100 transition-colors text-left"
                    data-testid="position-absent-btn"
                  >
                    <UserX className="w-4.5 h-4.5 flex-shrink-0" />
                    {isTarget ? 'Je confirme mon absence' : `Je confirme l'absence de ${targetFirstName}`}
                  </button>
                  <button
                    onClick={() => setConfirmPosition('confirmed_late_penalized')}
                    className="flex items-center gap-2.5 px-4 py-3 border-2 border-orange-200 bg-orange-50 text-orange-700 text-sm font-medium rounded-lg hover:bg-orange-100 transition-colors text-left"
                    data-testid="position-late-btn"
                  >
                    <Timer className="w-4.5 h-4.5 flex-shrink-0" />
                    {isTarget ? 'Je confirme mon retard au-delà de la tolérance' : `Je confirme le retard pénalisable de ${targetFirstName}`}
                  </button>
                </div>
              ) : (
                <ConfirmPositionBlock
                  position={confirmPosition}
                  isTarget={isTarget}
                  targetFirstName={targetFirstName}
                  onConfirm={() => handleSubmitPosition(confirmPosition)}
                  onCancel={() => setConfirmPosition(null)}
                  submitting={submittingPosition}
                />
              )}
            </div>
          )}

          {/* ─── Position déjà soumise ─── */}
          {dispute.my_position && !dispute.is_resolved && (
            <div className="p-5 border-b border-slate-100" data-testid="dispute-position-submitted">
              <h2 className="text-sm font-semibold text-slate-700 mb-2">Votre position sur le litige</h2>
              <div className="bg-slate-50 rounded-lg p-4">
                <p className="text-sm text-slate-600">
                  <PositionLabel position={dispute.my_position} isTarget={isTarget} targetFirstName={targetFirstName} />
                </p>
                <DisputeStateMessage dispute={dispute} />
              </div>
            </div>
          )}

          {/* ─── BLOC 5: Deadline ─── */}
          {deadline && !dispute.is_resolved && dispute.status !== 'escalated' && (
            <div className="p-5 border-b border-slate-100" data-testid="dispute-deadline-block">
              <div className="flex items-start gap-2.5">
                <Clock className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm text-slate-600">
                    Délai de réponse : {deadline.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    Passé ce délai, si les deux parties ne se sont pas exprimées, le dossier sera automatiquement transmis à un arbitre neutre.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* ─── BLOC 6: Éléments complémentaires ─── */}
          <div className="p-5 border-b border-slate-100" data-testid="dispute-evidence-block">
            <h2 className="text-sm font-semibold text-slate-700 mb-1">Éléments complémentaires</h2>
            <p className="text-xs text-slate-400 mb-3">Transmis uniquement à l'arbitre en cas d'escalade</p>

            {dispute.evidence_submissions?.length > 0 ? (
              <div className="space-y-2 mb-4">
                {dispute.evidence_submissions.map((sub) => (
                  <div key={sub.submission_id} className="flex items-center gap-2 text-xs text-slate-500 bg-slate-50 rounded-lg p-3">
                    <FileText className="w-3.5 h-3.5 text-slate-400" />
                    <span>{sub.evidence_type === 'text_statement' ? 'Déclaration écrite' : sub.evidence_type}</span>
                    <span className="text-slate-300">·</span>
                    <span>{sub.is_mine ? 'Vous' : 'Un participant'}</span>
                    <span className="text-slate-300">·</span>
                    <span>{new Date(sub.submitted_at).toLocaleDateString('fr-FR')}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 mb-4">Aucun élément soumis</p>
            )}

            {dispute.can_submit_evidence && (
              <>
                {showEvidenceForm ? (
                  <div className="space-y-3">
                    <textarea
                      value={evidenceText}
                      onChange={(e) => setEvidenceText(e.target.value)}
                      placeholder="Décrivez ce que vous avez observé..."
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-200"
                      rows={3}
                      data-testid="evidence-textarea"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={handleSubmitEvidence}
                        disabled={!evidenceText.trim() || submittingEvidence}
                        className="flex items-center gap-1.5 px-4 py-2 bg-slate-800 text-white text-xs font-medium rounded-lg hover:bg-slate-700 disabled:opacity-40 transition-colors"
                        data-testid="submit-evidence-btn"
                      >
                        {submittingEvidence ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                        Soumettre
                      </button>
                      <button
                        onClick={() => { setShowEvidenceForm(false); setEvidenceText(''); }}
                        className="px-4 py-2 text-xs text-slate-500 hover:text-slate-700"
                      >
                        Annuler
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => setShowEvidenceForm(true)}
                    className="flex items-center gap-1.5 px-4 py-2 border border-slate-200 rounded-lg text-xs text-slate-600 hover:border-slate-300 transition-colors"
                    data-testid="show-evidence-form-btn"
                  >
                    <MessageSquare className="w-3.5 h-3.5" />
                    Ajouter un élément
                  </button>
                )}
              </>
            )}
          </div>

          {/* ─── Résolution ─── */}
          {dispute.is_resolved && resolution.resolved_at && (
            <div className="p-5" data-testid="dispute-resolution">
              <h2 className="text-sm font-semibold text-slate-700 mb-3">Résolution</h2>
              <div className={`rounded-lg p-4 space-y-2 ${
                resolution.final_outcome === 'no_show' || resolution.final_outcome === 'late_penalized'
                  ? 'bg-red-50 border border-red-200'
                  : 'bg-emerald-50 border border-emerald-200'
              }`}>
                <p className="text-sm font-medium">
                  <ResolutionOutcomeLabel outcome={resolution.final_outcome} />
                </p>
                <p className="text-xs opacity-70">
                  {resolution.resolved_by === 'mutual_agreement'
                    ? 'Accord mutuel des deux parties'
                    : resolution.resolved_by === 'platform'
                    ? 'Décision de la plateforme'
                    : 'Résolution automatique'
                  }
                </p>
                {resolution.resolution_note && (
                  <p className="text-xs opacity-60 italic">"{resolution.resolution_note}"</p>
                )}
              </div>
            </div>
          )}

          {/* ─── Escalade info ─── */}
          {dispute.status === 'escalated' && !dispute.is_resolved && (
            <div className="p-5" data-testid="dispute-escalated-info">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start gap-2.5">
                  <Scale className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-blue-800">Dossier transmis à un arbitre neutre</p>
                    <p className="text-xs text-blue-600 mt-1">
                      Les positions des deux parties divergent. Un arbitre de la plateforme examinera le dossier et prendra une décision finale.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        <p className="text-xs text-slate-400 text-center mt-4">
          Les déclarations individuelles restent confidentielles. Aucune pénalité ne peut être appliquée sans l'accord explicite des deux parties.
        </p>
      </div>
    </div>
  );
}


const STATUS_DISPLAY = {
  absent: { label: 'absent(e)', color: 'text-red-600 bg-red-50 border-red-100', icon: UserX },
  present_on_time: { label: 'présent(e)', color: 'text-emerald-600 bg-emerald-50 border-emerald-100', icon: UserCheck },
  present_late: { label: 'présent(e) (en retard)', color: 'text-amber-600 bg-amber-50 border-amber-100', icon: Clock },
  unknown: { label: 'ne sait pas', color: 'text-slate-500 bg-slate-50 border-slate-100', icon: AlertTriangle },
};

function formatDeclarantNames(names) {
  if (names.length === 0) return '';
  if (names.length === 1) return names[0];
  if (names.length === 2) return `${names[0]} et ${names[1]}`;
  return `${names[0]}, ${names[1]} et ${names.length - 2} autre${names.length - 2 > 1 ? 's' : ''}`;
}

function DeclarationSummaryBlock({ summary, isTarget, targetFirstName }) {
  const declarants = summary.declarants || [];
  const hasDeclarants = declarants.length > 0;

  // Group by status, using "Vous" for is_me declarants
  const grouped = {};
  declarants.forEach(d => {
    const key = d.declared_status || 'unknown';
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(d.is_me ? 'Vous' : d.first_name);
  });

  return (
    <div className="bg-slate-50 rounded-lg p-4 space-y-3" data-testid="declaration-summary-block">
      {hasDeclarants ? (
        <>
          {/* Phrase résumé par groupe */}
          <div className="space-y-2">
            {Object.entries(grouped).map(([status, names]) => {
              const cfg = STATUS_DISPLAY[status] || STATUS_DISPLAY.unknown;
              const Icon = cfg.icon;
              const namesStr = formatDeclarantNames(names);
              const hasVous = names.includes('Vous');
              const onlyVous = names.length === 1 && hasVous;
              const verb = onlyVous ? 'avez déclaré' : (names.length > 1 ? 'ont déclaré' : 'a déclaré');
              const target = isTarget ? 'que vous étiez' : `que ${targetFirstName} était`;
              return (
                <div key={status} className="flex items-start gap-2 text-xs">
                  <Icon className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${cfg.color.split(' ')[0]}`} />
                  <span className="text-slate-700">
                    <span className="font-medium">{namesStr}</span> {verb} {target} <span className={`font-medium ${cfg.color.split(' ')[0]}`}>{cfg.label}</span>
                  </span>
                </div>
              );
            })}
          </div>

          {/* Liste détaillée individuelle */}
          {declarants.length > 1 && (
            <div className="border-t border-slate-200 pt-2.5 mt-2.5 space-y-1.5">
              {declarants.map((d, i) => {
                const cfg = STATUS_DISPLAY[d.declared_status] || STATUS_DISPLAY.unknown;
                const Icon = cfg.icon;
                const displayName = d.is_me ? 'Vous' : d.first_name;
                return (
                  <div key={i} className={`flex items-center justify-between px-2.5 py-1.5 rounded-md border ${cfg.color}`} data-testid={`declarant-row-${i}`}>
                    <span className="text-xs font-medium">{displayName}</span>
                    <span className="flex items-center gap-1 text-xs">
                      <Icon className="w-3 h-3" />
                      {cfg.label}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </>
      ) : (
        <p className="text-xs text-slate-400">Aucune déclaration de présence reçue</p>
      )}

      {summary.has_tech_evidence && (
        <p className="text-xs text-slate-500">Signal technique détecté</p>
      )}
    </div>
  );
}


function DisputeStateMessage({ dispute }) {
  const state = dispute.display_state;
  const otherName = dispute.other_party_name || 'l\'autre partie';

  if (state === 'arbitration') {
    return (
      <p className="text-xs text-blue-600 mt-2 flex items-center gap-1">
        <Scale className="w-3 h-3" />
        Les positions divergent. Un arbitre neutre examinera le dossier.
      </p>
    );
  }
  if (state === 'waiting_other') {
    if (dispute.my_position) {
      return <p className="text-xs text-amber-600 mt-2">En attente de la réponse de {otherName}.</p>;
    }
    return <p className="text-xs text-amber-600 mt-2">{otherName} a déjà répondu. C'est à votre tour.</p>;
  }
  if (state === 'waiting_both') {
    return <p className="text-xs text-slate-400 mt-2">Aucune des deux parties ne s'est encore exprimée.</p>;
  }
  return null;
}

function DisputeStatusBadge({ status, displayState }) {
  const config = {
    waiting_both: { label: 'En attente', color: 'bg-slate-100 text-slate-600' },
    waiting_other: { label: 'En attente', color: 'bg-amber-50 text-amber-700' },
    arbitration: { label: 'En cours d\'arbitrage', color: 'bg-blue-50 text-blue-700' },
    resolved: { label: 'Résolu', color: 'bg-emerald-50 text-emerald-700' },
  };
  const c = config[displayState] || config.waiting_both;
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${c.color}`} data-testid="dispute-status-badge">
      {c.label}
    </span>
  );
}


function ConfirmPositionBlock({ position, isTarget, targetFirstName, onConfirm, onCancel, submitting }) {
  const configs = {
    confirmed_present: {
      title: isTarget ? 'Vous confirmez votre présence.' : `Vous confirmez la présence de ${targetFirstName}.`,
      detail: 'Si l\'autre partie confirme aussi la présence, la garantie sera libérée. En cas de désaccord, un arbitre tranchera.',
      btnClass: 'bg-emerald-600 text-white hover:bg-emerald-700',
    },
    confirmed_absent: {
      title: isTarget ? 'Vous confirmez votre absence.' : `Vous confirmez l'absence de ${targetFirstName}.`,
      detail: 'Si l\'autre partie confirme aussi l\'absence, la pénalité sera appliquée. En cas de désaccord, un arbitre tranchera.',
      btnClass: 'bg-red-600 text-white hover:bg-red-700',
    },
    confirmed_late_penalized: {
      title: isTarget ? 'Vous confirmez votre retard au-delà de la tolérance.' : `Vous confirmez le retard pénalisable de ${targetFirstName}.`,
      detail: 'Si l\'autre partie confirme aussi le retard pénalisable, la pénalité sera appliquée. En cas de désaccord, un arbitre tranchera.',
      btnClass: 'bg-orange-600 text-white hover:bg-orange-700',
    },
  };
  const c = configs[position];

  return (
    <div className="bg-slate-50 rounded-lg p-4 space-y-3" data-testid="confirm-position-block">
      <p className="text-sm text-slate-700 font-medium">{c.title}</p>
      <p className="text-xs text-slate-500">{c.detail}</p>
      <p className="text-xs text-slate-400">Cette action est irréversible.</p>
      <div className="flex gap-2">
        <button
          onClick={onConfirm}
          disabled={!!submitting}
          className={`flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-lg transition-colors disabled:opacity-40 ${c.btnClass}`}
          data-testid="confirm-position-btn"
        >
          {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
          Confirmer
        </button>
        <button
          onClick={onCancel}
          disabled={!!submitting}
          className="px-4 py-2 text-xs text-slate-500 hover:text-slate-700"
          data-testid="cancel-position-btn"
        >
          Annuler
        </button>
      </div>
    </div>
  );
}


function PositionLabel({ position, isTarget, targetFirstName }) {
  const labels = {
    confirmed_present: isTarget ? 'Vous avez confirmé votre présence.' : `Vous avez confirmé la présence de ${targetFirstName}.`,
    confirmed_absent: isTarget ? 'Vous avez confirmé votre absence.' : `Vous avez confirmé l'absence de ${targetFirstName}.`,
    confirmed_late_penalized: isTarget ? 'Vous avez confirmé votre retard au-delà de la tolérance.' : `Vous avez confirmé le retard pénalisable de ${targetFirstName}.`,
  };
  return <>{labels[position] || position}</>;
}


function ResolutionOutcomeLabel({ outcome }) {
  const labels = {
    on_time: 'Présence confirmée — garantie libérée',
    late: 'Présence confirmée (retard toléré) — garantie libérée',
    waived: 'Garantie libérée — aucune pénalité',
    no_show: 'Absence confirmée — pénalité appliquée',
    late_penalized: 'Retard pénalisable confirmé — pénalité appliquée',
  };
  return <>{labels[outcome] || outcome}</>;
}
