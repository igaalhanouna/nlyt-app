import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, AlertTriangle, CheckCircle, Clock, Upload, FileText, Loader2, Scale, MessageSquare, ShieldCheck, ShieldAlert } from 'lucide-react';
import api from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';

const STATUS_LABELS = {
  opened: { label: 'Ouvert', color: 'bg-blue-100 text-blue-700', icon: Scale },
  awaiting_evidence: { label: 'En attente de preuves', color: 'bg-amber-100 text-amber-700', icon: Clock },
  escalated: { label: 'Escaladé à la plateforme', color: 'bg-red-100 text-red-700', icon: AlertTriangle },
  resolved: { label: 'Résolu', color: 'bg-emerald-100 text-emerald-700', icon: CheckCircle },
};

const REASON_LABELS = {
  contestant_contradiction: 'Le participant concerné conteste les déclarations',
  tiers_disagreement: 'Désaccord entre participants',
  coherence_failure: 'Incohérence globale des déclarations',
  collusion_signal: 'Suspicion de conflit d\'intérêt',
  tech_signal_contradiction: 'Signal technique contradictoire',
  small_group_escalation: 'Groupe trop restreint pour le vote déclaratif',
};

export default function DisputeDetailPage() {
  const { id: disputeId } = useParams();
  const navigate = useNavigate();
  const [dispute, setDispute] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showEvidenceForm, setShowEvidenceForm] = useState(false);
  const [evidenceText, setEvidenceText] = useState('');
  const [submittingEvidence, setSubmittingEvidence] = useState(false);
  const [decidingAction, setDecidingAction] = useState(null); // 'concede' | 'maintain' | null
  const [showConfirmDecision, setShowConfirmDecision] = useState(null); // 'concede' | 'maintain' | null

  const fetchDispute = useCallback(async () => {
    try {
      const res = await api.get(`/api/disputes/${disputeId}`);
      setDispute(res.data);
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

  const handleDecision = async (action) => {
    if (decidingAction) return;
    setDecidingAction(action);
    try {
      await api.post(`/api/disputes/${disputeId}/${action}`);
      setShowConfirmDecision(null);
      fetchDispute();
    } catch (err) {
      console.error(`Error ${action} dispute:`, err);
    } finally {
      setDecidingAction(null);
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
          <button onClick={() => navigate('/litiges')} className="mt-4 text-sm text-blue-600 underline">Retour</button>
        </div>
      </div>
    );
  }

  const s = STATUS_LABELS[dispute.status] || STATUS_LABELS.opened;
  const StatusIcon = s.icon;
  const deadline = dispute.deadline ? new Date(dispute.deadline) : null;
  const summary = dispute.declaration_summary || {};
  const resolution = dispute.resolution || {};

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
          {/* Header */}
          <div className="p-5 border-b border-slate-100">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h1 className="text-lg font-semibold text-slate-800" data-testid="dispute-title">
                  Litige — {dispute.appointment_title || 'Rendez-vous'}
                </h1>
                {dispute.appointment_date && (
                  <p className="text-xs text-slate-400 mt-1">
                    {new Date(dispute.appointment_date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
                  </p>
                )}
              </div>
              <span className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${s.color}`}>
                <StatusIcon className="w-3.5 h-3.5" />
                {s.label}
              </span>
            </div>
            {deadline && dispute.status !== 'resolved' && (
              <div className="flex items-center gap-1.5 mt-3 text-xs text-slate-400">
                <Clock className="w-3.5 h-3.5" />
                Deadline : {deadline.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
              </div>
            )}
          </div>

          {/* Disagreement summary */}
          <div className="p-5 border-b border-slate-100" data-testid="dispute-summary">
            <h2 className="text-sm font-medium text-slate-700 mb-3">Point de désaccord</h2>
            <div className="bg-slate-50 rounded-lg p-4 space-y-2">
              <p className="text-sm text-slate-600">
                Participant concerné : <span className="font-medium">{dispute.target_name || 'Participant'}</span>
              </p>
              <div className="flex flex-wrap gap-3 text-xs">
                {summary.declared_absent_count > 0 && (
                  <span className="flex items-center gap-1 text-red-600">
                    {summary.declared_absent_count} participant(s) l'ont déclaré absent
                  </span>
                )}
                {summary.declared_present_count > 0 && (
                  <span className="flex items-center gap-1 text-emerald-600">
                    {summary.declared_present_count} participant(s) l'ont déclaré présent
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400">
                Preuve technique : {summary.has_tech_evidence ? 'signal détecté' : 'aucune'}
              </p>
              {dispute.opened_reason && (
                <p className="text-xs text-slate-400 mt-1">
                  Raison : {REASON_LABELS[dispute.opened_reason] || dispute.opened_reason}
                </p>
              )}
            </div>
          </div>

          {/* Evidence submissions */}
          <div className="p-5 border-b border-slate-100">
            <h2 className="text-sm font-medium text-slate-700 mb-3">Preuves complémentaires</h2>

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
              <p className="text-xs text-slate-400 mb-4">Aucune preuve soumise pour le moment</p>
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
                    Soumettre une preuve complémentaire
                  </button>
                )}
              </>
            )}
          </div>

          {/* Organizer Decision Block — Phase 2 */}
          {dispute.can_decide && (
            <div className="p-5 border-b border-slate-100" data-testid="dispute-decision-block">
              <h2 className="text-sm font-medium text-slate-700 mb-2">Votre décision</h2>
              <p className="text-xs text-slate-500 mb-4">
                En tant qu'organisateur, vous pouvez libérer la garantie du participant (aucune pénalité)
                ou maintenir votre position (escalade à la plateforme pour arbitrage).
              </p>

              {showConfirmDecision === null ? (
                <div className="flex flex-col sm:flex-row gap-3">
                  <button
                    onClick={() => setShowConfirmDecision('concede')}
                    className="flex items-center justify-center gap-2 px-4 py-2.5 border-2 border-emerald-200 bg-emerald-50 text-emerald-700 text-sm font-medium rounded-lg hover:bg-emerald-100 transition-colors"
                    data-testid="concede-btn"
                  >
                    <ShieldCheck className="w-4 h-4" />
                    Je libère la garantie
                  </button>
                  <button
                    onClick={() => setShowConfirmDecision('maintain')}
                    className="flex items-center justify-center gap-2 px-4 py-2.5 border-2 border-red-200 bg-red-50 text-red-700 text-sm font-medium rounded-lg hover:bg-red-100 transition-colors"
                    data-testid="maintain-btn"
                  >
                    <ShieldAlert className="w-4 h-4" />
                    Je maintiens ma position
                  </button>
                </div>
              ) : (
                <div className="bg-slate-50 rounded-lg p-4 space-y-3" data-testid="confirm-decision-block">
                  <p className="text-sm text-slate-700 font-medium">
                    {showConfirmDecision === 'concede'
                      ? 'Confirmer la libération de la garantie ?'
                      : 'Confirmer l\'escalade à la plateforme ?'}
                  </p>
                  <p className="text-xs text-slate-500">
                    {showConfirmDecision === 'concede'
                      ? 'Le participant ne subira aucune pénalité financière. Cette action est irréversible.'
                      : 'Un arbitre de la plateforme examinera le dossier et prendra une décision finale. Cette action est irréversible.'}
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleDecision(showConfirmDecision)}
                      disabled={!!decidingAction}
                      className={`flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-lg transition-colors disabled:opacity-40 ${
                        showConfirmDecision === 'concede'
                          ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                          : 'bg-red-600 text-white hover:bg-red-700'
                      }`}
                      data-testid="confirm-decision-btn"
                    >
                      {decidingAction ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                      Confirmer
                    </button>
                    <button
                      onClick={() => setShowConfirmDecision(null)}
                      disabled={!!decidingAction}
                      className="px-4 py-2 text-xs text-slate-500 hover:text-slate-700"
                      data-testid="cancel-decision-btn"
                    >
                      Annuler
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Decision taken (non-resolved) */}
          {dispute.decision && dispute.status !== 'resolved' && (
            <div className="p-5 border-b border-slate-100" data-testid="dispute-decision-taken">
              <h2 className="text-sm font-medium text-slate-700 mb-3">Décision prise</h2>
              <div className={`rounded-lg p-4 ${
                dispute.decision === 'conceded'
                  ? 'bg-emerald-50 border border-emerald-200'
                  : 'bg-amber-50 border border-amber-200'
              }`}>
                <p className="text-sm font-medium">
                  {dispute.decision === 'conceded'
                    ? 'Garantie libérée — aucune pénalité'
                    : 'Position maintenue — en attente d\'arbitrage plateforme'}
                </p>
                {dispute.decision_at && (
                  <p className="text-xs mt-1 opacity-70">
                    {new Date(dispute.decision_at).toLocaleDateString('fr-FR', {
                      day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit'
                    })}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Resolution (if resolved) */}
          {dispute.status === 'resolved' && resolution.resolved_at && (
            <div className="p-5" data-testid="dispute-resolution">
              <h2 className="text-sm font-medium text-slate-700 mb-3">Résolution</h2>
              <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 space-y-2">
                <p className="text-sm text-emerald-800">
                  Résultat : <span className="font-medium">{resolution.final_outcome}</span>
                </p>
                <p className="text-xs text-emerald-600">
                  Décidé par : {resolution.resolved_by === 'platform' ? 'Plateforme' : resolution.resolved_by === 'organizer_concession' ? 'Décision organisateur' : 'Système'}
                </p>
                {resolution.resolution_note && (
                  <p className="text-xs text-emerald-600 italic">"{resolution.resolution_note}"</p>
                )}
              </div>
            </div>
          )}
        </div>

        <p className="text-xs text-slate-400 text-center mt-4">
          Les déclarations individuelles restent confidentielles.
        </p>
      </div>
    </div>
  );
}
