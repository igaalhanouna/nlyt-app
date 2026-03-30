import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import {
  AlertTriangle, CheckCircle, Clock, Send, Loader2,
  HelpCircle, MapPin, Video, Calendar, ArrowRight, UserCheck, UserX, Timer, Eye
} from 'lucide-react';
import api from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';
import { formatDateTimeCompactFr } from '../../utils/dateFormat';

const STATUS_OPTIONS = [
  { value: 'present_on_time', label: "Présent(e) à l'heure", color: 'border-emerald-400 bg-emerald-50 text-emerald-800', icon: UserCheck },
  { value: 'present_late', label: 'Présent(e) en retard', color: 'border-amber-400 bg-amber-50 text-amber-800', icon: Timer },
  { value: 'absent', label: 'Absent(e)', color: 'border-red-400 bg-red-50 text-red-800', icon: UserX },
  { value: 'unknown', label: 'Je ne sais pas', color: 'border-slate-300 bg-slate-50 text-slate-600', icon: HelpCircle },
];

const STATUS_DISPLAY = {
  present_on_time: { label: "Présent(e) à l'heure", color: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: UserCheck },
  present_late: { label: 'Présent(e) en retard', color: 'bg-amber-50 text-amber-700 border-amber-200', icon: Timer },
  absent: { label: 'Absent(e)', color: 'bg-red-50 text-red-700 border-red-200', icon: UserX },
  unknown: { label: 'Je ne sais pas', color: 'bg-slate-50 text-slate-600 border-slate-200', icon: HelpCircle },
};

export default function AttendanceSheetPage() {
  const { id: appointmentId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const cameFromPresences = location.state?.from === 'presences';
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
  const deadlineStr = deadline ? formatDateTimeCompactFr(deadline.toISOString()) : '';
  const isPhysical = sheet?.appointment_type === 'physical';

  return (
    <div className="min-h-screen bg-slate-50" data-testid="attendance-sheet-page">
      <AppNavbar />
      <AppBreadcrumb items={
        cameFromPresences
          ? [{ label: 'Presences', href: '/presences' }, { label: submitted ? 'Ma declaration' : 'Confirmer les presences' }]
          : [{ label: 'Tableau de bord', href: '/dashboard' }, { label: submitted ? 'Ma declaration' : 'Confirmer les presences' }]
      } />
      <div className="max-w-2xl mx-auto p-4 sm:p-6">

        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          {/* Header: appointment context */}
          <div className="p-5 border-b border-slate-100">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h1 className="text-lg font-semibold text-slate-800" data-testid="sheet-title">
                  {submitted ? 'Votre declaration' : 'Confirmer les presences'}
                </h1>
                {sheet?.appointment_title && (
                  <p className="text-sm text-slate-600 mt-0.5 font-medium" data-testid="sheet-appointment-title">
                    {sheet.appointment_title}
                  </p>
                )}
              </div>
              {submitted && (
                <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-600 border border-emerald-200 flex-shrink-0" data-testid="sheet-submitted-badge">
                  <CheckCircle className="w-3.5 h-3.5" />
                  Soumise
                </span>
              )}
            </div>

            {/* Metadata row */}
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2">
              {sheet?.appointment_start_datetime && (
                <span className="flex items-center gap-1 text-xs text-slate-500">
                  <Calendar className="w-3 h-3 text-slate-400" />
                  {formatDateTimeCompactFr(sheet.appointment_start_datetime)}
                </span>
              )}
              {sheet?.appointment_duration_minutes > 0 && (
                <span className="flex items-center gap-1 text-xs text-slate-500">
                  <Clock className="w-3 h-3 text-slate-400" />
                  {sheet.appointment_duration_minutes} min
                </span>
              )}
              {sheet?.appointment_type && (
                <span className="flex items-center gap-1 text-xs text-slate-500">
                  {isPhysical
                    ? <><MapPin className="w-3 h-3 text-slate-400" /> <span className="truncate max-w-[200px]">{sheet.appointment_location || 'Physique'}</span></>
                    : <><Video className="w-3 h-3 text-slate-400" /> {sheet.appointment_meeting_provider || 'Visioconference'}</>
                  }
                </span>
              )}
            </div>

            {/* Appointment link */}
            <Link
              to={`/appointments/${appointmentId}`}
              className="inline-flex items-center gap-1 mt-3 text-xs text-blue-600 hover:text-blue-800 font-medium transition-colors"
              data-testid="sheet-view-appointment-link"
            >
              Voir le rendez-vous
              <ArrowRight className="w-3 h-3" />
            </Link>

            {!submitted && (
              <p className="text-xs text-slate-400 mt-3">
                Le systeme n'a pas pu verifier automatiquement la presence de certains participants.
                Aidez-nous en declarant ce que vous avez observe.
              </p>
            )}

            {deadline && !submitted && (
              <div className="flex items-center gap-1.5 mt-2 text-xs text-slate-400">
                <Clock className="w-3.5 h-3.5" />
                <span>Deadline : {deadlineStr}</span>
              </div>
            )}
            {sheetStatus && !submitted && (
              <div className="text-xs text-slate-400 mt-1">
                {sheetStatus.submitted_sheets}/{sheetStatus.total_sheets} participants ont repondu
              </div>
            )}
          </div>

          {/* Content: read-only or edit mode */}
          {submitted ? (
            <div className="p-5" data-testid="sheet-readonly-view">
              <div className="flex items-center gap-2 mb-4">
                <Eye className="w-4 h-4 text-slate-400" />
                <p className="text-sm font-medium text-slate-600">Vos observations</p>
              </div>

              <div className="space-y-3">
                {sheet?.declarations?.map((d) => {
                  const status = d.declared_status;
                  const display = STATUS_DISPLAY[status] || STATUS_DISPLAY.unknown;
                  const StatusIcon = display.icon;
                  return (
                    <div
                      key={d.target_participant_id}
                      className={`flex items-center justify-between p-3 rounded-lg border ${display.color}`}
                      data-testid={`readonly-declaration-${d.target_participant_id}`}
                    >
                      <span className="text-sm font-medium">
                        {d.target_name || d.target_participant_id}
                      </span>
                      <span className="flex items-center gap-1.5 text-xs font-medium">
                        <StatusIcon className="w-3.5 h-3.5" />
                        {display.label}
                      </span>
                    </div>
                  );
                })}
              </div>

              <div className="mt-5 pt-4 border-t border-slate-100">
                <div className="flex items-start gap-2">
                  <HelpCircle className="w-4 h-4 text-slate-300 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-slate-400">
                    Vos reponses restent confidentielles. Les autres participants ne voient pas vos observations individuelles.
                  </p>
                </div>
              </div>
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
                    Vos reponses restent confidentielles jusqu'a la cloture du processus.
                    Les autres participants ne verront pas vos reponses individuelles.
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
