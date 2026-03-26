import React from 'react';
import { Button } from '../../components/ui/button';
import { Check, X, Clock, ChevronDown } from 'lucide-react';
import { FileEdit } from 'lucide-react';
import { formatDateTimeFr } from '../../utils/dateFormat';

export default function ModificationProposals({
  activeProposal,
  respondingProposal, onRespondProposal, onCancelProposal,
  proposalHistory,
  showHistory, setShowHistory,
}) {
  return (
    <>
      {/* Active Proposal Banner */}
      {activeProposal && activeProposal.status === 'pending' && (
        <div className="bg-blue-50 border-2 border-blue-300 rounded-lg p-6 mt-6" data-testid="active-proposal-banner">
          <div className="flex items-center gap-2 mb-3">
            <FileEdit className="w-5 h-5 text-blue-600" />
            <h2 className="font-semibold text-blue-900">Modification en cours</h2>
            <span className="ml-auto text-xs bg-blue-200 text-blue-800 px-2 py-0.5 rounded-full">
              {activeProposal.proposed_by?.role === 'organizer' ? 'Par vous' : `Par ${activeProposal.proposed_by?.name}`}
            </span>
          </div>

          <div className="grid sm:grid-cols-2 gap-3 mb-4">
            {Object.entries(activeProposal.changes || {}).map(([field, newVal]) => {
              const oldVal = activeProposal.original_values?.[field];
              const labels = { start_datetime: 'Date/Heure', duration_minutes: 'Durée', location: 'Lieu', meeting_provider: 'Visio', appointment_type: 'Type' };
              const formatVal = (f, v) => {
                if (f === 'start_datetime') return formatDateTimeFr(v);
                if (f === 'duration_minutes') return `${v} min`;
                if (f === 'appointment_type') return v === 'physical' ? 'En personne' : 'Visio';
                return v || '—';
              };
              return (
                <div key={field} className="bg-white rounded p-3 border border-blue-200">
                  <p className="text-xs font-semibold text-slate-500 mb-1">{labels[field] || field}</p>
                  <p className="text-sm text-red-600 line-through">{formatVal(field, oldVal)}</p>
                  <p className="text-sm text-emerald-700 font-semibold">{formatVal(field, newVal)}</p>
                </div>
              );
            })}
          </div>

          <div className="mb-4">
            <p className="text-sm font-medium text-slate-700 mb-2">Réponses</p>
            {activeProposal.organizer_response?.status === 'pending' && (
              <div className="flex items-center gap-2 text-sm mb-1">
                <Clock className="w-4 h-4 text-amber-500" />
                <span className="text-slate-700">Organisateur</span>
                <span className="text-amber-600 font-medium">En attente</span>
              </div>
            )}
            {activeProposal.organizer_response?.status === 'auto_accepted' && (
              <div className="flex items-center gap-2 text-sm mb-1">
                <Check className="w-4 h-4 text-emerald-500" />
                <span className="text-slate-700">Organisateur</span>
                <span className="text-emerald-600 font-medium">Accepté (auteur)</span>
              </div>
            )}
            {(activeProposal.responses || []).map((r) => (
              <div key={r.participant_id} className="flex items-center gap-2 text-sm mb-1">
                {r.status === 'pending' && <Clock className="w-4 h-4 text-amber-500" />}
                {r.status === 'accepted' && <Check className="w-4 h-4 text-emerald-500" />}
                {r.status === 'rejected' && <X className="w-4 h-4 text-red-500" />}
                <span className="text-slate-700">{r.first_name} {r.last_name}</span>
                <span className={`font-medium ${r.status === 'pending' ? 'text-amber-600' : r.status === 'accepted' ? 'text-emerald-600' : 'text-red-600'}`}>
                  {r.status === 'pending' ? 'En attente' : r.status === 'accepted' ? 'Accepté' : 'Refusé'}
                </span>
              </div>
            ))}
          </div>

          {activeProposal.proposed_by?.role === 'participant' && activeProposal.organizer_response?.status === 'pending' && (
            <div className="flex gap-2" data-testid="organizer-respond-proposal">
              <Button size="sm" onClick={() => onRespondProposal(activeProposal.proposal_id, 'accept')} disabled={respondingProposal} data-testid="accept-proposal-btn">
                <Check className="w-4 h-4 mr-1" /> Accepter
              </Button>
              <Button size="sm" variant="outline" className="text-red-600 border-red-300 hover:bg-red-50" onClick={() => onRespondProposal(activeProposal.proposal_id, 'reject')} disabled={respondingProposal} data-testid="reject-proposal-btn">
                <X className="w-4 h-4 mr-1" /> Refuser
              </Button>
            </div>
          )}

          {activeProposal.proposed_by?.role === 'organizer' && (
            <Button size="sm" variant="ghost" className="text-slate-500 mt-2" onClick={() => onCancelProposal(activeProposal.proposal_id)} data-testid="cancel-active-proposal-btn">
              Annuler cette proposition
            </Button>
          )}

          <p className="text-xs text-slate-400 mt-3">
            Expire le {formatDateTimeFr(activeProposal.expires_at)}
          </p>
        </div>
      )}

      {/* Proposal History */}
      {proposalHistory.length > 0 && (
        <div className="mt-4 px-4 pb-4">
          <button onClick={() => setShowHistory(!showHistory)} className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700" data-testid="toggle-proposal-history">
            <ChevronDown className={`w-4 h-4 transition-transform ${showHistory ? 'rotate-180' : ''}`} />
            Historique des modifications ({proposalHistory.length})
          </button>
          {showHistory && (
            <div className="mt-2 space-y-2">
              {proposalHistory.filter(p => p.status !== 'pending').map(p => (
                <div key={p.proposal_id} className="bg-white border border-slate-200 rounded p-3 text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      p.status === 'accepted' ? 'bg-emerald-100 text-emerald-700' :
                      p.status === 'rejected' ? 'bg-red-100 text-red-700' :
                      p.status === 'expired' ? 'bg-slate-100 text-slate-500' :
                      'bg-amber-100 text-amber-700'
                    }`}>
                      {p.status === 'accepted' ? 'Accepté' : p.status === 'rejected' ? 'Refusé' : p.status === 'expired' ? 'Expiré' : 'Annulé'}
                    </span>
                    <span className="text-slate-500">par {p.proposed_by?.name || p.proposed_by?.role}</span>
                    <span className="text-slate-400 ml-auto text-xs">{formatDateTimeFr(p.created_at)}</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(p.changes || {}).map(([f]) => (
                      <span key={f} className="text-xs bg-slate-100 px-2 py-0.5 rounded">
                        {f === 'start_datetime' ? 'Date' : f === 'duration_minutes' ? 'Durée' : f === 'location' ? 'Lieu' : f}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
}
