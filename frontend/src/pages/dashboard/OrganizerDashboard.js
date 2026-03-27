import React, { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useWorkspace } from '../../contexts/WorkspaceContext';
import { useAuth } from '../../contexts/AuthContext';
import { appointmentAPI, walletAPI, externalEventsAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../components/ui/tabs';
import {
  CalendarPlus, Calendar, Users, MapPin, Video,
  Trash2, Check, X, Clock, Building2, ChevronDown, Plus, Ban,
  ShieldCheck, CreditCard, History, Play, AlertTriangle, Bell,
  ArrowRight, Flame, Shield, Euro, Eye, Heart, Loader2,
  UserCheck, Mail, ChevronRight
} from 'lucide-react';
import { toast } from 'sonner';
import { formatDateTimeCompactFr, parseUTC } from '../../utils/dateFormat';
import AppNavbar from '../../components/AppNavbar';
import CalendarSyncPanel from './CalendarSyncPanel';
import ExternalEventCard from './ExternalEventCard';

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
    case 'cancelled_by_participant': return { label: 'Annulé', className: 'bg-red-100 text-red-800' };
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
    <div className="mb-6 bg-emerald-50 border border-emerald-200 rounded-lg p-5" data-testid="impact-card">
      <div className="flex items-center gap-2 mb-2">
        <Heart className="w-4.5 h-4.5 text-red-500 fill-red-500" />
        <span className="text-sm font-semibold text-emerald-700">Vos gestes solidaires</span>
      </div>
      <p className="text-3xl font-bold text-emerald-800 mb-1" data-testid="impact-amount">{amount}</p>
      <p className="text-sm text-emerald-600">reversés à des associations</p>
      <Link to="/settings/wallet" className="inline-block mt-3 text-xs text-emerald-600 hover:text-emerald-800 underline underline-offset-2 transition-colors" data-testid="impact-detail-link">
        Voir le détail →
      </Link>
    </div>
  );
}

// ── Action Required Section ──
function ActionRequiredSection({ items, onRemind, onAccept, onDecline, now }) {
  if (items.length === 0) return null;
  return (
    <div className="mb-6 bg-red-50/60 border border-red-200 rounded-lg p-5" data-testid="action-required-section">
      <div className="flex items-center gap-2 mb-4">
        <Flame className="w-5 h-5 text-red-500" />
        <h3 className="text-base font-semibold text-red-700">Action requise</h3>
        <span className="ml-auto text-xs text-red-400 font-medium">{items.length} élément{items.length > 1 ? 's' : ''}</span>
      </div>
      <div className="space-y-3">
        {items.slice(0, 8).map(item => (
          <ActionCard key={`${item.role}-${item.appointment_id}`} item={item} onRemind={onRemind} onAccept={onAccept} onDecline={onDecline} now={now} />
        ))}
      </div>
    </div>
  );
}

function ActionCard({ item, onRemind, onAccept, onDecline, now }) {
  const isParticipant = item.role === 'participant';

  return (
    <div className="bg-white border border-red-100 rounded-lg p-4" data-testid={`action-card-${item.appointment_id}`}>
      {/* Role label */}
      <div className="flex items-center gap-2 mb-2">
        <span className={`text-[11px] font-medium ${isParticipant ? 'text-blue-600' : 'text-slate-500'}`} data-testid={`role-label-${item.appointment_id}`}>
          {isParticipant ? `Invitation de ${item.counterparty_name}` : 'Créé par vous'}
        </span>
        {item.pending_label && (
          <span className={`ml-auto text-xs font-semibold ${isParticipant ? 'text-blue-600' : 'text-red-600'}`}>{item.pending_label}</span>
        )}
      </div>

      {/* Title */}
      <p className="font-semibold text-base text-slate-900 mb-2">{item.title}</p>

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

      {/* CTAs */}
      <div className="flex items-center gap-2">
        {isParticipant && item.status === 'invited' ? (
          <>
            <Button size="sm" className="h-11 md:h-8 text-xs flex-1 md:flex-none bg-emerald-600 hover:bg-emerald-700 text-white" onClick={() => onAccept(item)} data-testid={`accept-btn-${item.appointment_id}`}>
              <Check className="w-3.5 h-3.5 mr-1.5" /> Accepter
            </Button>
            <Button size="sm" variant="outline" className="h-11 md:h-8 text-xs flex-1 md:flex-none border-slate-200 text-slate-600" onClick={() => onDecline(item)} data-testid={`decline-btn-${item.appointment_id}`}>
              <X className="w-3.5 h-3.5 mr-1.5" /> Refuser
            </Button>
          </>
        ) : isParticipant && item.participant_status === 'accepted_pending_guarantee' ? (
          <Link to={`/appointments/${item.appointment_id}`} className="flex-1 md:flex-none">
            <Button size="sm" className="h-11 md:h-8 text-xs w-full bg-amber-600 hover:bg-amber-700 text-white" data-testid={`finalize-guarantee-btn-${item.appointment_id}`}>
              <CreditCard className="w-3.5 h-3.5 mr-1.5" /> Finaliser ma garantie
            </Button>
          </Link>
        ) : (
          <Button size="sm" variant="outline" className="h-11 md:h-8 text-xs flex-1 md:flex-none border-red-200 text-red-600 hover:bg-red-50" onClick={() => onRemind(item)} data-testid={`remind-action-${item.appointment_id}`}>
            <Bell className="w-3.5 h-3.5 mr-1.5" /> Relancer
          </Button>
        )}
        <Link to={`/appointments/${item.appointment_id}`} className="flex-1 md:flex-none">
          <Button size="sm" variant="ghost" className="h-11 md:h-8 text-xs w-full" data-testid={`view-action-${item.appointment_id}`}>
            <Eye className="w-3.5 h-3.5 mr-1.5" /> Voir détails
          </Button>
        </Link>
      </div>
    </div>
  );
}

// ── Timeline Card (unified for organizer + participant) ──
function TimelineCard({ item, isPast, onDelete, onRemind, now }) {
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

  const detailLink = `/appointments/${item.appointment_id}`;

  return (
    <div
      className={`relative border rounded-lg transition-all ${
        isOngoing ? 'border-blue-300 bg-blue-50/30 ring-1 ring-blue-200'
          : isPast ? 'border-slate-150 bg-slate-50/50 hover:border-slate-300'
          : 'border-slate-200 hover:border-slate-300 hover:shadow-sm'
      }`}
      data-testid={`timeline-card-${item.appointment_id}`}
    >
      <Link to={detailLink} className="block p-4 pb-2">
        {/* Row 0: Role label + Badges */}
        <div className="flex items-center justify-between gap-2 mb-2">
          <span className={`text-[11px] font-medium ${isParticipant ? 'text-blue-600' : 'text-slate-400'}`} data-testid={`timeline-role-${item.appointment_id}`}>
            {isParticipant ? `Invitation de ${item.counterparty_name}` : 'Créé par vous'}
          </span>
          <div className="flex items-center gap-1.5 flex-shrink-0">
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

        {/* Row 4: Participants + Progress (organizer only) */}
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

        {/* Pending label for participant */}
        {isParticipant && item.pending_label && (
          <div className="mb-1">
            <span className="text-xs font-medium text-blue-600">{item.pending_label}</span>
          </div>
        )}
      </Link>

      {/* Actions row */}
      <div className="flex items-center gap-2 px-4 pb-3 pt-1">
        <Link to={detailLink} className="flex-1 md:flex-none">
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

  // Timeline state
  const [timeline, setTimeline] = useState({ action_required: [], upcoming: [], past: [] });
  const [counts, setCounts] = useState({ action_required: 0, upcoming: 0, past: 0, total: 0 });
  const [loading, setLoading] = useState(true);
  const [pastVisible, setPastVisible] = useState(20);

  const [impactCents, setImpactCents] = useState(0);
  const [deleteModal, setDeleteModal] = useState({ open: false, item: null });
  const [deleting, setDeleting] = useState(false);
  const [workspaceDropdownOpen, setWorkspaceDropdownOpen] = useState(false);
  const [responding, setResponding] = useState(null);

  // Analytics state
  const [analytics, setAnalytics] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);

  // External events / calendar import state
  const [importSettings, setImportSettings] = useState(null);
  const [externalEvents, setExternalEvents] = useState([]);
  const [syncing, setSyncing] = useState(false);
  const [lastAutoCheckAt, setLastAutoCheckAt] = useState(null);

  useEffect(() => {
    loadTimeline();
    loadImpact();
    loadImportSettings().then(() => loadExternalEvents());
  }, [currentWorkspace]);

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

  const loadAnalytics = useCallback(async () => {
    if (!currentWorkspace) return;
    setAnalyticsLoading(true);
    try {
      const res = await appointmentAPI.analyticsStats(currentWorkspace.workspace_id);
      setAnalytics(res.data);
    } catch (error) {
      console.error('Analytics load error:', error);
    } finally {
      setAnalyticsLoading(false);
    }
  }, [currentWorkspace]);

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

  const handleRemind = async (item) => {
    try {
      await appointmentAPI.remind(item.appointment_id);
      toast.success('Relance envoyée aux participants en attente');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Erreur lors de la relance');
    }
  };

  const handleAcceptInvitation = async (item) => {
    if (!item.invitation_token) return;
    setResponding(item.appointment_id);
    try {
      const API_URL = process.env.REACT_APP_BACKEND_URL;
      const resp = await fetch(`${API_URL}/api/invitations/${item.invitation_token}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'accept' }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Erreur');

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
      // Reload timeline to reflect new status
      await loadTimeline();
    } catch (err) {
      toast.error(err.message || 'Erreur lors de l\'acceptation');
    } finally {
      setResponding(null);
    }
  };

  const handleDeclineInvitation = async (item) => {
    if (!item.invitation_token) return;
    setResponding(item.appointment_id);
    try {
      const API_URL = process.env.REACT_APP_BACKEND_URL;
      const resp = await fetch(`${API_URL}/api/invitations/${item.invitation_token}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'decline' }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Erreur');
      toast.success('Invitation refusée');
      await loadTimeline();
    } catch (err) {
      toast.error(err.message || 'Erreur lors du refus');
    } finally {
      setResponding(null);
    }
  };

  const handleSelectWorkspace = (workspace) => {
    selectWorkspace(workspace);
    setWorkspaceDropdownOpen(false);
    setLoading(true);
  };

  // ── External Events / Calendar Import ──

  const loadImportSettings = async () => {
    try {
      const res = await externalEventsAPI.getImportSettings();
      setImportSettings(res.data);
    } catch { /* silent */ }
  };

  const handleImportSettingChange = async (provider, enabled) => {
    const res = await externalEventsAPI.updateImportSetting(provider, enabled);
    await loadImportSettings();
    if (enabled && res.data?.sync?.synced) await loadExternalEvents();
    if (!enabled) setExternalEvents(prev => prev.filter(e => e.source !== provider));
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

  const syncIntervalRef = useRef(null);
  const syncInProgressRef = useRef(false);
  const syncingRef = useRef(false);
  useEffect(() => { syncingRef.current = syncing; }, [syncing]);

  useEffect(() => {
    if (syncIntervalRef.current) {
      clearInterval(syncIntervalRef.current);
      syncIntervalRef.current = null;
    }
    if (!hasAnyProviderEnabled) return;
    syncIntervalRef.current = setInterval(async () => {
      if (syncInProgressRef.current || syncingRef.current) return;
      syncInProgressRef.current = true;
      try {
        await externalEventsAPI.sync(true);
        const [settingsRes, eventsRes] = await Promise.all([
          externalEventsAPI.getImportSettings(),
          externalEventsAPI.list(),
        ]);
        setImportSettings(settingsRes.data);
        setExternalEvents(eventsRes.data?.events || []);
        setLastAutoCheckAt(new Date().toISOString());
      } catch { /* silent */ }
      finally { syncInProgressRef.current = false; }
    }, 120_000);
    return () => {
      if (syncIntervalRef.current) {
        clearInterval(syncIntervalRef.current);
        syncIntervalRef.current = null;
      }
    };
  }, [hasAnyProviderEnabled]);

  const now = useMemo(() => new Date(), [loading]); // eslint-disable-line react-hooks/exhaustive-deps

  // Merge upcoming timeline items + external events chronologically
  const upcomingMerged = useMemo(() => {
    return [
      ...timeline.upcoming.map(i => ({ type: 'timeline', data: i, sortKey: i.starts_at })),
      ...externalEvents.map(e => ({ type: 'external', data: e, sortKey: e.start_datetime })),
    ].sort((a, b) => (a.sortKey || '').localeCompare(b.sortKey || ''));
  }, [timeline.upcoming, externalEvents]);

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

        {/* Action Required Section */}
        {!loading && (
          <ActionRequiredSection
            items={timeline.action_required}
            onRemind={handleRemind}
            onAccept={handleAcceptInvitation}
            onDecline={handleDeclineInvitation}
            now={now}
          />
        )}

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
            <Tabs defaultValue="upcoming">
              <TabsList className="mb-6 w-full md:w-auto h-11 md:h-9">
                <TabsTrigger value="upcoming" data-testid="tab-upcoming" className="px-2 md:px-3 text-xs md:text-sm">
                  <Calendar className="w-3.5 h-3.5 md:w-4 md:h-4 mr-1 md:mr-1.5" />
                  À venir
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
                <TabsTrigger value="stats" data-testid="tab-stats" className="px-2 md:px-3 text-xs md:text-sm" onClick={() => { if (!analytics) loadAnalytics(); }}>
                  <Eye className="w-3.5 h-3.5 md:w-4 md:h-4 mr-1 md:mr-1.5" />
                  Statistiques
                </TabsTrigger>
              </TabsList>

              <TabsContent value="upcoming">
                {upcomingMerged.length === 0 ? (
                  <div className="text-center py-12">
                    <Calendar className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">Aucun engagement à venir</p>
                    <Link to="/appointments/create" className="mt-3 inline-block"><Button variant="outline" size="sm">Planifier un engagement</Button></Link>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {upcomingMerged.map(merged =>
                      merged.type === 'timeline' ? (
                        <TimelineCard key={`tl-${merged.data.appointment_id}`} item={merged.data} isPast={false} onDelete={handleDeleteClick} onRemind={handleRemind} now={now} />
                      ) : (
                        <ExternalEventCard key={`ext-${merged.data.external_event_id}`} event={merged.data} />
                      )
                    )}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="past">
                {timeline.past.length === 0 ? (
                  <div className="text-center py-12">
                    <History className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">Aucun engagement passé</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {timeline.past.slice(0, pastVisible).map(item => (
                      <TimelineCard key={`past-${item.role}-${item.appointment_id}`} item={item} isPast={true} onDelete={handleDeleteClick} onRemind={handleRemind} now={now} />
                    ))}
                    {timeline.past.length > pastVisible && (
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
                        <p className="text-xs text-slate-400 mt-1">{Math.min(pastVisible, timeline.past.length)} sur {timeline.past.length}</p>
                      </div>
                    )}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="stats">
                {analyticsLoading ? (
                  <div className="text-center py-12">
                    <Loader2 className="w-8 h-8 animate-spin text-slate-400 mx-auto" />
                  </div>
                ) : analytics ? (
                  <div className="space-y-5">
                    <div className={`px-4 py-3 rounded-lg text-sm font-medium ${
                      analytics.global_tone === 'positive' ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' :
                      analytics.global_tone === 'warning' ? 'bg-amber-50 text-amber-800 border border-amber-200' :
                      'bg-slate-50 text-slate-600 border border-slate-200'
                    }`} data-testid="analytics-global-message">
                      {analytics.global_message}
                    </div>
                    <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
                      <div className="bg-slate-50 rounded-lg p-4 border border-slate-100" data-testid="kpi-engagements">
                        <p className="text-2xl font-bold text-slate-900">{analytics.total_engagements}</p>
                        <p className="text-xs text-slate-500 mt-1">Engagements créés</p>
                      </div>
                      <div className="bg-slate-50 rounded-lg p-4 border border-slate-100" data-testid="kpi-presence">
                        <p className="text-2xl font-bold text-slate-900">
                          {analytics.presence_rate !== null ? `${analytics.presence_rate}%` : '—'}
                        </p>
                        <p className="text-xs text-slate-500 mt-1">Taux de présence</p>
                      </div>
                      <div className="bg-slate-50 rounded-lg p-4 border border-slate-100" data-testid="kpi-acceptance">
                        <p className="text-2xl font-bold text-slate-900">
                          {analytics.acceptance_rate !== null ? `${analytics.acceptance_rate}%` : '—'}
                        </p>
                        <p className="text-xs text-slate-500 mt-1">Taux d'acceptation</p>
                      </div>
                      <div className="bg-slate-50 rounded-lg p-4 border border-slate-100" data-testid="kpi-compensation">
                        <p className="text-2xl font-bold text-slate-900">
                          {(analytics.personal_compensation_cents / 100).toFixed(0)} €
                        </p>
                        <p className="text-xs text-slate-500 mt-1">Dédommagement personnel</p>
                      </div>
                      <div className="bg-slate-50 rounded-lg p-4 border border-slate-100" data-testid="kpi-charity">
                        <p className="text-2xl font-bold text-emerald-700">
                          {(analytics.charity_total_cents / 100).toFixed(0)} €
                        </p>
                        <p className="text-xs text-slate-500 mt-1">Reversés à des associations</p>
                      </div>
                      <div className="bg-slate-50 rounded-lg p-4 border border-slate-100" data-testid="kpi-defaults">
                        <p className={`text-2xl font-bold ${analytics.organizer_defaults > 0 ? 'text-amber-600' : 'text-slate-900'}`}>
                          {analytics.organizer_defaults}
                        </p>
                        {analytics.organizer_penalties_cents > 0 && (
                          <p className="text-sm font-semibold text-amber-600 mt-0.5">
                            {(analytics.organizer_penalties_cents / 100).toFixed(0)} €
                          </p>
                        )}
                        <p className="text-xs text-slate-500 mt-1">Engagements non honorés</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Eye className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">Chargement des statistiques...</p>
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
