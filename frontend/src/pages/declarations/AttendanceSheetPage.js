import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Clock, CheckCircle, AlertTriangle, HelpCircle, Send, Loader2 } from 'lucide-react';
import api from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';

const STATUS_OPTIONS = [
  { value: 'present_on_time', label: "Présent(e) à l'heure", color: 'border-emerald-400 bg-emerald-50 text-emerald-800' },
  { value: 'present_late', label: 'Présent(e) en retard', color: 'border-amber-400 bg-amber-50 text-amber-800' },
  { value: 'absent', label: 'Absent(e)', color: 'border-red-400 bg-red-50 text-red-800' },
  { value: 'unknown', label: 'Je ne sais pas', color: 'border-slate-300 bg-slate-50 text-slate-600' },
];

export default function AttendanceSheetPage() {
  const { id: appointmentId } = useParams();
  const navigate = useNavigate();
  const [sheet, setSheet] = useState(null);
  const [sheetStatus, setSheetStatus] = useState(null);
  const [selections, setSelections] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [submitted, setSubmitted] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [sheetRes, statusRes] = await Promise.all([
        api.get(`/api/attendance-sheets/${appointmentId}`),
        api.get(`/api/attendance-sheets/${appointmentId}/status`),
      ]);
      setSheet(sheetRes.data);
      setSheetStatus(statusRes.data);
      if (sheetRes.data.status === 'submitted') {
        setSubmitted(true);
        const existing = {};
        (sheetRes.data.declarations || []).forEach(d => {
          existing[d.target_participant_id] = d.declared_status;
        });
        setSelections(existing);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors du chargement');
    } finally {
      setLoading(false);
    }
  }, [appointmentId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSelect = (targetPid, status) => {
    if (submitted) return;
    setSelections(prev => ({ ...prev, [targetPid]: status }));
  };

  const allSelected = sheet?.declarations?.every(d => selections[d.target_participant_id]);

  const handleSubmit = async () => {
    if (!allSelected || submitting || submitted) return;
    setSubmitting(true);
    try {
      const declarations = sheet.declarations.map(d => ({
        target_participant_id: d.target_participant_id,
        declared_status: selections[d.target_participant_id],
      }));
      await api.post(`/api/attendance-sheets/${appointmentId}/submit`, { declarations });
      setSubmitted(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de la soumission');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error && !sheet) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <div className="max-w-lg mx-auto bg-white rounded-xl border p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-amber-500 mx-auto mb-3" />
          <p className="text-slate-600">{error}</p>
          <button onClick={() => navigate(-1)} className="mt-4 text-sm text-blue-600 underline">Retour</button>
        </div>
      </div>
    );
  }

  const deadline = sheetStatus?.deadline ? new Date(sheetStatus.deadline) : null;
  const deadlineStr = deadline ? deadline.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';

  return (
    <div className="min-h-screen bg-slate-50" data-testid="attendance-sheet-page">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Confirmer les présences' },
      ]} />
      <div className="max-w-2xl mx-auto p-4 sm:p-6">

        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-100">
            <h1 className="text-lg font-semibold text-slate-800" data-testid="sheet-title">
              Confirmer les présences
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Le système n'a pas pu vérifier automatiquement la présence de certains participants.
              Aidez-nous en déclarant ce que vous avez observé.
            </p>
            {deadline && (
              <div className="flex items-center gap-1.5 mt-3 text-xs text-slate-400">
                <Clock className="w-3.5 h-3.5" />
                <span>Deadline : {deadlineStr}</span>
              </div>
            )}
            {sheetStatus && (
              <div className="text-xs text-slate-400 mt-1">
                {sheetStatus.submitted_sheets}/{sheetStatus.total_sheets} participants ont répondu
              </div>
            )}
          </div>

          {submitted ? (
            <div className="p-8 text-center" data-testid="sheet-submitted-state">
              <CheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-3" />
              <h2 className="text-base font-medium text-slate-700">Observations enregistrées</h2>
              <p className="text-sm text-slate-500 mt-2">
                Le résultat sera communiqué sous 48h.<br />
                Vos réponses restent confidentielles.
              </p>
            </div>
          ) : (
            <div className="p-5 space-y-6">
              {sheet?.declarations?.map((d) => (
                <div key={d.target_participant_id} className="space-y-2" data-testid={`declaration-${d.target_participant_id}`}>
                  <p className="text-sm font-medium text-slate-700">
                    {d.target_name || d.target_participant_id}
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {STATUS_OPTIONS.map((opt) => {
                      const selected = selections[d.target_participant_id] === opt.value;
                      return (
                        <button
                          key={opt.value}
                          onClick={() => handleSelect(d.target_participant_id, opt.value)}
                          className={`px-3 py-2 rounded-lg border text-sm text-left transition-all ${
                            selected ? opt.color + ' border-2 font-medium' : 'border-slate-200 text-slate-500 hover:border-slate-300'
                          }`}
                          data-testid={`select-${d.target_participant_id}-${opt.value}`}
                        >
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}

              <div className="pt-2 border-t border-slate-100">
                <div className="flex items-start gap-2 mb-4">
                  <HelpCircle className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-slate-400">
                    Vos réponses restent confidentielles jusqu'à la clôture du processus.
                    Les autres participants ne verront pas vos réponses individuelles.
                  </p>
                </div>

                {error && <p className="text-sm text-red-500 mb-3">{error}</p>}

                <button
                  onClick={handleSubmit}
                  disabled={!allSelected || submitting}
                  className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-slate-800 text-white text-sm font-medium hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  data-testid="submit-sheet-btn"
                >
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  Soumettre mes observations
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
