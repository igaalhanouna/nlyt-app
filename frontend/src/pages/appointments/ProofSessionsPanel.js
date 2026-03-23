import React from 'react';
import { Button } from '../../components/ui/button';
import { Fingerprint, Activity, Video, Copy, UserCheck, UserX, AlertTriangle, Loader2, CheckCircle } from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function ProofSessionsPanel({ participants, proofSessions, validatingSession, onValidateSession, onRefresh }) {
  const handleCopyProofLink = (participant) => {
    const link = `${API_URL}/proof/${participant.invitation_token}?token=${participant.invitation_token}`;
    navigator.clipboard.writeText(link).then(() => {
      toast.success(`Lien copié pour ${participant.first_name}`);
    }).catch(() => {
      toast.error('Impossible de copier le lien');
    });
  };

  const levelColors = {
    strong: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    medium: 'bg-amber-50 text-amber-700 border-amber-200',
    weak: 'bg-red-50 text-red-700 border-red-200',
  };
  const levelLabels = { strong: 'Fort', medium: 'Moyen', weak: 'Faible' };
  const statusLabels = { present: 'Présent', partial: 'Partiel', absent: 'Absent' };
  const statusColors = {
    present: 'bg-emerald-50 text-emerald-700',
    partial: 'bg-amber-50 text-amber-700',
    absent: 'bg-red-50 text-red-700',
  };

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-6 mt-6" data-testid="proof-sessions-section">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Fingerprint className="w-5 h-5 text-blue-600" />
          <h2 className="text-lg font-semibold text-slate-900">NLYT Proof — Sessions de présence</h2>
        </div>
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-blue-500" />
          <span className="text-sm text-slate-500">{proofSessions.length} session(s)</span>
        </div>
      </div>

      {participants.length > 0 && (
        <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm font-semibold text-blue-900 mb-2">Liens de check-in NLYT</p>
          <p className="text-xs text-blue-700 mb-3">Chaque participant a un lien unique. Ce lien est inclus dans l'email d'invitation.</p>
          <div className="space-y-2">
            {participants.filter(p => !p.is_organizer).map(p => (
              <div key={p.participant_id} className="flex items-center justify-between gap-2 bg-white rounded-lg border border-blue-100 px-3 py-2">
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-slate-900">{p.first_name} {p.last_name}</span>
                  <span className="text-xs text-slate-400 ml-2">{p.email}</span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs gap-1 flex-shrink-0"
                  onClick={() => handleCopyProofLink(p)}
                  data-testid={`copy-proof-link-${p.participant_id}`}
                >
                  <Copy className="w-3 h-3" />
                  Copier le lien
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {proofSessions.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase">Participant</th>
                <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase">Check-in</th>
                <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase">Durée</th>
                <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase">Heartbeats</th>
                <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase">Score</th>
                <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase">Niveau</th>
                <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase">Statut</th>
                <th className="text-right py-2 px-3 text-xs font-semibold text-slate-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody>
              {proofSessions.map(session => {
                const isActive = !session.checked_out_at;
                const durationMin = Math.round((session.active_duration_seconds || 0) / 60);
                const finalStatus = session.final_status || session.suggested_status;

                return (
                  <tr key={session.session_id} className="border-b border-slate-100 hover:bg-slate-50" data-testid={`proof-session-row-${session.session_id}`}>
                    <td className="py-2.5 px-3">
                      <div className="font-medium text-slate-900">{session.participant_name || '—'}</div>
                      <div className="text-xs text-slate-400">{session.participant_email}</div>
                      {(session.video_display_name || session.video_email) && (
                        <div className="flex items-center gap-1 mt-0.5" data-testid={`video-name-${session.session_id}`}>
                          <Video className="w-3 h-3 text-blue-400 flex-shrink-0" />
                          <span className="text-xs text-blue-600 font-medium truncate max-w-[180px]" title={session.video_display_name || session.video_email}>
                            {session.video_display_name || session.video_email}
                          </span>
                          {session.video_provider && (
                            <span className="text-xs text-slate-300">({session.video_provider})</span>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-xs text-slate-600">
                      {session.checked_in_at ? new Date(session.checked_in_at).toLocaleString('fr-FR', { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' }) : '—'}
                    </td>
                    <td className="py-2.5 px-3">
                      {isActive ? (
                        <span className="inline-flex items-center gap-1 text-xs text-blue-600 font-medium">
                          <Activity className="w-3 h-3 animate-pulse" /> En cours
                        </span>
                      ) : (
                        <span className="text-sm text-slate-700">{durationMin} min</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-sm text-slate-700">{session.heartbeat_count || 0}</td>
                    <td className="py-2.5 px-3">
                      <span className="text-sm font-bold text-slate-900">{session.score || 0}<span className="text-xs text-slate-400">/100</span></span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium border ${levelColors[session.proof_level] || ''}`}>
                        {levelLabels[session.proof_level] || session.proof_level}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      {session.final_status ? (
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[session.final_status]}`}>
                          <CheckCircle className="w-3 h-3" />
                          {statusLabels[session.final_status]}
                        </span>
                      ) : (
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[finalStatus] || 'bg-slate-50 text-slate-500'}`}>
                          {statusLabels[finalStatus] || '—'} <span className="ml-1 text-slate-400">(suggéré)</span>
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      {!session.final_status && !isActive && (
                        <div className="flex items-center gap-1 justify-end">
                          <Button variant="outline" size="sm" className="h-6 text-xs px-2 text-emerald-700 border-emerald-200 hover:bg-emerald-50"
                            onClick={() => onValidateSession(session.session_id, 'present')} disabled={validatingSession === session.session_id}
                            data-testid={`validate-present-${session.session_id}`}>
                            {validatingSession === session.session_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <UserCheck className="w-3 h-3" />}
                          </Button>
                          <Button variant="outline" size="sm" className="h-6 text-xs px-2 text-amber-700 border-amber-200 hover:bg-amber-50"
                            onClick={() => onValidateSession(session.session_id, 'partial')} disabled={validatingSession === session.session_id}
                            data-testid={`validate-partial-${session.session_id}`}>
                            <AlertTriangle className="w-3 h-3" />
                          </Button>
                          <Button variant="outline" size="sm" className="h-6 text-xs px-2 text-red-700 border-red-200 hover:bg-red-50"
                            onClick={() => onValidateSession(session.session_id, 'absent')} disabled={validatingSession === session.session_id}
                            data-testid={`validate-absent-${session.session_id}`}>
                            <UserX className="w-3 h-3" />
                          </Button>
                        </div>
                      )}
                      {session.final_status && (
                        <span className="text-xs text-slate-400">Validé</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-8 text-slate-500">
          <Fingerprint className="w-8 h-8 mx-auto mb-2 text-slate-300" />
          <p className="text-sm">Aucune session de preuve enregistrée.</p>
          <p className="text-xs text-slate-400 mt-1">Les participants doivent utiliser leur lien de check-in NLYT pour démarrer une session.</p>
        </div>
      )}
    </div>
  );
}
