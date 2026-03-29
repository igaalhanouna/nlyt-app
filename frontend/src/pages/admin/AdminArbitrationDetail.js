import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import {
  Shield, XCircle, AlertTriangle, ArrowLeft, Clock, CheckCircle,
  Video, MapPin, Scale, FileWarning, Eye, UserCheck, UserX, Timer,
} from 'lucide-react';

const POSITION_LABELS = {
  confirmed_present: 'Presence confirmee',
  confirmed_absent: 'Absence confirmee',
  confirmed_late_penalized: 'Retard penalisable',
};

const OUTCOME_OPTIONS = [
  { value: 'on_time', label: 'Present (a l\'heure)', icon: CheckCircle, color: 'emerald' },
  { value: 'no_show', label: 'Absent (no-show)', icon: UserX, color: 'red' },
  { value: 'late_penalized', label: 'Retard penalisable', icon: Timer, color: 'amber' },
];

const ANALYSIS_COLORS = {
  high: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-800', icon: 'text-red-500' },
  medium: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-800', icon: 'text-amber-500' },
  low: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-800', icon: 'text-blue-500' },
};

export default function AdminArbitrationDetail() {
  const { disputeId } = useParams();
  const navigate = useNavigate();
  const [dispute, setDispute] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedOutcome, setSelectedOutcome] = useState('');
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await adminAPI.getDisputeForArbitration(disputeId);
        setDispute(res.data);
        // Pre-select suggested outcome if available
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
    if (!note || note.trim().length < 5) { toast.error('Note d\'arbitrage obligatoire (min 5 caracteres)'); return; }

    setSubmitting(true);
    try {
      await adminAPI.resolveDispute(disputeId, {
        final_outcome: selectedOutcome,
        resolution_note: note.trim(),
      });
      toast.success('Litige arbitre avec succes');
      navigate('/admin/arbitration');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Erreur lors de l\'arbitrage');
    } finally {
      setSubmitting(false);
    }
  };

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

  if (!dispute) {
    return (
      <>
        <AppNavbar />
        <div className="max-w-4xl mx-auto px-4 py-8 text-center">
          <p className="text-slate-500">Dossier introuvable</p>
        </div>
      </>
    );
  }

  const td = dispute.tech_dossier || {};
  const ps = td.proof_summary || {};
  const sa = dispute.system_analysis || {};
  const ds = dispute.declaration_summary || {};
  const acfg = ANALYSIS_COLORS[sa.confidence] || ANALYSIS_COLORS.low;

  return (
    <>
      <AppNavbar />
      <div className="max-w-4xl mx-auto px-4 py-8" data-testid="admin-arbitration-detail">
        {/* Back */}
        <button onClick={() => navigate('/admin/arbitration')} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-6" data-testid="back-btn">
          <ArrowLeft className="w-4 h-4" /> Retour a la liste
        </button>

        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <h1 className="text-xl font-bold text-slate-900" data-testid="dispute-title">{dispute.appointment_title || 'Rendez-vous'}</h1>
            <p className="text-sm text-slate-500 mt-0.5 flex items-center gap-2">
              {dispute.appointment_type === 'video' ? (
                <span className="inline-flex items-center gap-1"><Video className="w-3.5 h-3.5" />{dispute.appointment_meeting_provider || 'Visio'}</span>
              ) : (
                <span className="inline-flex items-center gap-1"><MapPin className="w-3.5 h-3.5" />{dispute.appointment_location || 'Physique'}</span>
              )}
              <span>{dispute.appointment_date ? new Date(dispute.appointment_date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}</span>
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Cible : <strong className="text-slate-600">{dispute.target_name}</strong> ({dispute.target_email})
              {dispute.organizer_name && <> — Organisateur : <strong className="text-slate-600">{dispute.organizer_name}</strong></>}
            </p>
          </div>
          {dispute.escalated_days_ago != null && (
            <span className={`flex-shrink-0 inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium ${
              dispute.escalated_days_ago >= 3 ? 'bg-red-100 text-red-700' : dispute.escalated_days_ago >= 1 ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'
            }`}>
              <Clock className="w-3.5 h-3.5" />
              Escalade il y a {dispute.escalated_days_ago}j
            </span>
          )}
        </div>

        {/* ═══ BLOC 1: Verdict rapide — Preuve technologique ═══ */}
        <section className={`rounded-xl border-2 p-5 mb-5 ${td.has_admissible_proof ? 'bg-emerald-50 border-emerald-300' : 'bg-red-50 border-red-300'}`} data-testid="tech-proof-bloc">
          <div className="flex items-center gap-3 mb-3">
            {td.has_admissible_proof ? (
              <Shield className="w-7 h-7 text-emerald-600" />
            ) : (
              <XCircle className="w-7 h-7 text-red-600" />
            )}
            <div>
              <h2 className={`text-lg font-bold ${td.has_admissible_proof ? 'text-emerald-900' : 'text-red-900'}`}>
                {td.has_admissible_proof ? 'Preuve technologique detectee' : 'Absence de preuve technologique detectee'}
              </h2>
              <p className={`text-sm ${td.has_admissible_proof ? 'text-emerald-700' : 'text-red-700'}`}>
                {td.has_admissible_proof
                  ? 'Le systeme a detecte au moins une preuve admissible'
                  : 'Charge de la preuve sur le participant — aucune preuve admissible detectee'}
              </p>
            </div>
          </div>

          {/* Proof details grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
            <ProofItem label="NLYT Proof" value={ps.nlyt_proof_score != null ? `${ps.nlyt_proof_score} pts (${ps.nlyt_proof_level})` : 'Aucune'} active={ps.nlyt_proof_score != null} />
            <ProofItem label="Video API" value={ps.video_api_outcome ? `${ps.video_provider} — ${ps.video_api_outcome}` : 'Aucune'} active={!!ps.video_api_outcome} />
            <ProofItem label="GPS" value={ps.gps_evidence ? 'Dans le rayon' : 'Aucune'} active={ps.gps_evidence} />
            <ProofItem label="QR Code" value={ps.qr_evidence ? 'Valide' : 'Aucun'} active={ps.qr_evidence} />
          </div>
        </section>

        {/* ═══ BLOC 1.5: Analyse systeme ═══ */}
        <section className={`rounded-xl border p-5 mb-5 ${acfg.bg} ${acfg.border}`} data-testid="system-analysis-bloc">
          <div className="flex items-start gap-3">
            <FileWarning className={`w-5 h-5 mt-0.5 flex-shrink-0 ${acfg.icon}`} />
            <div>
              <h3 className={`text-sm font-bold ${acfg.text}`}>
                Analyse systeme — Cas {sa.case || '?'}
                {sa.suggested_outcome && (
                  <span className="ml-2 px-2 py-0.5 rounded text-[11px] font-semibold bg-white/60">
                    {sa.suggested_outcome === 'no_show' ? 'Absent' : sa.suggested_outcome === 'on_time' ? 'Present' : 'Retard'}
                  </span>
                )}
              </h3>
              <p className={`text-sm mt-1 ${acfg.text} opacity-90`}>{sa.reasoning}</p>
            </div>
          </div>
        </section>

        {/* ═══ BLOC 2: Positions des parties ═══ */}
        <section className="rounded-xl border border-slate-200 bg-white p-5 mb-5" data-testid="positions-bloc">
          <h3 className="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
            <Scale className="w-4 h-4" /> Positions des parties
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <PositionCard
              role="Organisateur"
              name={dispute.organizer_name}
              position={dispute.organizer_position}
              positionAt={dispute.organizer_position_at}
            />
            <PositionCard
              role="Participant (cible)"
              name={dispute.target_name}
              position={dispute.participant_position}
              positionAt={dispute.participant_position_at}
            />
          </div>
        </section>

        {/* ═══ BLOC 3: Declarations croisees ═══ */}
        <section className="rounded-xl border border-slate-200 bg-white p-5 mb-5" data-testid="declarations-bloc">
          <h3 className="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
            <Eye className="w-4 h-4" /> Declarations croisees
          </h3>
          <div className="flex items-center gap-4 text-sm mb-3">
            <span className="text-emerald-700 font-medium">{ds.declared_present_count || 0} present</span>
            <span className="text-red-700 font-medium">{ds.declared_absent_count || 0} absent</span>
            <span className="text-slate-400 font-medium">{ds.unknown_count || 0} inconnu</span>
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
                    {dec.declared_status === 'absent' ? 'Absent' : dec.declared_status === 'present_on_time' ? 'Present (a l\'heure)' : 'Present (en retard)'}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400">Aucune declaration de tiers</p>
          )}

          {/* Contradiction signals */}
          {dispute.opened_reason && (
            <div className="mt-3 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg">
              <p className="text-xs font-medium text-amber-700 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5" />
                Signal detecte : {dispute.opened_reason.replace(/_/g, ' ')}
              </p>
            </div>
          )}
        </section>

        {/* ═══ BLOC 4: Preuves complementaires ═══ */}
        {(dispute.evidence_submissions || []).length > 0 && (
          <section className="rounded-xl border border-slate-200 bg-white p-5 mb-5" data-testid="evidence-bloc">
            <h3 className="text-sm font-bold text-slate-700 mb-3">Preuves complementaires soumises ({dispute.evidence_submissions.length})</h3>
            <div className="space-y-2">
              {dispute.evidence_submissions.map((ev, i) => (
                <div key={ev.submission_id || i} className="flex items-start gap-3 text-sm bg-slate-50 rounded-lg p-3 border border-slate-100">
                  <div className="flex-1">
                    <p className="text-xs font-medium text-slate-500">{ev.evidence_type} — {ev.submitted_at ? new Date(ev.submitted_at).toLocaleDateString('fr-FR') : ''}</p>
                    {ev.text_content && <p className="text-sm text-slate-700 mt-1">{ev.text_content}</p>}
                    {ev.content_url && <a href={ev.content_url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 underline mt-1 inline-block">Voir la piece jointe</a>}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ═══ BLOC 5: Action d'arbitrage ═══ */}
        <section className="rounded-xl border-2 border-slate-900 bg-white p-6" data-testid="arbitration-action-bloc">
          <h3 className="text-base font-bold text-slate-900 mb-1 flex items-center gap-2">
            <Scale className="w-5 h-5" /> Arbitrage
          </h3>
          <p className="text-xs text-slate-500 mb-5">Tranchez dans le cadre des regles strictes du systeme. Une note est obligatoire pour la tracabilite.</p>

          {/* Outcome selection */}
          <div className="grid grid-cols-3 gap-3 mb-5" data-testid="outcome-options">
            {OUTCOME_OPTIONS.map((opt) => {
              const Icon = opt.icon;
              const selected = selectedOutcome === opt.value;
              const colors = {
                emerald: selected ? 'border-emerald-500 bg-emerald-50 ring-2 ring-emerald-200' : 'border-slate-200 hover:border-emerald-300',
                red: selected ? 'border-red-500 bg-red-50 ring-2 ring-red-200' : 'border-slate-200 hover:border-red-300',
                amber: selected ? 'border-amber-500 bg-amber-50 ring-2 ring-amber-200' : 'border-slate-200 hover:border-amber-300',
              };
              return (
                <button
                  key={opt.value}
                  onClick={() => setSelectedOutcome(opt.value)}
                  className={`rounded-xl border-2 p-4 text-center transition-all cursor-pointer ${colors[opt.color]}`}
                  data-testid={`outcome-${opt.value}`}
                >
                  <Icon className={`w-6 h-6 mx-auto mb-2 ${selected ? `text-${opt.color}-600` : 'text-slate-400'}`} />
                  <p className={`text-sm font-medium ${selected ? 'text-slate-900' : 'text-slate-600'}`}>{opt.label}</p>
                </button>
              );
            })}
          </div>

          {/* Note */}
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Note d'arbitrage obligatoire — justifiez votre decision..."
            className="w-full border border-slate-300 rounded-lg px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400 resize-none"
            rows={3}
            data-testid="arbitration-note"
          />

          {/* Submit */}
          <div className="flex items-center justify-between mt-5">
            <p className="text-[11px] text-slate-400 max-w-xs">
              Cette decision est definitive et declenchera les consequences financieres associees.
            </p>
            <Button
              onClick={handleResolve}
              disabled={submitting || !selectedOutcome || !note || note.trim().length < 5}
              className="px-6"
              data-testid="submit-arbitration-btn"
            >
              {submitting ? 'Traitement...' : 'Confirmer l\'arbitrage'}
            </Button>
          </div>
        </section>
      </div>
    </>
  );
}

function ProofItem({ label, value, active }) {
  return (
    <div className={`rounded-lg px-3 py-2 border ${active ? 'bg-white border-emerald-200' : 'bg-white/50 border-slate-200'}`} data-testid={`proof-${label.toLowerCase().replace(/\s/g, '-')}`}>
      <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">{label}</p>
      <p className={`text-xs font-medium mt-0.5 ${active ? 'text-emerald-700' : 'text-slate-500'}`}>{value}</p>
    </div>
  );
}

function PositionCard({ role, name, position, positionAt }) {
  const isPresent = position === 'confirmed_present';
  const isAbsent = position === 'confirmed_absent';
  return (
    <div className={`rounded-lg border p-4 ${isPresent ? 'bg-emerald-50 border-emerald-200' : isAbsent ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'}`} data-testid={`position-${role.toLowerCase()}`}>
      <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide mb-1">{role}</p>
      <p className="text-sm font-medium text-slate-800">{name || '—'}</p>
      <p className={`text-sm font-bold mt-1 ${isPresent ? 'text-emerald-700' : isAbsent ? 'text-red-700' : 'text-amber-700'}`}>
        {POSITION_LABELS[position] || 'Non soumise'}
      </p>
      {positionAt && (
        <p className="text-[11px] text-slate-400 mt-1">
          Soumise le {new Date(positionAt).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })}
        </p>
      )}
    </div>
  );
}
