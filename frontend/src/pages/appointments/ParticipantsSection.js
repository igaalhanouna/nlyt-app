import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { Users, ShieldCheck, CreditCard, Check, X, Ban, Clock, AlertTriangle, RefreshCw } from 'lucide-react';

const getStatusBadge = (status, participant) => {
  if (participant?.guarantee_requires_revalidation && status === 'accepted_guaranteed') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-100 text-amber-800 rounded-full text-[10px] sm:text-xs font-medium" data-testid={`badge-revalidation-${participant.participant_id}`}>
        <AlertTriangle className="w-2.5 h-2.5 sm:w-3 sm:h-3" /> À reconfirmer
      </span>
    );
  }
  const badges = {
    accepted_guaranteed: { bg: 'bg-emerald-100 text-emerald-800', icon: <ShieldCheck className="w-2.5 h-2.5 sm:w-3 sm:h-3" />, label: 'Garanti' },
    accepted_pending_guarantee: { bg: 'bg-amber-100 text-amber-800', icon: <CreditCard className="w-2.5 h-2.5 sm:w-3 sm:h-3" />, label: 'Garantie en cours' },
    accepted: { bg: 'bg-emerald-100 text-emerald-800', icon: <Check className="w-2.5 h-2.5 sm:w-3 sm:h-3" />, label: 'Accepté' },
    declined: { bg: 'bg-red-100 text-red-800', icon: <X className="w-2.5 h-2.5 sm:w-3 sm:h-3" />, label: 'Refusé' },
    cancelled_by_participant: { bg: 'bg-orange-100 text-orange-800', icon: <Ban className="w-2.5 h-2.5 sm:w-3 sm:h-3" />, label: 'Annulé' },
  };
  const b = badges[status] || { bg: 'bg-blue-100 text-blue-800', icon: <Clock className="w-2.5 h-2.5 sm:w-3 sm:h-3" />, label: 'Invité' };
  return <span className={`inline-flex items-center gap-1 px-2 py-0.5 ${b.bg} rounded-full text-[10px] sm:text-xs font-medium`}>{b.icon} {b.label}</span>;
};

export default function ParticipantsSection({
  participants, isCancelled, appointmentId, resendingToken, onResend, acceptedCount, pendingCount, guaranteedCount,
}) {
  if (!participants.length) return null;
  const visible = participants.slice(0, 3);
  const remaining = participants.length - 3;

  return (
    <div className={`bg-white border border-slate-200 rounded-xl p-4 mb-4 ${isCancelled ? 'opacity-60' : ''}`} data-testid="participants-section">
      {/* Header with social signal */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-slate-900">Participants</h2>
        <p className="text-xs text-slate-500">
          <span className="text-emerald-600 font-medium">{acceptedCount} confirmé{acceptedCount > 1 ? 's' : ''}</span>
          {pendingCount > 0 && <span> · {pendingCount} en attente</span>}
        </p>
      </div>

      {/* List */}
      <div className="space-y-2">
        {visible.map((p) => (
          <div key={p.participant_id} className="flex items-center justify-between gap-2 py-2 border-b border-slate-100 last:border-0">
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 flex-wrap">
                <p className="text-sm font-medium text-slate-900 truncate">{p.first_name} {p.last_name}</p>
                {p.is_organizer && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-medium" data-testid={`organizer-badge-${p.participant_id}`}>Org.</span>
                )}
              </div>
              <p className="text-xs text-slate-400 truncate">{p.email}</p>
            </div>
            <div className="flex items-center gap-1.5 flex-shrink-0">
              {getStatusBadge(p.status, p)}
              {p.status === 'invited' && !isCancelled && !p.is_organizer && (
                <button
                  title="Renvoyer"
                  disabled={resendingToken === p.invitation_token}
                  onClick={() => onResend(p.invitation_token)}
                  className="p-1.5 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors disabled:opacity-50"
                  data-testid={`resend-detail-btn-${p.participant_id}`}
                >
                  <RefreshCw className={`w-3 h-3 ${resendingToken === p.invitation_token ? 'animate-spin' : ''}`} />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {remaining > 0 && (
        <p className="text-xs text-slate-400 text-center mt-2">et {remaining} autre{remaining > 1 ? 's' : ''}</p>
      )}

      {!isCancelled && (
        <Link to={`/appointments/${appointmentId}/participants`} className="block mt-3">
          <Button variant="outline" className="w-full h-10 text-sm gap-2" data-testid="manage-participants-btn">
            <Users className="w-4 h-4" />
            Gérer les participants
          </Button>
        </Link>
      )}
    </div>
  );
}
