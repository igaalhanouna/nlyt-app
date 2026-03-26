import React from 'react';
import { FileEdit, Check, X, Loader2, Pencil, Send } from 'lucide-react';
import { formatDateTimeFr, utcToLocalInput } from '../../utils/dateFormat';

export default function ModificationProposalSection({
  activeProposal,
  participant,
  respondingProposal,
  onRespondToProposal,
  appointment,
  responseStatus,
  isAppointmentPast,
  showProposeForm,
  setShowProposeForm,
  proposalForm,
  setProposalForm,
  submittingProposal,
  onSubmitProposal,
}) {
  const effectiveStatus = responseStatus || participant.status;
  const canPropose = ['accepted', 'accepted_guaranteed', 'accepted_pending_guarantee', 'guaranteed'].includes(effectiveStatus) && !activeProposal && !isAppointmentPast;

  return (
    <>
      {/* Active proposal banner */}
      {activeProposal && activeProposal.status === 'pending' && (
        <div className="p-6 bg-blue-50 border-b-2 border-blue-300" data-testid="participant-proposal-banner">
          <div className="flex items-center gap-2 mb-3">
            <FileEdit className="w-5 h-5 text-blue-600" />
            <h3 className="font-semibold text-blue-900">Modification proposée</h3>
            <span className="text-xs bg-blue-200 text-blue-800 px-2 py-0.5 rounded-full ml-auto">
              Par {activeProposal.proposed_by?.name || (activeProposal.proposed_by?.role === 'organizer' ? "l'organisateur" : 'un participant')}
            </span>
          </div>

          <div className="grid sm:grid-cols-2 gap-3 mb-4">
            {Object.entries(activeProposal.changes || {}).map(([field, newVal]) => {
              const oldVal = activeProposal.original_values?.[field];
              const labels = { start_datetime: 'Date/Heure', duration_minutes: 'Durée', location: 'Lieu', meeting_provider: 'Visio', appointment_type: 'Type' };
              const fmtVal = (f, v) => {
                if (f === 'start_datetime') return formatDateTimeFr(v);
                if (f === 'duration_minutes') return `${v} min`;
                if (f === 'appointment_type') return v === 'physical' ? 'En personne' : 'Visio';
                return v || '—';
              };
              return (
                <div key={field} className="bg-white rounded-lg p-3 border border-blue-200">
                  <p className="text-xs font-semibold text-slate-500 mb-1">{labels[field] || field}</p>
                  <p className="text-sm text-red-600 line-through">{fmtVal(field, oldVal)}</p>
                  <p className="text-sm text-emerald-700 font-semibold">{fmtVal(field, newVal)}</p>
                </div>
              );
            })}
          </div>

          {activeProposal.responses?.some(r => r.participant_id === participant.participant_id && r.status === 'pending') && (
            <div className="flex gap-3" data-testid="participant-respond-proposal">
              <button
                onClick={() => onRespondToProposal('accept')}
                disabled={respondingProposal}
                className="flex-1 flex items-center justify-center gap-2 py-3 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 font-semibold transition-colors"
                data-testid="accept-proposal-btn"
              >
                {respondingProposal ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                Accepter
              </button>
              <button
                onClick={() => onRespondToProposal('reject')}
                disabled={respondingProposal}
                className="flex-1 flex items-center justify-center gap-2 py-3 bg-white text-red-600 border-2 border-red-300 rounded-lg hover:bg-red-50 disabled:opacity-50 font-semibold transition-colors"
                data-testid="reject-proposal-btn"
              >
                <X className="w-4 h-4" /> Refuser
              </button>
            </div>
          )}

          {activeProposal.responses?.some(r => r.participant_id === participant.participant_id && r.status === 'accepted') && (
            <p className="text-sm text-emerald-700 font-medium flex items-center gap-1">
              <Check className="w-4 h-4" /> Vous avez accepté cette modification. En attente des autres participants.
            </p>
          )}

          <p className="text-xs text-slate-400 mt-3">Expire le {formatDateTimeFr(activeProposal.expires_at)}</p>
        </div>
      )}

      {/* Propose modification form */}
      {canPropose && (
        <div className="px-6 py-3 border-b border-slate-100">
          {!showProposeForm ? (
            <button
              onClick={() => {
                setProposalForm({
                  start_datetime: utcToLocalInput(appointment.start_datetime),
                  duration_minutes: String(appointment.duration_minutes || 60),
                  location: appointment.location || ''
                });
                setShowProposeForm(true);
              }}
              className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 transition-colors"
              data-testid="participant-propose-btn"
            >
              <Pencil className="w-4 h-4" /> Proposer une modification
            </button>
          ) : (
            <div className="space-y-3" data-testid="participant-proposal-form">
              <h4 className="font-semibold text-slate-800 flex items-center gap-2">
                <FileEdit className="w-4 h-4 text-blue-600" /> Proposer une modification
              </h4>
              <p className="text-xs text-slate-500">L'organisateur et les autres participants devront accepter.</p>
              <div className="grid sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-slate-600">Date et heure</label>
                  <input type="datetime-local" value={proposalForm.start_datetime}
                    min={(() => { const n=new Date(); return `${n.getFullYear()}-${String(n.getMonth()+1).padStart(2,'0')}-${String(n.getDate()).padStart(2,'0')}T${String(n.getHours()).padStart(2,'0')}:${String(n.getMinutes()).padStart(2,'0')}`; })()}
                    onChange={(e) => setProposalForm({...proposalForm, start_datetime: e.target.value})}
                    className="w-full mt-1 h-9 rounded-md border border-slate-300 px-2 text-sm"
                    data-testid="participant-proposal-datetime"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-600">Durée (min)</label>
                  <input type="number" min="15" step="15" value={proposalForm.duration_minutes}
                    onChange={(e) => setProposalForm({...proposalForm, duration_minutes: e.target.value})}
                    className="w-full mt-1 h-9 rounded-md border border-slate-300 px-2 text-sm"
                    data-testid="participant-proposal-duration"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="text-xs font-medium text-slate-600">Lieu</label>
                  <input type="text" value={proposalForm.location}
                    onChange={(e) => setProposalForm({...proposalForm, location: e.target.value})}
                    className="w-full mt-1 h-9 rounded-md border border-slate-300 px-2 text-sm"
                    data-testid="participant-proposal-location"
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={onSubmitProposal} disabled={submittingProposal}
                  className="flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 font-medium"
                  data-testid="participant-submit-proposal-btn"
                >
                  {submittingProposal ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Envoyer
                </button>
                <button onClick={() => setShowProposeForm(false)}
                  className="px-4 py-2 bg-slate-100 text-slate-600 rounded-lg text-sm hover:bg-slate-200"
                >Annuler</button>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}
