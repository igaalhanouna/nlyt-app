import React, { useState } from 'react';
import { Button } from '../../components/ui/button';
import { AlertTriangle, UserCheck, UserX, Clock, MapPin, Fingerprint, Loader2 } from 'lucide-react';

export default function PendingReviewSection({
  attendance,
  participants,
  evidenceData,
  onReclassify,
  reclassifying,
}) {
  const [confirmAction, setConfirmAction] = useState(null); // { recordId, outcome }

  if (!attendance?.evaluated) return null;

  const pendingRecords = (attendance.records || []).filter(r => r.review_required);
  if (pendingRecords.length === 0) return null;

  const getParticipantName = (pid) => {
    const p = participants?.find(pp => pp.participant_id === pid);
    if (!p) return pid.slice(0, 8);
    return [p.first_name, p.last_name].filter(Boolean).join(' ') || p.email || pid.slice(0, 8);
  };

  const getParticipantEvidence = (pid) => {
    const pe = evidenceData?.participants?.find(p => p.participant_id === pid);
    return pe?.evidence || [];
  };

  const basisLabels = {
    manual_checkin_only_on_time: 'Check-in manuel sans GPS',
    manual_checkin_only_late: 'Check-in manuel sans GPS (retard)',
    weak_evidence: 'Preuve insuffisante',
    no_proof_of_attendance: 'Aucune preuve de presence',
    pending_guarantee: 'Garantie en attente',
    accepted_no_guarantee: 'Pas de garantie',
    nlyt_proof_medium: 'NLYT Proof partiel (score moyen)',
    nlyt_proof_weak: 'NLYT Proof insuffisant',
    no_proof_meet_assisted_only: 'Google Meet seul (pas de NLYT Proof)',
    no_proof_video_fallback_on_time: 'API video seule (pas de NLYT Proof)',
    no_proof_video_fallback_late: 'API video seule — en retard',
    no_proof_video_ambiguous: 'Video ambigu',
    no_proof_no_video: 'Aucune preuve video',
    cancelled_late: 'Annulation tardive (sans timestamp)',
    cancellation_date_parse_error: 'Erreur date annulation',
  };

  const getEvidenceSummary = (evidence) => {
    if (!evidence || evidence.length === 0) return 'Aucune preuve enregistree';
    const sources = evidence.map(e => {
      const facts = e.derived_facts || {};
      if (e.source === 'manual_checkin') {
        if (facts.latitude) return `GPS (${facts.distance_meters ? Math.round(facts.distance_meters) + 'm' : '?'})`;
        return 'Check-in manuel (sans GPS)';
      }
      if (e.source === 'gps') return `GPS ${facts.distance_meters ? Math.round(facts.distance_meters) + 'm' : ''}`;
      if (e.source === 'qr') return 'QR code';
      if (e.source === 'video_conference') return `Video (${facts.provider || '?'})`;
      return e.source;
    });
    return sources.join(' + ');
  };

  const getDaysRemaining = (decidedAt) => {
    if (!decidedAt) return null;
    const decided = new Date(decidedAt);
    const timeout = new Date(decided.getTime() + 15 * 24 * 60 * 60 * 1000);
    const now = new Date();
    const daysLeft = Math.max(0, Math.ceil((timeout - now) / (24 * 60 * 60 * 1000)));
    return daysLeft;
  };

  const handleConfirm = (recordId, outcome) => {
    setConfirmAction({ recordId, outcome });
  };

  const executeAction = () => {
    if (!confirmAction) return;
    onReclassify(confirmAction.recordId, confirmAction.outcome);
    setConfirmAction(null);
  };

  return (
    <div className="mb-4 bg-amber-50 border border-amber-200 rounded-xl overflow-hidden" data-testid="pending-review-section">
      <div className="px-4 py-3 border-b border-amber-200 bg-amber-100/50">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-600" />
          <span className="text-sm font-semibold text-amber-900">
            {pendingRecords.length} participant{pendingRecords.length > 1 ? 's' : ''} en attente de verification
          </span>
        </div>
        <p className="text-xs text-amber-700 mt-1">
          Le systeme n'a pas pu determiner automatiquement la presence. Votre decision est requise.
        </p>
      </div>

      <div className="p-4 space-y-3">
        {pendingRecords.map((record) => {
          const evidence = getParticipantEvidence(record.participant_id);
          const daysLeft = getDaysRemaining(record.decided_at);
          const isProcessing = reclassifying === record.record_id;

          return (
            <div
              key={record.record_id}
              className="bg-white border border-amber-100 rounded-lg p-4"
              data-testid={`review-record-${record.record_id}`}
            >
              {/* Participant info */}
              <div className="flex items-start justify-between gap-3 mb-3">
                <div>
                  <p className="text-sm font-semibold text-slate-900" data-testid={`review-name-${record.record_id}`}>
                    {getParticipantName(record.participant_id)}
                  </p>
                  <p className="text-xs text-amber-700 mt-0.5">
                    {basisLabels[record.decision_basis] || record.decision_basis}
                  </p>
                </div>
                {record.outcome && record.outcome !== 'manual_review' && (
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    record.outcome === 'on_time' ? 'bg-emerald-100 text-emerald-700' :
                    record.outcome === 'late' ? 'bg-amber-100 text-amber-700' :
                    record.outcome === 'no_show' ? 'bg-red-100 text-red-700' :
                    'bg-slate-100 text-slate-700'
                  }`}>
                    {record.outcome === 'on_time' ? 'Suggere: Present' :
                     record.outcome === 'late' ? 'Suggere: En retard' :
                     record.outcome === 'no_show' ? 'Suggere: Absent' :
                     record.outcome}
                  </span>
                )}
              </div>

              {/* Evidence summary */}
              <div className="flex items-center gap-2 mb-3 text-xs text-slate-600">
                <Fingerprint className="w-3.5 h-3.5 text-slate-400" />
                <span>{getEvidenceSummary(evidence)}</span>
              </div>

              {/* Delay info if available */}
              {record.delay_minutes != null && record.delay_minutes > 0 && (
                <div className="flex items-center gap-2 mb-3 text-xs text-slate-600">
                  <Clock className="w-3.5 h-3.5 text-slate-400" />
                  <span>
                    Retard: {Math.round(record.delay_minutes)} min
                    {record.tolerated_delay_minutes != null && ` (tolerance: ${record.tolerated_delay_minutes} min)`}
                  </span>
                </div>
              )}

              {/* GPS details if available */}
              {evidence.some(e => e.derived_facts?.distance_meters) && (
                <div className="flex items-center gap-2 mb-3 text-xs text-slate-600">
                  <MapPin className="w-3.5 h-3.5 text-slate-400" />
                  <span>
                    {evidence.find(e => e.derived_facts?.distance_meters)?.derived_facts?.geographic_detail || 'Position GPS disponible'}
                  </span>
                </div>
              )}

              {/* Action buttons */}
              {confirmAction?.recordId === record.record_id ? (
                <div className="flex items-center gap-2 bg-slate-50 rounded-lg p-3">
                  <p className="text-xs text-slate-700 flex-1">
                    Confirmer : <strong>{confirmAction.outcome === 'on_time' ? 'Present (garantie liberee)' : 'Absent (penalite appliquee)'}</strong> ?
                  </p>
                  <Button
                    size="sm"
                    className="h-8 text-xs"
                    onClick={executeAction}
                    disabled={isProcessing}
                    data-testid={`confirm-review-${record.record_id}`}
                  >
                    {isProcessing ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : null}
                    Confirmer
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-8 text-xs"
                    onClick={() => setConfirmAction(null)}
                    data-testid={`cancel-review-${record.record_id}`}
                  >
                    Annuler
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    className="h-9 bg-emerald-600 hover:bg-emerald-700 text-white text-xs gap-1.5"
                    onClick={() => handleConfirm(record.record_id, 'on_time')}
                    disabled={isProcessing}
                    data-testid={`review-present-${record.record_id}`}
                  >
                    <UserCheck className="w-3.5 h-3.5" />
                    Present
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-9 border-red-200 text-red-700 hover:bg-red-50 text-xs gap-1.5"
                    onClick={() => handleConfirm(record.record_id, 'no_show')}
                    disabled={isProcessing}
                    data-testid={`review-absent-${record.record_id}`}
                  >
                    <UserX className="w-3.5 h-3.5" />
                    Absent
                  </Button>
                </div>
              )}

              {/* Timeout info */}
              {daysLeft !== null && (
                <p className="text-xs text-slate-400 mt-2" data-testid={`review-timeout-${record.record_id}`}>
                  {daysLeft > 0
                    ? `Resolution auto dans ${daysLeft} jour${daysLeft > 1 ? 's' : ''} (garantie liberee sans penalite)`
                    : 'Resolution automatique imminente'}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
