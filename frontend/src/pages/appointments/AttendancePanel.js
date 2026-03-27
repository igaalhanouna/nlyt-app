import React from 'react';
import { Button } from '../../components/ui/button';
import { ClipboardCheck, RefreshCw, Loader2, Check, X, AlertTriangle, UserCheck, UserX, HelpCircle, ChevronDown } from 'lucide-react';
import { formatDateTimeFr } from '../../utils/dateFormat';

export default function AttendancePanel({
  attendance,
  evaluating,
  onEvaluate,
  onReevaluate,
  onReclassify,
  reclassifying,
  reclassifyDropdown,
  setReclassifyDropdown,
  participants,
  getParticipantEvidence,
}) {
  const outcomeLabels = { on_time: 'Présent', late: 'En retard (toléré)', late_penalized: 'En retard (pénalisé)', no_show: 'Absent', manual_review: 'À vérifier', waived: 'Dispensé' };
  const outcomeColors = {
    on_time: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    late: 'bg-amber-100 text-amber-800 border-amber-200',
    late_penalized: 'bg-orange-100 text-orange-800 border-orange-200',
    no_show: 'bg-red-100 text-red-800 border-red-200',
    manual_review: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    waived: 'bg-slate-100 text-slate-800 border-slate-200',
  };
  const outcomeIcons = {
    on_time: <UserCheck className="w-3.5 h-3.5" />,
    late: <AlertTriangle className="w-3.5 h-3.5" />,
    late_penalized: <AlertTriangle className="w-3.5 h-3.5" />,
    no_show: <UserX className="w-3.5 h-3.5" />,
    manual_review: <HelpCircle className="w-3.5 h-3.5" />,
    waived: <Check className="w-3.5 h-3.5" />,
  };

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-6 mt-6" data-testid="attendance-section">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="w-5 h-5 text-slate-700" />
          <h2 className="text-lg font-semibold text-slate-900">Détection de présence</h2>
        </div>
        {!attendance?.evaluated && (
          <Button onClick={onEvaluate} disabled={evaluating} size="sm" data-testid="evaluate-attendance-btn">
            {evaluating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ClipboardCheck className="w-4 h-4 mr-2" />}
            Évaluer la présence
          </Button>
        )}
        {attendance?.evaluated && (
          <Button onClick={onReevaluate} disabled={evaluating} size="sm" variant="outline" data-testid="reevaluate-attendance-btn">
            {evaluating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
            Re-évaluer
          </Button>
        )}
      </div>

      {attendance?.evaluated ? (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-5">
            {[
              { key: 'on_time', label: 'Présents', color: 'emerald' },
              { key: 'late', label: 'En retard (toléré)', color: 'amber' },
              { key: 'late_penalized', label: 'En retard (pénalisé)', color: 'orange' },
              { key: 'no_show', label: 'Absents', color: 'red' },
              { key: 'manual_review', label: 'À vérifier', color: 'yellow' },
              { key: 'waived', label: 'Dispensés', color: 'slate' },
            ].map(({ key, label, color }) => (
              <div key={key} className={`text-center p-3 rounded-lg bg-${color}-50 border border-${color}-200`} data-testid={`attendance-summary-${key}`}>
                <p className={`text-xl font-bold text-${color}-800`}>{attendance.summary?.[key] || 0}</p>
                <p className={`text-xs text-${color}-600`}>{label}</p>
              </div>
            ))}
          </div>

          <div className="space-y-2">
            {attendance.records?.map((record) => {
              const pEvidence = getParticipantEvidence(record.participant_id);
              return (
                <div key={record.participant_id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg" data-testid={`attendance-record-${record.participant_id}`}>
                  <div className="flex items-center gap-3">
                    <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${outcomeColors[record.outcome] || 'bg-slate-100'}`}>
                      {outcomeIcons[record.outcome]}
                      {outcomeLabels[record.outcome] || record.outcome}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-slate-900">
                        {participants.find(p => p.participant_id === record.participant_id)?.first_name || record.participant_id.slice(0, 8)}
                        {' '}
                        {participants.find(p => p.participant_id === record.participant_id)?.last_name || ''}
                      </p>
                      {pEvidence && pEvidence.length > 0 && (
                        <div className="flex items-center gap-2 mt-0.5">
                          {pEvidence.map(e => (
                            <span key={e.evidence_id} className="text-xs text-slate-400">
                              {e.source === 'qr' ? 'QR' : e.source === 'gps' ? 'GPS' : e.source === 'manual_checkin' ? 'Manuel' : e.source === 'video_conference' ? 'Vidéo' : e.source}
                              {' '}({e.confidence_score})
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="relative">
                    <Button variant="ghost" size="sm" className="h-7 text-xs gap-1"
                      onClick={() => setReclassifyDropdown(reclassifyDropdown === record.record_id ? null : record.record_id)}
                      disabled={reclassifying === record.record_id}
                      data-testid={`reclassify-btn-${record.participant_id}`}>
                      {reclassifying === record.record_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <ChevronDown className="w-3 h-3" />}
                      Reclasser
                    </Button>
                    {reclassifyDropdown === record.record_id && (
                      <div className="absolute right-0 top-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg py-1 z-20 min-w-[140px]">
                        {Object.entries(outcomeLabels).filter(([k]) => k !== record.outcome).map(([key, label]) => (
                          <button key={key} className="w-full text-left px-3 py-1.5 text-xs hover:bg-slate-50 flex items-center gap-2"
                            onClick={() => onReclassify(record.record_id, key)}
                            data-testid={`reclassify-${record.participant_id}-${key}`}>
                            {outcomeIcons[key]}
                            {label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <p className="text-xs text-slate-400 mt-3">
            Évalué le {formatDateTimeFr(attendance.evaluated_at)} — Décisions automatiques, modifiables par l'organisateur
          </p>
        </>
      ) : (
        <div className="text-center py-6 text-slate-500">
          <ClipboardCheck className="w-8 h-8 mx-auto mb-2 text-slate-300" />
          <p className="text-sm">L'évaluation de présence n'a pas encore été effectuée.</p>
          <p className="text-xs text-slate-400 mt-1">Cliquez sur "Évaluer la présence" ou attendez l'évaluation automatique (toutes les 10 min après fin du RDV + 30 min).</p>
        </div>
      )}
    </div>
  );
}
