import React from 'react';
import { Button } from '../../components/ui/button';
import { Check, X, Clock, FileEdit, Zap, ArrowRight, UserCheck } from 'lucide-react';
import { formatDateTimeFr } from '../../utils/dateFormat';

// ── Shared helpers ──

const CHANGE_LABELS = { start_datetime: 'Date/Heure', duration_minutes: 'Durée', location: 'Lieu', meeting_provider: 'Visio', appointment_type: 'Type' };
const PROVIDER_LABELS = { zoom: 'Zoom', teams: 'Teams', meet: 'Google Meet', external: 'Externe' };

function formatVal(f, v) {
  if (f === 'start_datetime') return formatDateTimeFr(v);
  if (f === 'duration_minutes') return `${v} min`;
  if (f === 'appointment_type') return v === 'physical' ? 'En personne' : 'Visio';
  if (f === 'meeting_provider') return PROVIDER_LABELS[v] || v || '—';
  return v || '—';
}

function computeVoteProgress(proposal) {
  const responses = proposal?.responses || [];
  const orgResp = proposal?.organizer_response || {};
  let total = responses.length;
  let accepted = 0;
  responses.forEach(r => { if (r.status === 'accepted') accepted++; });
  if (orgResp.status === 'auto_accepted') { total++; accepted++; }
  else if (['pending', 'accepted', 'rejected'].includes(orgResp.status)) {
    total++;
    if (orgResp.status === 'accepted') accepted++;
  }
  return { accepted, total, pct: total > 0 ? Math.round((accepted / total) * 100) : 0 };
}

const STATUS_CONFIG = {
  accepted:     { label: 'Accepté',  dot: 'bg-emerald-500', badge: 'bg-emerald-100 text-emerald-700' },
  auto_applied: { label: 'Appliqué (direct)', dot: 'bg-emerald-500', badge: 'bg-emerald-100 text-emerald-700' },
  rejected:     { label: 'Refusé',   dot: 'bg-red-500',     badge: 'bg-red-100 text-red-700' },
  expired:      { label: 'Expiré',   dot: 'bg-slate-400',   badge: 'bg-slate-100 text-slate-500' },
  cancelled:    { label: 'Annulé',   dot: 'bg-slate-400',   badge: 'bg-amber-100 text-amber-700' },
  pending:      { label: 'En cours', dot: 'bg-blue-500',    badge: 'bg-blue-100 text-blue-700' },
};

// ── P2.2: Vote Progress Bar ──

function VoteProgressBar({ proposal, className = '' }) {
  const { accepted, total, pct } = computeVoteProgress(proposal);
  if (total === 0) return null;
  return (
    <div className={`${className}`} data-testid="vote-progress-bar">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs font-medium text-slate-600 flex items-center gap-1.5">
          <UserCheck className="w-3.5 h-3.5" />
          <span className="font-semibold">{accepted}</span>/{total} validé{accepted !== 1 ? 's' : ''}
        </span>
        <span className="text-xs text-slate-400 font-medium">{pct}%</span>
      </div>
      <div className="w-full bg-slate-100 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all duration-500 ${
            pct === 100 ? 'bg-emerald-500' : pct > 0 ? 'bg-amber-400' : 'bg-slate-200'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ── Responder row (shared between active banner and history) ──

function ResponderRow({ label, status }) {
  const icon = status === 'pending'
    ? <Clock className="w-3.5 h-3.5 text-amber-500" />
    : ['accepted', 'auto_accepted'].includes(status)
      ? <Check className="w-3.5 h-3.5 text-emerald-500" />
      : <X className="w-3.5 h-3.5 text-red-500" />;
  const statusLabel = status === 'pending' ? 'En attente'
    : status === 'auto_accepted' ? 'Accepté (auteur)'
    : status === 'accepted' ? 'Accepté' : 'Refusé';
  const color = status === 'pending' ? 'text-amber-600'
    : ['accepted', 'auto_accepted'].includes(status) ? 'text-emerald-600' : 'text-red-600';

  return (
    <div className="flex items-center gap-2 text-sm">
      {icon}
      <span className="text-slate-700">{label}</span>
      <span className={`font-medium ${color}`}>{statusLabel}</span>
    </div>
  );
}

// ── P2.1: Timeline History Entry ──

function TimelineEntry({ proposal, isLast }) {
  const cfg = STATUS_CONFIG[proposal.status] || STATUS_CONFIG.pending;
  const isDirect = proposal.mode === 'direct' || proposal.status === 'auto_applied';
  const { accepted, total } = computeVoteProgress(proposal);

  return (
    <div className="relative flex gap-4" data-testid={`history-entry-${proposal.proposal_id}`}>
      {/* Vertical line + dot */}
      <div className="flex flex-col items-center flex-shrink-0 w-5">
        <div className={`w-3 h-3 rounded-full ${cfg.dot} ring-2 ring-white z-10 mt-1`} />
        {!isLast && <div className="w-0.5 flex-1 bg-slate-200 mt-1" />}
      </div>

      {/* Content */}
      <div className={`flex-1 pb-5 ${isLast ? '' : ''}`}>
        {/* Header: status + date */}
        <div className="flex items-center flex-wrap gap-2 mb-2">
          <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${cfg.badge}`}>{cfg.label}</span>
          {isDirect && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-blue-50 text-blue-600 border border-blue-100">
              <Zap className="w-3 h-3" /> Direct
            </span>
          )}
          <span className="text-[11px] text-slate-400 ml-auto">{formatDateTimeFr(proposal.created_at)}</span>
        </div>

        {/* Proposer */}
        <p className="text-xs text-slate-500 mb-2">
          Par <span className="font-medium text-slate-700">{proposal.proposed_by?.name || proposal.proposed_by?.role}</span>
          {proposal.proposed_by?.role === 'organizer' ? ' (organisateur)' : ' (participant)'}
        </p>

        {/* Changes: old → new */}
        <div className="grid sm:grid-cols-2 gap-2 mb-2">
          {Object.entries(proposal.changes || {}).map(([field, newVal]) => {
            const oldVal = proposal.original_values?.[field];
            return (
              <div key={field} className="bg-slate-50 rounded-lg px-3 py-2 border border-slate-100">
                <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-0.5">{CHANGE_LABELS[field] || field}</p>
                <div className="flex items-center gap-1.5 text-xs">
                  <span className="text-red-500 line-through">{formatVal(field, oldVal)}</span>
                  <ArrowRight className="w-3 h-3 text-slate-300 flex-shrink-0" />
                  <span className="text-emerald-700 font-semibold">{formatVal(field, newVal)}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Responses (only for non-direct proposals) */}
        {!isDirect && (proposal.responses?.length > 0 || proposal.organizer_response) && (
          <div className="bg-white border border-slate-100 rounded-lg p-2.5 space-y-1">
            <div className="flex items-center justify-between mb-1">
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Votes</p>
              <span className="text-[11px] font-medium text-slate-400">{accepted}/{total} validé{accepted !== 1 ? 's' : ''}</span>
            </div>
            {proposal.organizer_response && proposal.organizer_response.status !== 'auto_accepted' && (
              <ResponderRow label="Organisateur" status={proposal.organizer_response.status} />
            )}
            {proposal.organizer_response?.status === 'auto_accepted' && (
              <ResponderRow label="Organisateur" status="auto_accepted" />
            )}
            {(proposal.responses || []).map(r => (
              <ResponderRow key={r.participant_id} label={`${r.first_name || ''} ${r.last_name || ''}`.trim() || r.email || 'Participant'} status={r.status} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Component ──

export default function ModificationProposals({
  activeProposal,
  respondingProposal, onRespondProposal, onCancelProposal,
  proposalHistory,
  showHistory, setShowHistory,
  viewerParticipantId,
  isOrganizer,
}) {
  const viewerMustRespond = (() => {
    if (!activeProposal || activeProposal.status !== 'pending') return false;
    if (isOrganizer && activeProposal.organizer_response?.status === 'pending') return true;
    if (viewerParticipantId) {
      const myResp = (activeProposal.responses || []).find(r => r.participant_id === viewerParticipantId);
      if (myResp?.status === 'pending') return true;
    }
    return false;
  })();

  const viewerIsProposer = (() => {
    if (!activeProposal || activeProposal.status !== 'pending') return false;
    if (isOrganizer && activeProposal.proposed_by?.role === 'organizer') return true;
    if (viewerParticipantId && activeProposal.proposed_by?.participant_id === viewerParticipantId) return true;
    return false;
  })();

  return (
    <>
      {/* ━━━ Active Proposal Banner ━━━ */}
      {activeProposal && activeProposal.status === 'pending' && (
        <div className={`${viewerMustRespond ? 'bg-amber-50 border-amber-300' : 'bg-blue-50 border-blue-300'} border-2 rounded-lg p-6 mt-6`} data-testid="active-proposal-banner">
          <div className="flex items-center gap-2 mb-3">
            <FileEdit className={`w-5 h-5 ${viewerMustRespond ? 'text-amber-600' : 'text-blue-600'}`} />
            <h2 className={`font-semibold ${viewerMustRespond ? 'text-amber-900' : 'text-blue-900'}`}>
              {viewerMustRespond ? 'Modification demandée — Action requise' : 'Modification demandée'}
            </h2>
            <span className="ml-auto text-xs bg-slate-200 text-slate-700 px-2 py-0.5 rounded-full">
              Par {activeProposal.proposed_by?.name || activeProposal.proposed_by?.role}
              {activeProposal.proposed_by?.role === 'organizer' ? ' (organisateur)' : ' (participant)'}
            </span>
          </div>

          {/* Changes grid */}
          <div className="grid sm:grid-cols-2 gap-3 mb-4">
            {Object.entries(activeProposal.changes || {}).map(([field, newVal]) => {
              const oldVal = activeProposal.original_values?.[field];
              return (
                <div key={field} className={`bg-white rounded p-3 border ${viewerMustRespond ? 'border-amber-200' : 'border-blue-200'}`}>
                  <p className="text-xs font-semibold text-slate-500 mb-1">{CHANGE_LABELS[field] || field}</p>
                  <p className="text-sm text-red-600 line-through">{formatVal(field, oldVal)}</p>
                  <p className="text-sm text-emerald-700 font-semibold">{formatVal(field, newVal)}</p>
                </div>
              );
            })}
          </div>

          {/* P2.2: Vote progress bar */}
          <VoteProgressBar proposal={activeProposal} className="mb-4" />

          {/* Individual responses */}
          <div className="mb-4 space-y-1">
            <p className="text-sm font-medium text-slate-700 mb-2">Réponses</p>
            {activeProposal.organizer_response && (
              <ResponderRow
                label="Organisateur"
                status={activeProposal.organizer_response.status}
              />
            )}
            {(activeProposal.responses || []).map((r) => (
              <ResponderRow
                key={r.participant_id}
                label={`${r.first_name || ''} ${r.last_name || ''}`.trim() || r.email || 'Participant'}
                status={r.status}
              />
            ))}
          </div>

          {/* CTA: respond */}
          {viewerMustRespond && (
            <div className="flex gap-2" data-testid="respond-proposal-actions">
              <Button size="sm" onClick={() => onRespondProposal(activeProposal.proposal_id, 'accept')} disabled={respondingProposal} data-testid="accept-proposal-btn">
                <Check className="w-4 h-4 mr-1" /> Accepter
              </Button>
              <Button size="sm" variant="outline" className="text-red-600 border-red-300 hover:bg-red-50" onClick={() => onRespondProposal(activeProposal.proposal_id, 'reject')} disabled={respondingProposal} data-testid="reject-proposal-btn">
                <X className="w-4 h-4 mr-1" /> Refuser
              </Button>
            </div>
          )}

          {/* CTA: cancel */}
          {viewerIsProposer && onCancelProposal && (
            <Button size="sm" variant="ghost" className="text-slate-500 mt-2" onClick={() => onCancelProposal(activeProposal.proposal_id)} data-testid="cancel-active-proposal-btn">
              Annuler cette proposition
            </Button>
          )}

          <p className="text-xs text-slate-400 mt-3">
            Expire le {formatDateTimeFr(activeProposal.expires_at)}
          </p>
        </div>
      )}

      {/* ━━━ P2.1: Timeline History ━━━ */}
      {proposalHistory.length > 0 && (
        <div className="px-4 pb-4 pt-2" data-testid="proposal-history-timeline">
          {proposalHistory.filter(p => p.status !== 'pending').length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-3">Aucune modification passée</p>
          ) : (
            <div className="mt-1">
              {proposalHistory.filter(p => p.status !== 'pending').map((p, idx, arr) => (
                <TimelineEntry key={p.proposal_id} proposal={p} isLast={idx === arr.length - 1} />
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
}
