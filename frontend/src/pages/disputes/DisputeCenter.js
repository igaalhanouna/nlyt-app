import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';
import { Button } from '../../components/ui/button';
import { attendanceAPI } from '../../services/api';
import { toast } from 'sonner';
import {
  AlertTriangle, UserCheck, UserX, Clock, MapPin, Fingerprint,
  Loader2, Calendar, ChevronRight, CheckCircle, Timer, ArrowLeft
} from 'lucide-react';

const basisLabels = {
  manual_checkin_only_on_time: 'Check-in manuel sans GPS',
  manual_checkin_only_late: 'Check-in manuel sans GPS (retard)',
  weak_evidence: 'Preuve insuffisante',
  no_proof_of_attendance: 'Aucune preuve de presence',
  nlyt_proof_medium: 'NLYT Proof partiel (score moyen)',
  nlyt_proof_weak: 'NLYT Proof insuffisant',
  no_proof_meet_assisted_only: 'Google Meet seul (pas de NLYT Proof)',
  no_proof_video_fallback_on_time: 'API video seule (pas de NLYT Proof)',
  no_proof_video_fallback_late: 'API video seule — en retard',
  no_proof_video_ambiguous: 'Video ambigu',
  no_proof_no_video: 'Aucune preuve video',
  cancelled_late: 'Annulation tardive (sans timestamp)',
  medium_evidence_on_time: 'Preuve partielle (a l\'heure)',
  medium_evidence_late: 'Preuve partielle (en retard)',
};

function formatDate(isoString) {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString('fr-FR', {
      day: 'numeric', month: 'long', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  } catch { return isoString; }
}

export default function DisputeCenter() {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reclassifying, setReclassifying] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null);

  const loadReviews = useCallback(async () => {
    try {
      const res = await attendanceAPI.pendingReviews();
      setReviews(res.data.pending_reviews || []);
    } catch {
      toast.error('Erreur lors du chargement des decisions en attente');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadReviews(); }, [loadReviews]);

  const handleReclassify = async (recordId, newOutcome) => {
    setReclassifying(recordId);
    try {
      await attendanceAPI.reclassify(recordId, { new_outcome: newOutcome });
      toast.success(newOutcome === 'on_time' ? 'Participant marque comme present' : 'Participant marque comme absent');
      setConfirmAction(null);
      await loadReviews();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Erreur lors de la reclassification');
    } finally {
      setReclassifying(null);
    }
  };

  // Group reviews by appointment
  const grouped = reviews.reduce((acc, r) => {
    const key = r.appointment_id;
    if (!acc[key]) {
      acc[key] = {
        appointment_id: r.appointment_id,
        title: r.appointment_title,
        datetime: r.appointment_datetime,
        type: r.appointment_type,
        records: [],
      };
    }
    acc[key].records.push(r);
    return acc;
  }, {});

  const appointments = Object.values(grouped).sort((a, b) => {
    const minA = Math.min(...a.records.map(r => r.days_remaining ?? 15));
    const minB = Math.min(...b.records.map(r => r.days_remaining ?? 15));
    return minA - minB;
  });

  const totalCount = reviews.length;

  return (
    <div className="min-h-screen bg-slate-50/50">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Decisions en attente' },
      ]} />

      <div className="max-w-4xl mx-auto px-4 md:px-6 pb-12">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-slate-900" data-testid="disputes-title">
              Decisions en attente
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Cas necessitant votre verification avant action financiere
            </p>
          </div>
          {totalCount > 0 && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-100 text-amber-800 text-sm font-semibold rounded-full" data-testid="disputes-count-badge">
              <AlertTriangle className="w-3.5 h-3.5" />
              {totalCount}
            </span>
          )}
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
          </div>
        ) : totalCount === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 p-12 text-center" data-testid="disputes-empty">
            <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
            <h2 className="text-lg font-semibold text-slate-900 mb-2">Tout est en ordre</h2>
            <p className="text-sm text-slate-500 mb-6">Aucune decision en attente. Tous les cas ont ete traites.</p>
            <Link to="/dashboard">
              <Button variant="outline" size="sm" className="gap-1.5">
                <ArrowLeft className="w-3.5 h-3.5" />
                Retour au tableau de bord
              </Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {appointments.map((apt) => (
              <div
                key={apt.appointment_id}
                className="bg-white rounded-xl border border-slate-200 overflow-hidden"
                data-testid={`dispute-group-${apt.appointment_id}`}
              >
                {/* Appointment header — fully clickable */}
                <Link
                  to={`/appointments/${apt.appointment_id}`}
                  state={{ from: 'disputes' }}
                  className="block px-4 py-3 border-b border-slate-100 flex items-center justify-between hover:bg-slate-50 transition-colors cursor-pointer group"
                  data-testid={`dispute-apt-link-${apt.appointment_id}`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center">
                      <AlertTriangle className="w-4 h-4 text-amber-600" />
                    </div>
                    <div className="min-w-0">
                      <h3 className="text-sm font-semibold text-slate-900 truncate group-hover:text-slate-700" data-testid={`dispute-apt-title-${apt.appointment_id}`}>
                        {apt.title}
                      </h3>
                      <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
                        <Calendar className="w-3 h-3" />
                        <span>{formatDate(apt.datetime)}</span>
                        <span className="text-slate-300">|</span>
                        <span className="capitalize">{apt.type === 'video' ? 'Video' : 'Physique'}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full font-medium">
                      {apt.records.length} cas
                    </span>
                    <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-slate-600 transition-colors" />
                  </div>
                </Link>

                {/* Records */}
                <div className="divide-y divide-slate-50">
                  {apt.records.map((record) => {
                    const isProcessing = reclassifying === record.record_id;
                    const isConfirming = confirmAction?.recordId === record.record_id;

                    return (
                      <div key={record.record_id} className="px-4 py-4" data-testid={`dispute-record-${record.record_id}`}>
                        <div className="flex items-start justify-between gap-4">
                          {/* Left: participant info */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1.5">
                              <p className="text-sm font-semibold text-slate-900 truncate" data-testid={`dispute-name-${record.record_id}`}>
                                {record.participant_name}
                              </p>
                              {record.outcome && record.outcome !== 'manual_review' && (
                                <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                                  record.outcome === 'on_time' ? 'bg-emerald-50 text-emerald-700' :
                                  record.outcome === 'late' ? 'bg-amber-50 text-amber-700' :
                                  record.outcome === 'no_show' ? 'bg-red-50 text-red-700' :
                                  'bg-slate-50 text-slate-600'
                                }`}>
                                  {record.outcome === 'on_time' ? 'Suggere: Present' :
                                   record.outcome === 'late' ? 'Suggere: En retard' :
                                   record.outcome === 'no_show' ? 'Suggere: Absent' :
                                   record.outcome}
                                </span>
                              )}
                            </div>

                            {/* Reason */}
                            <p className="text-xs text-amber-700 mb-2">
                              {basisLabels[record.decision_basis] || record.decision_basis}
                            </p>

                            {/* Evidence */}
                            <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-1">
                              <Fingerprint className="w-3 h-3 text-slate-400" />
                              <span>{record.evidence_sources?.length > 0 ? record.evidence_sources.join(' + ') : 'Aucune preuve enregistree'}</span>
                            </div>

                            {/* Delay info */}
                            {record.delay_minutes != null && record.delay_minutes > 0 && (
                              <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-1">
                                <Clock className="w-3 h-3 text-slate-400" />
                                <span>Retard: {Math.round(record.delay_minutes)} min
                                  {record.tolerated_delay_minutes != null && ` (tolerance: ${record.tolerated_delay_minutes} min)`}
                                </span>
                              </div>
                            )}

                            {/* Timeout */}
                            <div className="flex items-center gap-1.5 text-xs text-slate-400 mt-1.5">
                              <Timer className="w-3 h-3" />
                              <span>
                                {record.days_remaining != null && record.days_remaining > 0
                                  ? `Resolution auto dans ${record.days_remaining} jour${record.days_remaining > 1 ? 's' : ''}`
                                  : 'Resolution automatique imminente'}
                              </span>
                            </div>
                          </div>

                          {/* Right: action buttons */}
                          <div className="flex-shrink-0">
                            {isConfirming ? (
                              <div className="bg-slate-50 rounded-lg p-3 min-w-[180px]">
                                <p className="text-xs text-slate-700 mb-2">
                                  {confirmAction.outcome === 'on_time'
                                    ? 'Confirmer present ? (garantie liberee)'
                                    : 'Confirmer absent ? (penalite appliquee)'}
                                </p>
                                <div className="flex gap-2">
                                  <Button
                                    size="sm"
                                    className="h-7 text-xs flex-1"
                                    onClick={() => handleReclassify(record.record_id, confirmAction.outcome)}
                                    disabled={isProcessing}
                                    data-testid={`dispute-confirm-${record.record_id}`}
                                  >
                                    {isProcessing ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Oui'}
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    className="h-7 text-xs"
                                    onClick={() => setConfirmAction(null)}
                                    data-testid={`dispute-cancel-${record.record_id}`}
                                  >
                                    Non
                                  </Button>
                                </div>
                              </div>
                            ) : (
                              <div className="flex flex-col gap-1.5">
                                <Button
                                  size="sm"
                                  className="h-8 bg-emerald-600 hover:bg-emerald-700 text-white text-xs gap-1.5 w-full justify-start"
                                  onClick={() => setConfirmAction({ recordId: record.record_id, outcome: 'on_time' })}
                                  disabled={isProcessing}
                                  data-testid={`dispute-present-${record.record_id}`}
                                >
                                  <UserCheck className="w-3.5 h-3.5" />
                                  Present
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-8 border-red-200 text-red-700 hover:bg-red-50 text-xs gap-1.5 w-full justify-start"
                                  onClick={() => setConfirmAction({ recordId: record.record_id, outcome: 'no_show' })}
                                  disabled={isProcessing}
                                  data-testid={`dispute-absent-${record.record_id}`}
                                >
                                  <UserX className="w-3.5 h-3.5" />
                                  Absent
                                </Button>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
