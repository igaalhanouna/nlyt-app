import React from 'react';
import { ClipboardCheck, Clock, XCircle, AlertTriangle, UserCheck, FileText } from 'lucide-react';

const outcomeConfig = {
  on_time: { label: 'Présent à l\'heure', icon: UserCheck, color: 'text-emerald-700 bg-emerald-50 border-emerald-200' },
  late: { label: 'En retard (non pénalisé)', icon: Clock, color: 'text-amber-700 bg-amber-50 border-amber-200' },
  late_penalized: { label: 'En retard (pénalisé)', icon: Clock, color: 'text-orange-700 bg-orange-50 border-orange-200' },
  no_show: { label: 'Absent', icon: XCircle, color: 'text-red-700 bg-red-50 border-red-200' },
  manual_review: { label: 'En attente de vérification', icon: AlertTriangle, color: 'text-slate-600 bg-slate-50 border-slate-200' },
  waived: { label: 'Dispensé', icon: FileText, color: 'text-blue-700 bg-blue-50 border-blue-200' },
};

export default function AttendancePanel({ attendance, participants, declarativePhase }) {
  if (!attendance?.evaluated || !attendance?.records?.length) return null;

  const getParticipantName = (pid) => {
    const p = participants?.find(x => x.participant_id === pid);
    return p ? `${p.first_name || ''} ${p.last_name || ''}`.trim() || p.email : pid?.slice(0, 8);
  };

  const phaseLabel = declarativePhase === 'collecting'
    ? 'Déclarations en cours'
    : declarativePhase === 'disputed'
    ? 'Litige en cours'
    : declarativePhase === 'resolved'
    ? 'Résolu'
    : null;

  return (
    <div className="p-4 space-y-3" data-testid="attendance-panel-readonly">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="w-4 h-4 text-slate-500" />
          <h4 className="text-sm font-semibold text-slate-900">Résultats de présence</h4>
        </div>
        {phaseLabel && (
          <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
            {phaseLabel}
          </span>
        )}
      </div>

      <div className="space-y-2">
        {attendance.records.map((record) => {
          const config = outcomeConfig[record.outcome] || outcomeConfig.manual_review;
          const Icon = config.icon;
          return (
            <div
              key={record.record_id || record.participant_id}
              className={`flex items-center justify-between px-3 py-2 border rounded-lg ${config.color}`}
              data-testid={`attendance-record-${record.participant_id}`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <Icon className="w-4 h-4 flex-shrink-0" />
                <span className="text-sm font-medium truncate">{getParticipantName(record.participant_id)}</span>
              </div>
              <span className="text-xs font-medium flex-shrink-0">{config.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
