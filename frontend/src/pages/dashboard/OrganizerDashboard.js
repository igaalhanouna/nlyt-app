import React, { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useWorkspace } from '../../contexts/WorkspaceContext';
import { useAuth } from '../../contexts/AuthContext';
import { appointmentAPI, walletAPI, externalEventsAPI, invitationAPI, modificationAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../components/ui/tabs';
import {
  CalendarPlus, Calendar, Users, MapPin, Video,
  Trash2, Check, X, Clock, Building2, ChevronDown, Plus, Ban,
  ShieldCheck, CreditCard, History, Play, AlertTriangle, Bell,
  Flame, Shield, Euro, Eye, Heart,
  UserCheck, Mail, ChevronRight, CheckCircle, LogOut, FileEdit, Search
} from 'lucide-react';
import { toast } from 'sonner';
import { formatDateTimeCompactFr, parseUTC } from '../../utils/dateFormat';
import AppNavbar from '../../components/AppNavbar';
import CalendarSyncPanel from './CalendarSyncPanel';
import ExternalEventCard from './ExternalEventCard';
import { useCalendarAutoSync } from '../../hooks/useCalendarAutoSync';
import { useScrollRestore } from '../../hooks/useScrollRestore';

// ── Helpers ──

function fmtEuro(amount) {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', minimumFractionDigits: 0 }).format(amount || 0);
}

function getTemporalBadge(item, now) {
  const aptStatus = item.appointment_status || item.status;
  if (aptStatus === 'cancelled') return { key: 'cancelled', label: 'Annulé', className: 'bg-red-100 text-red-800' };
  if (aptStatus === 'pending_organizer_guarantee') return { key: 'pending_guarantee', label: 'Garantie en attente', className: 'bg-amber-100 text-amber-800' };
  if (aptStatus === 'draft') return { key: 'draft', label: 'Brouillon', className: 'bg-slate-100 text-slate-800' };

  const start = parseUTC(item.starts_at);
  if (!start) return { key: 'past', label: 'Terminé', className: 'bg-slate-100 text-slate-600' };
  const end = new Date(start.getTime() + (item.duration_minutes || 0) * 60000);
  if (now >= start && now < end) return { key: 'ongoing', label: 'En cours', className: 'bg-blue-100 text-blue-800' };
  if (end < now) return { key: 'past', label: 'Terminé', className: 'bg-slate-100 text-slate-600' };
  return { key: 'active', label: 'Actif', className: 'bg-emerald-100 text-emerald-800' };
}

function getParticipantStatusBadge(status) {
  switch (status) {
    case 'invited': return { label: 'En attente', className: 'bg-amber-100 text-amber-800' };
    case 'accepted':
    case 'accepted_guaranteed': return { label: 'Confirmé', className: 'bg-emerald-100 text-emerald-800' };
    case 'accepted_pending_guarantee': return { label: 'Garantie en attente', className: 'bg-amber-100 text-amber-800' };
    case 'declined': return { label: 'Refusé', className: 'bg-red-100 text-red-800' };
    case 'cancelled_by_participant':
    case 'guarantee_released': return { label: 'Participation annulée', className: 'bg-orange-100 text-orange-800' };
    default: return { label: status, className: 'bg-slate-100 text-slate-600' };
  }
}

const RISK_CONFIG = {
  high:     { label: 'Risque élevé', className: 'bg-red-100 text-red-700 border-red-200', icon: AlertTriangle },
  medium:   { label: 'À surveiller', className: 'bg-amber-50 text-amber-700 border-amber-200', icon: Clock },
  secured:  { label: 'Sécurisé', className: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: Shield },
};

function getRiskFromItem(item, now) {
  if (item.role !== 'organizer') return null;
  const start = parseUTC(item.starts_at);
  if (!start) return 'secured';
  const total = item.participants_count || 0;
  if (total === 0) return 'secured';
  const hoursUntil = (start - now) / 3600000;
  if (hoursUntil <= 0) return 'secured';
  const accepted = item.accepted_count || 0;
  const pending = item.pending_count || 0;
  if (accepted === total) return 'secured';
  if (hoursUntil <= 24 && pending > 0) return 'high';
  if (hoursUntil <= 48 || pending > 0) return 'medium';
  return 'secured';
}

// ── Sub-components ──

function HeaderStats({ user, counts }) {
  return (
    <div className="mb-8">
      <h2 className="text-2xl font-bold text-slate-900 mb-1" data-testid="dashboard-title">
        Bonjour, {user?.first_name}
      </h2>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-slate-500 mt-1" data-testid="dashboard-stats">
        <span><span className="font-semibold text-slate-700">{counts.upcoming + counts.action_required}</span> engagement{(counts.upcoming + counts.action_required) !== 1 ? 's' : ''} à venir</span>
        {counts.action_required > 0 && (
          <>
            <span className="text-slate-300">|</span>
            <span><span className="font-semibold text-red-600">{counts.action_required}</span> action{counts.action_required !== 1 ? 's' : ''} requise{counts.action_required !== 1 ? 's' : ''}</span>
          </>
        )}
      </div>
    </div>
  );
}

function ImpactCard({ totalCharityCents }) {
  const amount = fmtEuro((totalCharityCents || 0) / 100);
  return (
    <Link to="/mes-resultats" className="block mb-6 bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-3 hover:bg-emerald-100/60 transition-colors" data-testid="impact-card">
      <div className="flex items-center gap-2.5">
        <Heart className="w-4 h-4 text-red-500 fill-red-500 flex-shrink-0" />
        <span className="text-sm font-medium text-emerald-700">Vos gestes solidaires reversés à des associations</span>
        <span className="ml-auto text-sm font-bold text-emerald-800 flex-shrink-0" data-testid="impact-amount">{amount}</span>
        <ChevronRight className="w-4 h-4 text-emerald-400 flex-shrink-0" />
      </div>
    </Link>
  );
}

// ── Action Required Section ──
function ActionCard({ item, onRemind, onAccept, onDecline, onCancel, onDelete, onGuarantee, now, onNavigate, confirmCancelId, onCancelConfirmReset }) {
  const isParticipant = item.role === 'participant';
  const isOrgAlert = !isParticipant && item.action_required;
  const needsOrgGuarantee = !isParticipant && item.needs_organizer_guarantee;

  // Block organizer cancel if appointment has started
  const actionStartDt = parseUTC(item.starts_at);
  const isActionStarted = actionStartDt && now >= actionStartDt;

  const detailLink = `/appointments/${item.appointment_id}`;
  const navState = { fromTab: 'action_required' };

  return (
    <div className="bg-white border border-red-100 rounded-lg transition-all hover:border-red-200 hover:shadow-sm" data-testid={`action-card-${item.appointment_id}`}>
      {/* Clickable content area — navigates to detail */}
      <Link to={detailLink} state={navState} className="block p-4 pb-2" onClick={onNavigate}>
        {/* Role label */}
        <div className="flex items-center gap-2 mb-2">
          <span className={`text-[11px] font-medium ${isParticipant ? 'text-blue-600' : 'text-slate-500'}`} data-testid={`role-label-${item.appointment_id}`}>
            {isParticipant ? `Invitation de ${item.counterparty_name}` : 'Créé par vous'}
          </span>
          {item.pending_label && (
            <span className={`ml-auto text-xs font-semibold ${isParticipant ? 'text-blue-600' : 'text-amber-600'}`}>{item.pending_label}</span>
          )}
        </div>

        {/* Title */}
        <p className="font-semibold text-sm leading-tight text-slate-900 mb-2.5">{item.title}</p>

        {/* Metadata grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5 text-xs text-slate-600 mb-3">
          <span className="flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            {formatDateTimeCompactFr(item.starts_at)}
          </span>
          <span className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            {item.duration_minutes} min
          </span>
          <span className="flex items-center gap-1.5">
            {item.appointment_type === 'physical'
              ? <><MapPin className="w-3.5 h-3.5 text-slate-400" /> {item.location_display_name || item.location || 'Physique'}</>
              : <><Video className="w-3.5 h-3.5 text-slate-400" /> {item.meeting_provider || 'Visioconférence'}</>
            }
          </span>
          {item.penalty_amount > 0 && (
            <span className="flex items-center gap-1.5">
              <CreditCard className="w-3.5 h-3.5 text-slate-400" />
              Garantie : {fmtEuro(item.penalty_amount)}
            </span>
          )}
        </div>

        {/* Engagement rules */}
        {(item.tolerated_delay_minutes > 0 || item.cancellation_deadline_hours > 0) && (
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500 mb-3 pb-3 border-b border-slate-100">
            {item.tolerated_delay_minutes > 0 && (
              <span>Tolérance retard : {item.tolerated_delay_minutes} min</span>
            )}
            {item.cancellation_deadline_hours > 0 && (
              <span>Annulation possible jusqu'à {item.cancellation_deadline_hours}h avant</span>
            )}
          </div>
        )}
      </Link>

      {/* CTAs — outside the Link to avoid nested <a> */}
      <div className="flex items-center gap-2 flex-wrap px-4 pb-3 pt-1">
        {needsOrgGuarantee ? (
          <>
            <Button size="sm" className="h-11 md:h-8 text-xs flex-1 md:flex-none bg-amber-600 hover:bg-amber-700 text-white" onClick={() => onGuarantee(item)} data-testid={`guarantee-btn-${item.appointment_id}`}>
              <CreditCard className="w-3.5 h-3.5 mr-1.5" /> Garantir le RDV
            </Button>
            <Button size="sm" variant="outline" className="h-11 md:h-8 text-xs flex-1 md:flex-none border-red-200 text-red-600 hover:bg-red-50" onClick={() => onDelete(item)} data-testid={`delete-action-${item.appointment_id}`}>
              <Trash2 className="w-3.5 h-3.5 mr-1.5" /> Supprimer
            </Button>
          </>
        ) : isParticipant && item.status === 'invited' ? (
          <>
            <Button size="sm" className="h-11 md:h-8 text-xs flex-1 md:flex-none bg-emerald-600 hover:bg-emerald-700 text-white" onClick={() => onAccept(item)} data-testid={`accept-btn-${item.appointment_id}`}>
              <Check className="w-3.5 h-3.5 mr-1.5" /> Accepter
            </Button>
            <Button size="sm" variant="outline" className="h-11 md:h-8 text-xs flex-1 md:flex-none border-red-200 text-red-600 hover:bg-red-50" onClick={() => onDecline(item)} data-testid={`decline-btn-${item.appointment_id}`}>
              <X className="w-3.5 h-3.5 mr-1.5" /> Refuser
            </Button>
          </>
        ) : isParticipant && item.participant_status === 'accepted_pending_guarantee' ? (
          <>
            <Link to={detailLink} state={navState} className="flex-1 md:flex-none" onClick={onNavigate}>
              <Button size="sm" className="h-11 md:h-8 text-xs w-full bg-amber-600 hover:bg-amber-700 text-white" data-testid={`finalize-guarantee-btn-${item.appointment_id}`}>
                <CreditCard className="w-3.5 h-3.5 mr-1.5" /> Finaliser ma garantie
              </Button>
            </Link>
            <Button size="sm" variant="outline" className="h-11 md:h-8 text-xs flex-1 md:flex-none border-red-200 text-red-600 hover:bg-red-50" onClick={() => onDecline(item)} data-testid={`decline-guarantee-btn-${item.appointment_id}`}>
              <X className="w-3.5 h-3.5 mr-1.5" /> Refuser
            </Button>
          </>
        ) : isOrgAlert ? (
          <>
            <Button size="sm" className="h-11 md:h-8 text-xs flex-1 md:flex-none bg-amber-600 hover:bg-amber-700 text-white" onClick={() => onRemind(item)} data-testid={`remind-action-${item.appointment_id}`}>
              <Bell className="w-3.5 h-3.5 mr-1.5" /> Relancer
            </Button>
            {!isActionStarted && (
              confirmCancelId === item.appointment_id ? (
                <div className="flex items-center gap-1.5 flex-1 md:flex-none">
                  <span className="text-xs text-red-600 font-medium">Annuler ?</span>
                  <button onClick={() => onCancel(item)} className="px-2 py-1 text-xs font-bold text-white bg-red-600 rounded hover:bg-red-700 transition-colors" data-testid={`confirm-cancel-${item.appointment_id}`}>Oui</button>
                  <button onClick={onCancelConfirmReset} className="px-2 py-1 text-xs font-medium text-slate-600 bg-slate-100 rounded hover:bg-slate-200 transition-colors" data-testid={`deny-cancel-${item.appointment_id}`}>Non</button>
                </div>
              ) : (
                <Button size="sm" variant="outline" className="h-11 md:h-8 text-xs flex-1 md:flex-none border-red-200 text-red-600 hover:bg-red-50" onClick={() => onCancel(item)} data-testid={`cancel-action-${item.appointment_id}`}>
                  <Ban className="w-3.5 h-3.5 mr-1.5" /> Annuler
                </Button>
              )
            )}
          </>
        ) : (
          <Button size="sm" variant="outline" className="h-11 md:h-8 text-xs flex-1 md:flex-none border-red-200 text-red-600 hover:bg-red-50" onClick={() => onRemind(item)} data-testid={`remind-action-${item.appointment_id}`}>
            <Bell className="w-3.5 h-3.5 mr-1.5" /> Relancer
          </Button>
        )}

        {/* Delete/Trash icon for organizer — aligned with TimelineCard */}
        {!isParticipant && (
          <button
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDelete(item); }}
            className="ml-auto flex items-center justify-center w-11 h-11 md:w-auto md:h-auto md:p-1.5 text-slate-300 hover:text-rose-600 hover:bg-rose-50 rounded-lg md:rounded transition-colors"
            title="Supprimer"
            data-testid={`delete-action-${item.appointment_id}`}
          >
            <Trash2 className="w-4 h-4 md:w-3.5 md:h-3.5" />
          </button>
        )}
        {/* Quit action for participant — aligned with TimelineCard */}
        {isParticipant && item.status !== 'invited' && item.participant_status !== 'accepted_pending_guarantee' && !isActionStarted && (
          <Button
            size="sm"
            variant="outline"
            className="h-11 md:h-8 text-xs flex-1 md:flex-none border-red-200 text-red-600 hover:bg-red-50 ml-auto"
            onClick={() => onDecline(item)}
            data-testid={`quit-action-${item.appointment_id}`}
          >
            <LogOut className="w-3.5 h-3.5 mr-1.5" /> Quitter
          </Button>
        )}
      </div>
    </div>
  );
}

// ── Modification change summary helper ──
function formatChangeSummary(mod) {
  if (!mod?.changes) return '';
  const parts = [];
  const c = mod.changes;
  const o = mod.original_values || {};

  if (c.start_datetime) {
    const newDt = new Date(c.start_datetime);
    const oldDt = o.start_datetime ? new Date(o.start_datetime) : null;
    const dateFmt = { day: 'numeric', month: 'short' };
    const timeFmt = { hour: '2-digit', minute: '2-digit' };

    const newDate = newDt.toLocaleDateString('fr-FR', dateFmt);
    const oldDate = oldDt ? oldDt.toLocaleDateString('fr-FR', dateFmt) : '—';
    const newTime = newDt.toLocaleTimeString('fr-FR', timeFmt);
    const oldTime = oldDt ? oldDt.toLocaleTimeString('fr-FR', timeFmt) : '—';

    const dateChanged = oldDate !== newDate;
    const timeChanged = oldTime !== newTime;

    if (dateChanged) parts.push(`Date : ${oldDate} → ${newDate}`);
    if (timeChanged) parts.push(`Horaire : ${oldTime} → ${newTime}`);
    if (!dateChanged && !timeChanged) parts.push(`Date/Heure modifiée`);
  }
  if (c.duration_minutes) parts.push(`Durée : ${o.duration_minutes || '—'} → ${c.duration_minutes} min`);
  if (c.location) {
    const oldLoc = o.location || '—';
    const newLoc = c.location;
    parts.push(`Lieu : ${oldLoc} → ${newLoc}`);
  }
  if (c.meeting_provider) {
    const providerLabels = { zoom: 'Zoom', teams: 'Teams', meet: 'Google Meet', external: 'Externe' };
    const oldP = providerLabels[o.meeting_provider] || o.meeting_provider || '—';
    const newP = providerLabels[c.meeting_provider] || c.meeting_provider;
    parts.push(`Visio : ${oldP} → ${newP}`);
  }
  if (c.appointment_type) parts.push(c.appointment_type === 'video' ? 'Passage en visio' : 'Passage en présentiel');
  return parts.join(' · ') || 'Modification demandée';
}

// ── Timeline Card (unified for organizer + participant) ──
function TimelineCard({ item, isPast, onDelete, onRemind, onQuit, onDecline, onGuarantee, now, fromTab, onNavigate, hasModification, modActionRequired, modificationData, confirmQuitId, onQuitConfirmReset }) {
  const isParticipant = item.role === 'participant';
  const badge = getTemporalBadge(item, now);
  const isOngoing = badge.key === 'ongoing';

  // Risk for organizer items only
  const risk = !isPast && !isParticipant ? getRiskFromItem(item, now) : null;
  const riskCfg = risk ? RISK_CONFIG[risk] : null;
  const RiskIcon = riskCfg?.icon;

  // Status badge for participant items
  const pBadge = isParticipant ? getParticipantStatusBadge(item.participant_status || item.status) : null;

  // Progress for organizer
  const total = item.participants_count || 0;
  const accepted = item.accepted_count || 0;
  const pending = item.pending_count || 0;
  const progressPct = total > 0 ? Math.round((accepted / total) * 100) : 100;

  // Participant actions based on exact backend API constraints:
  // - "Annuler" (cancel participation): only for accepted / accepted_guaranteed + future + deadline not passed
  // - "Refuser" (decline): only for invited / accepted_pending_guarantee + future
  const pStatus = item.participant_status;
  const hasToken = !!item.invitation_token;

  // Temporal checks for cancellation
  const startDt = parseUTC(item.starts_at);
  const isStarted = startDt && now >= startDt;
  const deadlineHours = item.cancellation_deadline_hours || 0;
  const cancellationDeadline = deadlineHours > 0 && startDt
    ? new Date(startDt.getTime() - deadlineHours * 3600000)
    : null;
  const isPastCancelDeadline = cancellationDeadline ? now >= cancellationDeadline : false;

  const canQuit = isParticipant && !isPast && !isStarted && !isPastCancelDeadline && hasToken
    && ['accepted', 'accepted_guaranteed'].includes(pStatus);
  const canQuitDisabled = isParticipant && !isPast && !isStarted && isPastCancelDeadline && hasToken
    && ['accepted', 'accepted_guaranteed'].includes(pStatus);
  const canDecline = isParticipant && !isPast && hasToken
    && ['invited', 'accepted_pending_guarantee'].includes(pStatus);

  const detailLink = `/appointments/${item.appointment_id}`;
  const navState = { fromTab: fromTab || (isPast ? 'past' : 'upcoming') };

  return (
    <div
      className={`relative border rounded-lg transition-all ${
        isOngoing ? 'border-blue-300 bg-blue-50/30 ring-1 ring-blue-200'
          : isPast ? 'border-slate-150 bg-slate-50/50 hover:border-slate-300'
          : 'border-slate-200 hover:border-slate-300 hover:shadow-sm'
      }`}
      data-testid={`timeline-card-${item.appointment_id}`}
    >
      <Link to={detailLink} state={navState} className="block p-4 pb-2" onClick={onNavigate}>
        {/* Row 0: Role label + Badges */}
        <div className="flex items-center justify-between gap-2 mb-2">
          <span className={`text-[11px] font-medium ${isParticipant ? 'text-blue-600' : 'text-slate-400'}`} data-testid={`timeline-role-${item.appointment_id}`}>
            {isParticipant ? `Invitation de ${item.counterparty_name}` : 'Créé par vous'}
          </span>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            {modActionRequired && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium rounded-full border bg-amber-50 border-amber-300 text-amber-700" data-testid={`mod-action-badge-${item.appointment_id}`}>
                <FileEdit className="w-3 h-3" />
                Action requise
              </span>
            )}
            {hasModification && !modActionRequired && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium rounded-full border bg-blue-50 border-blue-200 text-blue-600" data-testid={`mod-pending-badge-${item.appointment_id}`}>
                <FileEdit className="w-3 h-3" />
                Modification demandée
              </span>
            )}
            {riskCfg && risk !== 'secured' && (
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium rounded-full border ${riskCfg.className}`}>
                <RiskIcon className="w-3 h-3" />
                {riskCfg.label}
              </span>
            )}
            {isParticipant && pBadge ? (
              <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${pBadge.className}`}>
                {pBadge.label}
              </span>
            ) : (
              <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${badge.className}`}>
                {badge.label}
              </span>
            )}
          </div>
        </div>

        {/* Modification context banner */}
        {(hasModification || modActionRequired) && modificationData && (() => {
          const [a, t] = (modificationData.participants_summary || '0/0').split('/');
          const acc = parseInt(a) || 0;
          const tot = parseInt(t) || 0;
          const pctMod = tot > 0 ? Math.round((acc / tot) * 100) : 0;
          return (
          <div className={`rounded-lg px-3 py-2 mb-2.5 text-xs ${modActionRequired ? 'bg-amber-50 border border-amber-200' : 'bg-blue-50 border border-blue-100'}`} data-testid={`mod-context-${item.appointment_id}`}>
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className={`font-medium truncate ${modActionRequired ? 'text-amber-800' : 'text-blue-700'}`}>
                  {formatChangeSummary(modificationData)}
                </p>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Par {modificationData.proposed_by?.name || modificationData.proposed_by?.role}
                  {modActionRequired ? ' — En attente de votre réponse' : ' — En attente des réponses'}
                </p>
              </div>
              <span className={`flex-shrink-0 ml-3 px-2.5 py-1 rounded-md text-[11px] font-medium cursor-pointer ${modActionRequired ? 'bg-amber-600 text-white hover:bg-amber-700' : 'bg-blue-100 text-blue-700 hover:bg-blue-200'} transition-colors`} data-testid={`mod-cta-${item.appointment_id}`}>
                Voir la demande
              </span>
            </div>
            {/* Mini vote progress */}
            <div className="flex items-center gap-2 mt-1.5" data-testid={`mod-timeline-progress-${item.appointment_id}`}>
              <div className="flex-1 max-w-[100px] bg-white/60 rounded-full h-1.5">
                <div className={`h-1.5 rounded-full transition-all ${pctMod === 100 ? 'bg-emerald-500' : pctMod > 0 ? 'bg-amber-400' : 'bg-slate-200'}`} style={{ width: `${pctMod}%` }} />
              </div>
              <span className="text-[11px] font-medium text-slate-500">{acc}/{tot} validé{acc !== 1 ? 's' : ''}</span>
            </div>
          </div>
          );
        })()}

        {/* Row 1: Title */}
        <h4 className={`font-semibold text-sm leading-tight mb-2.5 ${isPast && !isOngoing ? 'text-slate-500' : 'text-slate-900'}`}>
          {isOngoing && <Play className="w-3.5 h-3.5 inline mr-1 text-blue-600" />}
          {item.title}
          {item.converted_from?.source && (
            <span className={`ml-2 inline-flex items-center text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
              item.converted_from.source === 'google'
                ? 'bg-[#4285F4]/10 text-[#4285F4]'
                : 'bg-[#0078D4]/10 text-[#0078D4]'
            }`}>
              via {item.converted_from.source === 'google' ? 'Google' : 'Outlook'}
            </span>
          )}
        </h4>

        {/* Row 2: Metadata grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5 text-xs text-slate-500 mb-3">
          <span className="flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            {formatDateTimeCompactFr(item.starts_at)}
          </span>
          <span className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            {item.duration_minutes} min
          </span>
          <span className="flex items-center gap-1.5">
            {item.appointment_type === 'physical'
              ? <><MapPin className="w-3.5 h-3.5 text-slate-400" /> <span className="truncate">{item.location_display_name || item.location || 'Physique'}</span></>
              : <><Video className="w-3.5 h-3.5 text-slate-400" /> {item.meeting_provider || 'Visioconférence'}</>
            }
          </span>
          {item.penalty_amount > 0 && (
            <span className="flex items-center gap-1.5 font-medium text-slate-600">
              <CreditCard className="w-3.5 h-3.5 text-slate-400" />
              Garantie : {fmtEuro(item.penalty_amount)}
            </span>
          )}
          {/* Counterparty for organizer */}
          {!isParticipant && item.counterparty_name && item.counterparty_name !== 'Aucun participant' && (
            <span className="flex items-center gap-1.5">
              <Users className="w-3.5 h-3.5 text-slate-400" />
              Avec {item.counterparty_name}
            </span>
          )}
        </div>

        {/* Row 3: Engagement rules (if not past) */}
        {!isPast && (item.tolerated_delay_minutes > 0 || item.cancellation_deadline_hours > 0) && (
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-400 mb-3 pb-2 border-b border-slate-100">
            {item.tolerated_delay_minutes > 0 && (
              <span>Tolérance retard : {item.tolerated_delay_minutes} min</span>
            )}
            {item.cancellation_deadline_hours > 0 && (
              <span>Annulation possible jusqu'à {item.cancellation_deadline_hours}h avant</span>
            )}
          </div>
        )}

        {/* Row 4: Participants + Progress (organizer) or Engagement signal (participant) */}
        {!isParticipant && total > 0 && (
          <div className="space-y-2 mb-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-600 flex items-center gap-1.5">
                <UserCheck className="w-3.5 h-3.5" />
                <span className="font-medium">{accepted}</span>/{total} confirmé{accepted !== 1 ? 's' : ''}
                {pending > 0 && <span className="text-amber-600 ml-1">({pending} en attente)</span>}
              </span>
              <span className="text-slate-400 font-medium">{progressPct}%</span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-1.5">
              <div
                className={`h-1.5 rounded-full transition-all ${
                  progressPct === 100 ? 'bg-emerald-500' : progressPct >= 50 ? 'bg-amber-400' : 'bg-red-400'
                }`}
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>
        )}
        {isParticipant && total > 0 && accepted > 0 && (
          <div className="mb-1">
            <span className="text-xs text-slate-500 flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
              <span className="font-medium text-emerald-600">{accepted}</span> participant{accepted > 1 ? 's' : ''} engagé{accepted > 1 ? 's' : ''}
            </span>
          </div>
        )}

        {/* Pending label for participant */}
        {isParticipant && item.pending_label && (
          <div className="mb-1">
            <span className="text-xs font-medium text-blue-600">{item.pending_label}</span>
          </div>
        )}

        {/* Cancellation banner for organizer */}
        {!isParticipant && item.cancelled_participants_label && (
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-orange-50 border border-orange-200 rounded-md mb-1" data-testid={`cancelled-banner-${item.appointment_id}`}>
            <Ban className="w-3.5 h-3.5 text-orange-500 flex-shrink-0" />
            <span className="text-xs font-medium text-orange-700">{item.cancelled_participants_label}</span>
          </div>
        )}

        {/* Financial badge for past items */}
        {isPast && item.financial_badge && (
          <div className={`flex items-center gap-1.5 text-xs font-medium mt-1 mb-1 ${
            item.financial_badge.type === 'penalty' ? 'text-red-600' :
            item.financial_badge.type === 'compensation' ? 'text-emerald-600' :
            item.financial_badge.type === 'review' ? 'text-amber-600' :
            'text-slate-500'
          }`} data-testid={`financial-badge-${item.appointment_id}`}>
            {item.financial_badge.type === 'penalty' && <AlertTriangle className="w-3 h-3" />}
            {item.financial_badge.type === 'compensation' && <CreditCard className="w-3 h-3" />}
            {item.financial_badge.type === 'review' && <Clock className="w-3 h-3" />}
            {item.financial_badge.type === 'clean' && <CheckCircle className="w-3 h-3" />}
            <span>{item.financial_badge.label}</span>
          </div>
        )}
      </Link>

      {/* Actions row */}
      <div className="flex items-center gap-2 px-4 pb-3 pt-1">
        {/* Organizer guarantee CTA — priority over other actions */}
        {item.needs_organizer_guarantee && !isParticipant && (
          <Button
            size="sm"
            className="h-11 md:h-7 text-xs flex-1 md:flex-none bg-amber-600 hover:bg-amber-700 text-white"
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); onGuarantee(item); }}
            data-testid={`guarantee-timeline-btn-${item.appointment_id}`}
          >
            <CreditCard className="w-3.5 h-3.5 mr-1.5" /> Garantir le RDV
          </Button>
        )}
        <Link to={detailLink} state={navState} className="flex-1 md:flex-none" onClick={onNavigate}>
          <Button size="sm" variant="outline" className="h-11 md:h-7 text-xs w-full md:w-auto" data-testid={`view-details-${item.appointment_id}`}>
            <Eye className="w-3.5 h-3.5 mr-1.5" /> Voir détails
          </Button>
        </Link>
        {!isParticipant && !isPast && pending > 0 && (
          <Button
            size="sm"
            variant="outline"
            className="h-11 md:h-7 text-xs flex-1 md:flex-none border-amber-200 text-amber-700 hover:bg-amber-50"
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); onRemind(item); }}
            data-testid={`remind-btn-${item.appointment_id}`}
          >
            <Bell className="w-3.5 h-3.5 mr-1.5" /> Relancer
          </Button>
        )}
        {canQuit && (
          confirmQuitId === item.appointment_id ? (
            <div className="flex items-center gap-1.5 flex-1 md:flex-none" onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}>
              <span className="text-xs text-red-600 font-medium">Annuler ?</span>
              <button onClick={(e) => { e.preventDefault(); e.stopPropagation(); onQuit(item); }} className="px-2 py-1 text-xs font-bold text-white bg-red-600 rounded hover:bg-red-700 transition-colors" data-testid={`confirm-quit-${item.appointment_id}`}>Oui</button>
              <button onClick={(e) => { e.preventDefault(); e.stopPropagation(); onQuitConfirmReset(); }} className="px-2 py-1 text-xs font-medium text-slate-600 bg-slate-100 rounded hover:bg-slate-200 transition-colors" data-testid={`deny-quit-${item.appointment_id}`}>Non</button>
            </div>
          ) : (
            <Button
              size="sm"
              variant="outline"
              className="h-11 md:h-7 text-xs flex-1 md:flex-none border-red-200 text-red-600 hover:bg-red-50"
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); onQuit(item); }}
              data-testid={`quit-btn-${item.appointment_id}`}
            >
              <LogOut className="w-3.5 h-3.5 mr-1.5" /> Annuler
            </Button>
          )
        )}
        {canQuitDisabled && (
          <span title="Le délai d'annulation est dépassé" className="flex-1 md:flex-none">
            <Button
              size="sm"
              variant="outline"
              className="h-11 md:h-7 text-xs w-full border-slate-200 text-slate-400 cursor-not-allowed"
              disabled
              data-testid={`quit-btn-disabled-${item.appointment_id}`}
            >
              <LogOut className="w-3.5 h-3.5 mr-1.5" /> Annuler
            </Button>
          </span>
        )}
        {canDecline && (
          <Button
            size="sm"
            variant="outline"
            className="h-11 md:h-7 text-xs flex-1 md:flex-none border-red-200 text-red-600 hover:bg-red-50"
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDecline(item); }}
            data-testid={`decline-btn-${item.appointment_id}`}
          >
            <X className="w-3.5 h-3.5 mr-1.5" /> Refuser
          </Button>
        )}
        {!isParticipant && (
          <button
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDelete(item); }}
            className="ml-auto flex items-center justify-center w-11 h-11 md:w-auto md:h-auto md:p-1.5 text-slate-300 hover:text-rose-600 hover:bg-rose-50 rounded-lg md:rounded transition-colors"
            title="Supprimer"
            data-testid={`delete-appointment-${item.appointment_id}`}
          >
            <Trash2 className="w-4 h-4 md:w-3.5 md:h-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}

// ── Main Dashboard ──

export default function OrganizerDashboard() {
  const { user } = useAuth();
  const { currentWorkspace, workspaces, selectWorkspace } = useWorkspace();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Active tab from URL (?tab=upcoming|past|stats), default "upcoming"
  const activeTab = searchParams.get('tab') || 'upcoming';
  const setActiveTab = useCallback((val) => {
    setSearchParams({ tab: val }, { replace: true });
  }, [setSearchParams]);

  // Timeline state
  const [timeline, setTimeline] = useState({ action_required: [], upcoming: [], past: [] });
  const [counts, setCounts] = useState({ action_required: 0, upcoming: 0, past: 0, total: 0 });
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [pastVisible, setPastVisible] = useState(20);
  const { saveScroll } = useScrollRestore('dashboard', !loading);

  const [impactCents, setImpactCents] = useState(0);
  const [deleteModal, setDeleteModal] = useState({ open: false, item: null });
  const [deleting, setDeleting] = useState(false);
  const [confirmCancelId, setConfirmCancelId] = useState(null);
  const [confirmQuitId, setConfirmQuitId] = useState(null);
  const [workspaceDropdownOpen, setWorkspaceDropdownOpen] = useState(false);
  const [responding, setResponding] = useState(null);
  const [allModifications, setAllModifications] = useState([]);

  // External events / calendar import state
  const [importSettings, setImportSettings] = useState(null);
  const [externalEvents, setExternalEvents] = useState([]);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    loadTimeline();
    loadImpact();
    loadImportSettings().then(() => loadExternalEvents());
    loadPendingModifications();
  }, [currentWorkspace]);

  // Handle Stripe return (guarantee_status=success in URL)
  useEffect(() => {
    const guaranteeStatus = searchParams.get('guarantee_status');
    if (guaranteeStatus === 'success') {
      toast.success('Garantie validée ! Votre engagement est maintenant actif.');
      // Clean URL params
      const newParams = new URLSearchParams(searchParams);
      newParams.delete('guarantee_status');
      newParams.delete('session_id');
      newParams.delete('dev_mode');
      setSearchParams(newParams, { replace: true });
      // Refresh timeline to reflect activation
      setTimeout(() => loadTimeline(), 1500);
    } else if (guaranteeStatus === 'cancelled') {
      toast.error('Garantie annulée. Le rendez-vous reste en attente.');
      const newParams = new URLSearchParams(searchParams);
      newParams.delete('guarantee_status');
      setSearchParams(newParams, { replace: true });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Dashboard polling: refresh timeline every 60s when page is visible
  useEffect(() => {
    const poll = () => {
      if (document.hidden) return;
      appointmentAPI.myTimeline().then(res => {
        setTimeline({
          action_required: res.data.action_required || [],
          upcoming: res.data.upcoming || [],
          past: res.data.past || [],
        });
        setCounts(res.data.counts || { action_required: 0, upcoming: 0, past: 0, total: 0 });
      }).catch(() => {});
    };
    const intervalId = setInterval(poll, 60000);
    return () => clearInterval(intervalId);
  }, [currentWorkspace]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadTimeline = async () => {
    setLoading(true);
    try {
      const res = await appointmentAPI.myTimeline();
      setTimeline({
        action_required: res.data.action_required || [],
        upcoming: res.data.upcoming || [],
        past: res.data.past || [],
      });
      setCounts(res.data.counts || { action_required: 0, upcoming: 0, past: 0, total: 0 });
    } catch (error) {
      toast.error('Erreur lors du chargement du dashboard');
    } finally {
      setLoading(false);
    }
  };

  const loadPendingModifications = async () => {
    try {
      const res = await modificationAPI.mine();
      setAllModifications(res.data?.proposals || []);
    } catch { /* non-blocking */ }
  };

  const pendingModifications = allModifications.filter(p => p.status === 'pending');

  // Sets + data for badges and context on timeline cards
  const modActionAptIds = new Set(pendingModifications.filter(p => p.is_action_required).map(p => p.appointment_id));
  const modPendingAptIds = new Set(pendingModifications.map(p => p.appointment_id));
  const modDataByAptId = {};
  pendingModifications.forEach(p => { modDataByAptId[p.appointment_id] = p; });

  const loadImpact = async () => {
    try {
      const res = await walletAPI.getImpact();
      setImpactCents(res.data?.total_charity_cents || 0);
    } catch (_) { /* non-blocking */ }
  };

  // ── Actions ──

  const handleDeleteClick = (item) => {
    setDeleteModal({ open: true, item });
  };

  const handleConfirmDelete = async () => {
    if (!deleteModal.item) return;
    setDeleting(true);
    try {
      await appointmentAPI.delete(deleteModal.item.appointment_id);
      // Remove from all buckets
      const aptId = deleteModal.item.appointment_id;
      setTimeline(prev => ({
        action_required: prev.action_required.filter(i => i.appointment_id !== aptId),
        upcoming: prev.upcoming.filter(i => i.appointment_id !== aptId),
        past: prev.past.filter(i => i.appointment_id !== aptId),
      }));
      toast.success('Engagement supprimé');
      setDeleteModal({ open: false, item: null });
    } catch (error) {
      toast.error('Erreur lors de la suppression');
    } finally {
      setDeleting(false);
    }
  };

  const handleCancelAppointment = async (item) => {
    if (confirmCancelId !== item.appointment_id) { setConfirmCancelId(item.appointment_id); setConfirmQuitId(null); return; }
    setConfirmCancelId(null);
    try {
      await appointmentAPI.cancel(item.appointment_id);
      const aptId = item.appointment_id;
      setTimeline(prev => ({
        action_required: prev.action_required.filter(i => i.appointment_id !== aptId),
        upcoming: prev.upcoming.filter(i => i.appointment_id !== aptId),
        past: [...prev.past, { ...item, appointment_status: 'cancelled' }],
      }));
      setCounts(prev => ({
        ...prev,
        action_required: Math.max(0, prev.action_required - 1),
        past: prev.past + 1,
      }));
      toast.success('Engagement annulé');
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erreur lors de l'annulation");
    }
  };

  const handleRemind = async (item) => {
    try {
      await appointmentAPI.remind(item.appointment_id);
      toast.success('Relance envoyée aux participants en attente');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Erreur lors de la relance');
    }
  };

  const handleQuitParticipation = async (item) => {
    if (!item.invitation_token) return;
    if (confirmQuitId !== item.appointment_id) { setConfirmQuitId(item.appointment_id); setConfirmCancelId(null); return; }
    setConfirmQuitId(null);
    try {
      await invitationAPI.cancelParticipation(item.invitation_token);
      toast.success('Participation annulée');
      await loadTimeline();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Impossible d\'annuler la participation');
    }
  };

  const handleAcceptInvitation = async (item) => {
    if (!item.invitation_token) return;
    setResponding(item.appointment_id);
    try {
      const { data } = await invitationAPI.respond(item.invitation_token, { action: 'accept' });

      if (data.requires_guarantee && data.checkout_url) {
        toast.info('Redirection vers la page de garantie...');
        window.location.href = data.checkout_url;
        return;
      }
      if (data.reused_card) {
        toast.success(data.message || 'Garantie confirmée avec votre carte enregistrée');
      } else {
        toast.success('Invitation acceptée');
      }
      await loadTimeline();
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || 'Erreur lors de l\'acceptation');
    } finally {
      setResponding(null);
    }
  };

  const handleDeclineInvitation = async (item) => {
    if (!item.invitation_token) return;
    setResponding(item.appointment_id);
    try {
      await invitationAPI.respond(item.invitation_token, { action: 'decline' });
      toast.success('Invitation refusée');
      await loadTimeline();
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || 'Erreur lors du refus');
    } finally {
      setResponding(null);
    }
  };

  const handleSelectWorkspace = (workspace) => {
    selectWorkspace(workspace);
    setWorkspaceDropdownOpen(false);
    setLoading(true);
  };

  const handleGuaranteeOrganizer = async (item) => {
    try {
      const { data } = await appointmentAPI.retryGuarantee(item.appointment_id);
      if (data.checkout_url) {
        toast.info('Redirection vers Stripe pour valider votre garantie...');
        window.location.href = data.checkout_url;
        return;
      }
      if (data.status === 'active' && data.activated) {
        toast.success(data.message || 'Garantie validée ! Engagement activé.');
        await loadTimeline();
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la validation de la garantie');
    }
  };

  // ── External Events / Calendar Import ──

  const loadImportSettings = async () => {
    try {
      const res = await externalEventsAPI.getImportSettings();
      setImportSettings(res.data);
    } catch { /* silent */ }
  };

  const settingChangeRef = useRef(false);

  const handleImportSettingChange = async (provider, enabled) => {
    if (settingChangeRef.current) return;
    settingChangeRef.current = true;
    try {
      const res = await externalEventsAPI.updateImportSetting(provider, enabled);
      await loadImportSettings();
      if (enabled && res.data?.sync?.synced) await loadExternalEvents();
      if (!enabled) setExternalEvents(prev => prev.filter(e => e.source !== provider));
    } finally { settingChangeRef.current = false; }
  };

  const handleSync = async (force = false) => {
    setSyncing(true);
    try {
      await externalEventsAPI.sync(force);
      await loadImportSettings();
      await loadExternalEvents();
    } catch {
      if (force) toast.error('Erreur lors de la synchronisation');
    } finally {
      setSyncing(false);
    }
  };

  const loadExternalEvents = async () => {
    try {
      const res = await externalEventsAPI.list();
      setExternalEvents(res.data?.events || []);
    } catch { /* silent */ }
  };

  // ── Auto-refresh: 2-minute interval for enabled providers ──
  const hasAnyProviderEnabled = useMemo(() => {
    const providers = importSettings?.providers || {};
    return Object.values(providers).some(p => p.import_enabled);
  }, [importSettings]);

  // ── Auto-refresh: centralized hook ──
  const autoSyncCallback = useCallback(async () => {
    await externalEventsAPI.sync(true);
    const [settingsRes, eventsRes] = await Promise.all([
      externalEventsAPI.getImportSettings(),
      externalEventsAPI.list(),
    ]);
    setImportSettings(settingsRes.data);
    setExternalEvents(eventsRes.data?.events || []);
  }, []);

  const { lastAutoCheckAt } = useCalendarAutoSync({
    enabled: hasAnyProviderEnabled,
    syncing,
    onSync: autoSyncCallback,
  });

  const now = useMemo(() => new Date(), [loading]); // eslint-disable-line react-hooks/exhaustive-deps

  // Merge upcoming timeline items + external events chronologically
  const upcomingMerged = useMemo(() => {
    return [
      ...timeline.upcoming.map(i => ({ type: 'timeline', data: i, sortKey: i.starts_at })),
      ...externalEvents.map(e => ({ type: 'external', data: e, sortKey: e.start_datetime })),
    ].sort((a, b) => (a.sortKey || '').localeCompare(b.sortKey || ''));
  }, [timeline.upcoming, externalEvents]);

  // Search filter
  const matchesSearch = useCallback((item) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const fields = [
      item.title,
      item.location_display_name,
      item.location,
      item.counterparty_name,
      item.status,
      item.participant_status,
    ];
    return fields.some(f => f && String(f).toLowerCase().includes(q));
  }, [searchQuery]);

  const filteredUpcoming = useMemo(() =>
    upcomingMerged.filter(m => m.type === 'external' || matchesSearch(m.data)),
  [upcomingMerged, matchesSearch]);

  const filteredPast = useMemo(() =>
    timeline.past.filter(matchesSearch),
  [timeline.past, matchesSearch]);

  return (
    <div className="min-h-screen bg-background">
      {/* Delete Modal */}
      {deleteModal.open && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setDeleteModal({ open: false, item: null })}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-rose-100 flex items-center justify-center">
                <Trash2 className="w-5 h-5 text-rose-600" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900">Supprimer cet engagement</h3>
            </div>
            <p className="text-slate-600 mb-1">Voulez-vous vraiment supprimer cet engagement ?</p>
            <p className="text-sm text-slate-500 mb-6"><strong>"{deleteModal.item?.title}"</strong><br />Cette action est irréversible.</p>
            <div className="flex flex-col-reverse sm:flex-row gap-2 sm:gap-3 sm:justify-end">
              <Button variant="outline" onClick={() => setDeleteModal({ open: false, item: null })} disabled={deleting} className="min-h-[44px] sm:min-h-0">Annuler</Button>
              <Button variant="destructive" onClick={handleConfirmDelete} disabled={deleting} className="bg-rose-600 hover:bg-rose-700 text-white min-h-[44px] sm:min-h-0" data-testid="confirm-delete-btn">
                {deleting ? 'Suppression...' : 'Supprimer'}
              </Button>
            </div>
          </div>
        </div>
      )}

      <AppNavbar />

      <div className="max-w-7xl mx-auto px-4 md:px-6 py-6 md:py-8">
        {/* Header + Workspace Switcher */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-2">
          <HeaderStats user={user} counts={counts} />
          <div className="relative flex-shrink-0">
            <button
              onClick={() => setWorkspaceDropdownOpen(!workspaceDropdownOpen)}
              className="flex items-center gap-2 px-3 py-2 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors text-sm"
              data-testid="workspace-switcher-btn"
            >
              <Building2 className="w-4 h-4 text-slate-600" />
              <span className="font-medium text-slate-800">{currentWorkspace?.name}</span>
              <ChevronDown className={`w-4 h-4 text-slate-500 transition-transform ${workspaceDropdownOpen ? 'rotate-180' : ''}`} />
            </button>
            {workspaceDropdownOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setWorkspaceDropdownOpen(false)} />
                <div className="absolute right-0 top-full mt-2 w-72 bg-white rounded-lg shadow-lg border border-slate-200 z-20" data-testid="workspace-dropdown">
                  <div className="p-2">
                    <p className="text-xs font-medium text-slate-500 uppercase px-2 py-1">Vos workspaces</p>
                    {workspaces.map(ws => (
                      <button
                        key={ws.workspace_id}
                        onClick={() => handleSelectWorkspace(ws)}
                        className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-left transition-colors ${ws.workspace_id === currentWorkspace?.workspace_id ? 'bg-slate-100 text-slate-900' : 'hover:bg-slate-50 text-slate-700'}`}
                        data-testid={`workspace-option-${ws.workspace_id}`}
                      >
                        <Building2 className="w-4 h-4 text-slate-500" />
                        <div className="flex-1 min-w-0">
                          <p className="font-medium truncate">{ws.name}</p>
                          {ws.description && <p className="text-xs text-slate-500 truncate">{ws.description}</p>}
                        </div>
                        {ws.workspace_id === currentWorkspace?.workspace_id && <Check className="w-4 h-4 text-green-600" />}
                      </button>
                    ))}
                  </div>
                  <div className="border-t border-slate-100 p-2">
                    <button
                      onClick={() => { setWorkspaceDropdownOpen(false); navigate('/workspace/create'); }}
                      className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-left hover:bg-slate-50 text-slate-700 transition-colors"
                      data-testid="create-new-workspace-btn"
                    >
                      <Plus className="w-4 h-4 text-slate-500" />
                      <span className="font-medium">Créer un nouveau workspace</span>
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Impact Card */}
        {!loading && <ImpactCard totalCharityCents={impactCents} />}

        {/* Calendar Sync Panel */}
        {!loading && importSettings && (
          <CalendarSyncPanel
            importSettings={importSettings}
            onSettingChange={handleImportSettingChange}
            onSync={handleSync}
            syncing={syncing}
            lastAutoCheckAt={lastAutoCheckAt}
          />
        )}

        <div className="mb-6">
          <Link to="/appointments/create" className="block sm:inline-block">
            <Button size="lg" className="w-full sm:w-auto min-h-[44px]" data-testid="create-appointment-btn">
              <CalendarPlus className="w-5 h-5 mr-2" />
              Créer un engagement
            </Button>
          </Link>
        </div>

        {/* Unified Action Required Section */}
        {!loading && (timeline.action_required.length > 0 || pendingModifications.filter(p => p.is_action_required).length > 0) && (() => {
          const invItems = timeline.action_required;
          const modItems = pendingModifications.filter(p => p.is_action_required);
          const total = invItems.length + modItems.length;
          return (
            <div className="mb-6 bg-red-50/60 border border-red-200 rounded-lg p-5" data-testid="action-required-section">
              <div className="flex items-center gap-2 mb-1">
                <Flame className="w-5 h-5 text-red-500" />
                <h3 className="text-base font-semibold text-red-700">Actions requises</h3>
                <span className="ml-auto text-xs text-red-400 font-medium">{total} action{total !== 1 ? 's' : ''}</span>
              </div>
              <p className="text-xs text-red-400 mb-4">Ces actions nécessitent votre intervention pour débloquer les rendez-vous.</p>

              {/* Sub-section 1: Invitations & garanties */}
              {invItems.length > 0 && (
                <div className="mb-4" data-testid="action-subsection-invitations">
                  <div className="flex items-center gap-2 mb-2.5">
                    <span className="text-xs font-semibold text-red-600 uppercase tracking-wide">Action immédiate</span>
                    <span className="text-[11px] text-red-400">— Invitations & garanties ({invItems.length})</span>
                  </div>
                  <div className="space-y-3">
                    {invItems.slice(0, 8).map(item => (
                      <ActionCard key={`${item.role}-${item.appointment_id}`} item={item} onRemind={handleRemind} onAccept={handleAcceptInvitation} onDecline={handleDeclineInvitation} onCancel={handleCancelAppointment} onDelete={handleDeleteClick} onGuarantee={handleGuaranteeOrganizer} now={now} onNavigate={saveScroll} confirmCancelId={confirmCancelId} onCancelConfirmReset={() => setConfirmCancelId(null)} />
                    ))}
                  </div>
                </div>
              )}

              {/* Divider between sub-sections */}
              {invItems.length > 0 && modItems.length > 0 && (
                <div className="border-t border-red-200 my-4" />
              )}

              {/* Sub-section 2: Modifications à valider */}
              {modItems.length > 0 && (
                <div data-testid="action-subsection-modifications">
                  <div className="flex items-center gap-2 mb-2.5">
                    <FileEdit className="w-4 h-4 text-amber-600" />
                    <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Modifications à valider ({modItems.length})</span>
                  </div>
                  <div className="space-y-2">
                    {modItems.map(mod => {
                      const [accStr, totStr] = (mod.participants_summary || '0/0').split('/');
                      const accN = parseInt(accStr) || 0;
                      const totN = parseInt(totStr) || 0;
                      const pct = totN > 0 ? Math.round((accN / totN) * 100) : 0;
                      return (
                        <Link
                          key={mod.proposal_id}
                          to={`/appointments/${mod.appointment_id}`}
                          className="flex items-center justify-between bg-white border border-red-100 rounded-lg p-3 hover:border-red-300 transition-colors"
                          data-testid={`mod-action-card-${mod.proposal_id}`}
                        >
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-slate-900 truncate">{mod.appointment_title || 'Rendez-vous'}</p>
                            <p className="text-xs text-slate-700 mt-0.5 font-medium">{formatChangeSummary(mod)}</p>
                            <p className="text-[11px] text-slate-500 mt-0.5">
                              Par {mod.proposed_by?.name || mod.proposed_by?.role}
                              {mod.proposed_by?.role === 'participant' ? ' (participant)' : ' (organisateur)'}
                            </p>
                            <div className="flex items-center gap-2 mt-1.5" data-testid={`mod-progress-${mod.proposal_id}`}>
                              <div className="flex-1 max-w-[120px] bg-slate-100 rounded-full h-1.5">
                                <div className={`h-1.5 rounded-full transition-all ${pct === 100 ? 'bg-emerald-500' : pct > 0 ? 'bg-amber-400' : 'bg-slate-200'}`} style={{ width: `${pct}%` }} />
                              </div>
                              <span className="text-[11px] font-medium text-slate-500">{accN}/{totN} validé{accN !== 1 ? 's' : ''}</span>
                            </div>
                          </div>
                          <span className="flex-shrink-0 ml-3 text-xs font-medium text-white bg-amber-600 px-3 py-1.5 rounded-lg hover:bg-amber-700 transition-colors" data-testid={`mod-action-cta-${mod.proposal_id}`}>
                            Examiner
                          </span>
                        </Link>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        })()}

        {/* Main list */}
        <div className="bg-white rounded-lg border border-slate-200 p-4 md:p-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Engagements</h3>

          {loading ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900 mx-auto"></div>
            </div>
          ) : counts.total === 0 && externalEvents.length === 0 ? (
            <div className="text-center py-12">
              <Calendar className="w-16 h-16 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-600 mb-4">Aucun engagement pour le moment</p>
              <Link to="/appointments/create"><Button variant="outline">Créer votre premier engagement</Button></Link>
            </div>
          ) : (
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <div className="flex items-center justify-between gap-3 mb-6">
                <TabsList className="w-auto h-11 md:h-9">
                  <TabsTrigger value="upcoming" data-testid="tab-upcoming" className="px-2 md:px-3 text-xs md:text-sm">
                    <Calendar className="w-3.5 h-3.5 md:w-4 md:h-4 mr-1 md:mr-1.5" />
                    A venir
                    {(counts.upcoming > 0) && (
                      <span className="ml-1 md:ml-1.5 px-1 md:px-1.5 py-0.5 text-[10px] md:text-xs font-semibold bg-slate-900 text-white rounded-full">{counts.upcoming}</span>
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="past" data-testid="tab-past" className="px-2 md:px-3 text-xs md:text-sm">
                    <History className="w-3.5 h-3.5 md:w-4 md:h-4 mr-1 md:mr-1.5" />
                    Historique
                    {counts.past > 0 && (
                      <span className="ml-1 md:ml-1.5 px-1 md:px-1.5 py-0.5 text-[10px] md:text-xs font-semibold bg-slate-200 text-slate-600 rounded-full">{counts.past}</span>
                    )}
                  </TabsTrigger>
                </TabsList>
                <div className="relative w-48 md:w-64">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Rechercher..."
                    className="w-full h-9 pl-8 pr-3 text-sm border border-slate-200 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-300 placeholder:text-slate-400"
                    data-testid="engagement-search-input"
                  />
                </div>
              </div>

              <TabsContent value="upcoming">
                {filteredUpcoming.length === 0 ? (
                  <div className="text-center py-12">
                    <Calendar className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">{searchQuery ? 'Aucun engagement trouve' : 'Aucun engagement a venir'}</p>
                    {!searchQuery && <Link to="/appointments/create" className="mt-3 inline-block"><Button variant="outline" size="sm">Planifier un engagement</Button></Link>}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {filteredUpcoming.map(merged =>
                      merged.type === 'timeline' ? (
                        <TimelineCard key={`tl-${merged.data.appointment_id}`} item={merged.data} isPast={false} onDelete={handleDeleteClick} onRemind={handleRemind} onQuit={handleQuitParticipation} onDecline={handleDeclineInvitation} onGuarantee={handleGuaranteeOrganizer} now={now} fromTab="upcoming" onNavigate={saveScroll} hasModification={modPendingAptIds.has(merged.data.appointment_id)} modActionRequired={modActionAptIds.has(merged.data.appointment_id)} modificationData={modDataByAptId[merged.data.appointment_id]} confirmQuitId={confirmQuitId} onQuitConfirmReset={() => setConfirmQuitId(null)} />
                      ) : (
                        <ExternalEventCard key={`ext-${merged.data.external_event_id}`} event={merged.data} />
                      )
                    )}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="past">
                {filteredPast.length === 0 ? (
                  <div className="text-center py-12">
                    <History className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">{searchQuery ? 'Aucun engagement trouve' : 'Aucun engagement passe'}</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {filteredPast.slice(0, pastVisible).map(item => (
                      <TimelineCard key={`past-${item.role}-${item.appointment_id}`} item={item} isPast={true} onDelete={handleDeleteClick} onRemind={handleRemind} onQuit={handleQuitParticipation} onDecline={handleDeclineInvitation} onGuarantee={handleGuaranteeOrganizer} now={now} fromTab="past" onNavigate={saveScroll} hasModification={modPendingAptIds.has(item.appointment_id)} modActionRequired={modActionAptIds.has(item.appointment_id)} modificationData={modDataByAptId[item.appointment_id]} confirmQuitId={confirmQuitId} onQuitConfirmReset={() => setConfirmQuitId(null)} />
                    ))}
                    {filteredPast.length > pastVisible && (
                      <div className="pt-4 text-center">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setPastVisible(prev => prev + 20)}
                          className="text-slate-500 hover:text-slate-700"
                          data-testid="load-more-past-btn"
                        >
                          Voir plus
                        </Button>
                        <p className="text-xs text-slate-400 mt-1">{Math.min(pastVisible, filteredPast.length)} sur {filteredPast.length}</p>
                      </div>
                    )}
                  </div>
                )}
              </TabsContent>


            </Tabs>
          )}
        </div>
      </div>
    </div>
  );
}
