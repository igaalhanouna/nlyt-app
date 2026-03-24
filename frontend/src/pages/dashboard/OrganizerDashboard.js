import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useWorkspace } from '../../contexts/WorkspaceContext';
import { useAuth } from '../../contexts/AuthContext';
import { appointmentAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../components/ui/tabs';
import {
  CalendarPlus, LogOut, Settings, Calendar, Users, MapPin, Video,
  Trash2, Check, X, Clock, Building2, ChevronDown, Plus, Ban,
  ShieldCheck, CreditCard, History, Play, AlertTriangle, Bell,
  ArrowRight, Flame, Shield, Euro, Eye, Heart, Loader2
} from 'lucide-react';
import { toast } from 'sonner';
import { formatDateTimeCompactFr, parseUTC } from '../../utils/dateFormat';

// ── Helpers ──

const ACCEPTED_STATUSES = new Set(['accepted', 'accepted_guaranteed']);
const PENDING_STATUSES = new Set(['invited', 'accepted_pending_guarantee']);

function getParticipantCounts(appointment) {
  const participants = appointment.participants || [];
  const total = participants.length;
  const accepted = participants.filter(p => ACCEPTED_STATUSES.has(p.status)).length;
  const pending = participants.filter(p => PENDING_STATUSES.has(p.status)).length;
  return { total, accepted, pending };
}

function getRisk(appointment, now) {
  const start = parseUTC(appointment.start_datetime);
  if (!start) return 'secured';
  const { total, accepted, pending } = getParticipantCounts(appointment);
  if (total === 0) return 'secured';
  const hoursUntil = (start - now) / 3600000;
  if (hoursUntil <= 0) return 'secured'; // already started/past

  if (accepted === total) return 'secured';
  if (hoursUntil <= 24 && pending > 0) return 'high';
  if (hoursUntil <= 48 || pending > 0) return 'medium';
  return 'secured';
}

const RISK_CONFIG = {
  high:     { label: 'Risque élevé', className: 'bg-red-100 text-red-700 border-red-200', dot: 'bg-red-500', icon: AlertTriangle },
  medium:   { label: 'À surveiller', className: 'bg-amber-50 text-amber-700 border-amber-200', dot: 'bg-amber-500', icon: Clock },
  secured:  { label: 'Sécurisé', className: 'bg-emerald-50 text-emerald-700 border-emerald-200', dot: 'bg-emerald-500', icon: Shield },
};

function fmtEuro(amount) {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', minimumFractionDigits: 0 }).format(amount || 0);
}

// ── Sub-components ──

function HeaderStats({ user, stats }) {
  return (
    <div className="mb-8">
      <h2 className="text-2xl font-bold text-slate-900 mb-1" data-testid="dashboard-title">
        Bonjour, {user?.first_name}
      </h2>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-slate-500 mt-1" data-testid="dashboard-stats">
        <span><span className="font-semibold text-slate-700">{stats.upcoming}</span> engagement{stats.upcoming !== 1 ? 's' : ''}</span>
        <span className="text-slate-300">|</span>
        <span><span className="font-semibold text-red-600">{stats.atRisk}</span> à risque</span>
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
        <span className="text-sm font-semibold text-emerald-700">Votre impact</span>
      </div>
      <p className="text-3xl font-bold text-emerald-800 mb-1" data-testid="impact-amount">{amount}</p>
      <p className="text-sm text-emerald-600">générés pour des associations</p>
      <p className="text-xs text-emerald-500 mt-1">Grâce à vos engagements sur NLYT</p>
      <Link to="/impact" className="inline-block mt-3 text-xs text-emerald-600 hover:text-emerald-800 underline underline-offset-2 transition-colors" data-testid="impact-detail-link">
        Voir le détail →
      </Link>
    </div>
  );
}

function PrioritySection({ items, onRemind }) {
  if (items.length === 0) return null;
  return (
    <div className="mb-6 bg-red-50/60 border border-red-200 rounded-lg p-5" data-testid="priority-section">
      <div className="flex items-center gap-2 mb-4">
        <Flame className="w-5 h-5 text-red-500" />
        <h3 className="text-base font-semibold text-red-700">À traiter maintenant</h3>
        <span className="ml-auto text-xs text-red-400 font-medium">{items.length} engagement{items.length > 1 ? 's' : ''}</span>
      </div>
      <div className="space-y-3">
        {items.slice(0, 5).map(a => (
          <PriorityCard key={a.appointment_id} appointment={a} onRemind={onRemind} />
        ))}
      </div>
    </div>
  );
}

function PriorityCard({ appointment, onRemind }) {
  const { total, accepted, pending } = getParticipantCounts(appointment);
  return (
    <div className="flex items-center gap-4 bg-white border border-red-100 rounded-lg p-3" data-testid={`priority-card-${appointment.appointment_id}`}>
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-sm text-slate-900 truncate">{appointment.title}</p>
        <p className="text-xs text-slate-500">{formatDateTimeCompactFr(appointment.start_datetime)} · {appointment.duration_minutes} min</p>
      </div>
      <div className="text-xs text-right whitespace-nowrap">
        <span className="text-red-600 font-semibold">{pending} en attente</span>
        <span className="text-slate-400"> / {total}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <Button size="sm" variant="outline" className="h-7 text-xs border-red-200 text-red-600 hover:bg-red-50" onClick={(e) => { e.stopPropagation(); onRemind(appointment); }} data-testid={`remind-priority-${appointment.appointment_id}`}>
          <Bell className="w-3 h-3 mr-1" /> Relancer
        </Button>
        <Link to={`/appointments/${appointment.appointment_id}`}>
          <Button size="sm" variant="ghost" className="h-7 text-xs" data-testid={`view-priority-${appointment.appointment_id}`}>
            <Eye className="w-3 h-3 mr-1" /> Voir
          </Button>
        </Link>
      </div>
    </div>
  );
}

function EngagementCard({ appointment, isPast, onDelete, onRemind, now }) {
  const risk = isPast ? 'secured' : getRisk(appointment, now);
  const riskCfg = RISK_CONFIG[risk];
  const RiskIcon = riskCfg.icon;
  const { total, accepted, pending } = getParticipantCounts(appointment);
  const progressPct = total > 0 ? Math.round((accepted / total) * 100) : 100;
  const badge = getTemporalBadge(appointment, now);
  const isOngoing = badge.key === 'ongoing';

  return (
    <div
      className={`relative border rounded-lg transition-all ${
        isOngoing ? 'border-blue-300 bg-blue-50/30 ring-1 ring-blue-200'
          : isPast ? 'border-slate-150 bg-slate-50/50 hover:border-slate-300'
          : 'border-slate-200 hover:border-slate-300 hover:shadow-sm'
      }`}
      data-testid={`appointment-card-${appointment.appointment_id}`}
    >
      <Link to={`/appointments/${appointment.appointment_id}`} className="block p-4">
        {/* Row 1: Title + Risk badge */}
        <div className="flex items-start justify-between gap-3 mb-2">
          <h4 className={`font-semibold text-sm leading-tight ${isPast && !isOngoing ? 'text-slate-500' : 'text-slate-900'}`}>
            {isOngoing && <Play className="w-3.5 h-3.5 inline mr-1 text-blue-600" />}
            {appointment.title}
          </h4>
          <div className="flex items-center gap-2 flex-shrink-0">
            {!isPast && (
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium rounded-full border ${riskCfg.className}`} data-testid={`risk-badge-${appointment.appointment_id}`}>
                <RiskIcon className="w-3 h-3" />
                {riskCfg.label}
              </span>
            )}
            <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${badge.className}`}>
              {badge.label}
            </span>
          </div>
        </div>

        {/* Row 2: Meta */}
        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 mb-3">
          <span>{formatDateTimeCompactFr(appointment.start_datetime)}</span>
          <span className="text-slate-300">·</span>
          <span>{appointment.duration_minutes} min</span>
          <span className="text-slate-300">·</span>
          <span className="flex items-center gap-1">
            {appointment.appointment_type === 'physical'
              ? <><MapPin className="w-3 h-3" /> Physique</>
              : <><Video className="w-3 h-3" /> {appointment.meeting_provider || 'Visio'}</>
            }
          </span>
          {appointment.penalty_amount > 0 && (
            <>
              <span className="text-slate-300">·</span>
              <span className="flex items-center gap-1 text-slate-600 font-medium">
                <Euro className="w-3 h-3" /> {fmtEuro(appointment.penalty_amount)}
              </span>
            </>
          )}
        </div>

        {/* Row 3: Participants + Progress */}
        {total > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-600 flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5" />
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
                data-testid={`progress-bar-${appointment.appointment_id}`}
              />
            </div>
          </div>
        )}
      </Link>

      {/* Actions row */}
      <div className="flex items-center gap-2 px-4 pb-3 pt-1">
        <Link to={`/appointments/${appointment.appointment_id}`}>
          <Button size="sm" variant="outline" className="h-7 text-xs" data-testid={`view-details-${appointment.appointment_id}`}>
            <Eye className="w-3 h-3 mr-1" /> Voir détails
          </Button>
        </Link>
        {!isPast && pending > 0 && (
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs border-amber-200 text-amber-700 hover:bg-amber-50"
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); onRemind(appointment); }}
            data-testid={`remind-btn-${appointment.appointment_id}`}
          >
            <Bell className="w-3 h-3 mr-1" /> Relancer
          </Button>
        )}
        <button
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDelete(appointment); }}
          className="ml-auto p-1.5 text-slate-300 hover:text-rose-600 hover:bg-rose-50 rounded transition-colors"
          title="Supprimer"
          data-testid={`delete-appointment-${appointment.appointment_id}`}
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

function getTemporalBadge(appointment, now) {
  if (appointment.status === 'cancelled') return { key: 'cancelled', label: 'Annulé', className: 'bg-red-100 text-red-800' };
  if (appointment.status === 'pending_organizer_guarantee') return { key: 'pending_guarantee', label: 'Garantie en attente', className: 'bg-amber-100 text-amber-800' };
  if (appointment.status === 'draft') return { key: 'draft', label: 'Brouillon', className: 'bg-slate-100 text-slate-800' };
  const start = parseUTC(appointment.start_datetime);
  if (!start) return { key: 'past', label: 'Terminé', className: 'bg-slate-100 text-slate-600' };
  const end = new Date(start.getTime() + (appointment.duration_minutes || 0) * 60000);
  if (now >= start && now < end) return { key: 'ongoing', label: 'En cours', className: 'bg-blue-100 text-blue-800' };
  if (end < now) return { key: 'past', label: 'Terminé', className: 'bg-slate-100 text-slate-600' };
  return { key: 'active', label: 'Actif', className: 'bg-emerald-100 text-emerald-800' };
}

// ── Main Dashboard ──

export default function OrganizerDashboard() {
  const { user, logout } = useAuth();
  const { currentWorkspace, workspaces, selectWorkspace } = useWorkspace();
  const navigate = useNavigate();

  // Pagination state — upcoming
  const [upcoming, setUpcoming] = useState([]);
  const [upcomingTotal, setUpcomingTotal] = useState(0);
  const [upcomingHasMore, setUpcomingHasMore] = useState(false);
  const [upcomingLoading, setUpcomingLoading] = useState(false);

  // Pagination state — past
  const [past, setPast] = useState([]);
  const [pastTotal, setPastTotal] = useState(0);
  const [pastHasMore, setPastHasMore] = useState(false);
  const [pastLoading, setPastLoading] = useState(false);

  const [loading, setLoading] = useState(true);
  const [impactCents, setImpactCents] = useState(0);
  const [deleteModal, setDeleteModal] = useState({ open: false, appointment: null });
  const [deleting, setDeleting] = useState(false);
  const [workspaceDropdownOpen, setWorkspaceDropdownOpen] = useState(false);

  // Analytics state
  const [analytics, setAnalytics] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);

  const PAGE_SIZE = 20;

  useEffect(() => {
    if (currentWorkspace) loadInitial();
    loadImpact();
  }, [currentWorkspace]);

  const loadInitial = async () => {
    setLoading(true);
    try {
      const wsId = currentWorkspace.workspace_id;
      const [upRes, pastRes] = await Promise.all([
        appointmentAPI.list(wsId, { skip: 0, limit: PAGE_SIZE, time_filter: 'upcoming' }),
        appointmentAPI.list(wsId, { skip: 0, limit: PAGE_SIZE, time_filter: 'past' }),
      ]);
      setUpcoming(upRes.data.items || []);
      setUpcomingTotal(upRes.data.total || 0);
      setUpcomingHasMore(upRes.data.has_more || false);
      setPast(pastRes.data.items || []);
      setPastTotal(pastRes.data.total || 0);
      setPastHasMore(pastRes.data.has_more || false);
    } catch (error) {
      toast.error('Erreur lors du chargement des engagements');
    } finally {
      setLoading(false);
    }
  };

  const loadMoreUpcoming = useCallback(async () => {
    if (upcomingLoading || !upcomingHasMore) return;
    setUpcomingLoading(true);
    try {
      const res = await appointmentAPI.list(currentWorkspace.workspace_id, {
        skip: upcoming.length, limit: PAGE_SIZE, time_filter: 'upcoming'
      });
      setUpcoming(prev => [...prev, ...(res.data.items || [])]);
      setUpcomingHasMore(res.data.has_more || false);
    } catch (error) {
      toast.error('Erreur lors du chargement');
    } finally {
      setUpcomingLoading(false);
    }
  }, [upcoming.length, upcomingLoading, upcomingHasMore, currentWorkspace]);

  const loadMorePast = useCallback(async () => {
    if (pastLoading || !pastHasMore) return;
    setPastLoading(true);
    try {
      const res = await appointmentAPI.list(currentWorkspace.workspace_id, {
        skip: past.length, limit: PAGE_SIZE, time_filter: 'past'
      });
      setPast(prev => [...prev, ...(res.data.items || [])]);
      setPastHasMore(res.data.has_more || false);
    } catch (error) {
      toast.error('Erreur lors du chargement');
    } finally {
      setPastLoading(false);
    }
  }, [past.length, pastLoading, pastHasMore, currentWorkspace]);

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
      const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/impact`);
      const data = await res.json();
      setImpactCents(data.total_charity_cents || 0);
    } catch (_) { /* non-blocking */ }
  };

  const handleDeleteClick = (appointment) => {
    setDeleteModal({ open: true, appointment });
  };

  const handleConfirmDelete = async () => {
    if (!deleteModal.appointment) return;
    setDeleting(true);
    try {
      await appointmentAPI.delete(deleteModal.appointment.appointment_id);
      const aptId = deleteModal.appointment.appointment_id;
      setUpcoming(prev => prev.filter(a => a.appointment_id !== aptId));
      setPast(prev => prev.filter(a => a.appointment_id !== aptId));
      toast.success('Engagement supprimé');
      setDeleteModal({ open: false, appointment: null });
    } catch (error) {
      toast.error('Erreur lors de la suppression');
    } finally {
      setDeleting(false);
    }
  };

  const handleRemind = async (appointment) => {
    try {
      await appointmentAPI.remind(appointment.appointment_id);
      toast.success('Relance envoyée aux participants en attente');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Erreur lors de la relance');
    }
  };

  const handleSelectWorkspace = (workspace) => {
    selectWorkspace(workspace);
    setWorkspaceDropdownOpen(false);
    setLoading(true);
  };

  // ── Computed data ──
  const computed = useMemo(() => {
    const now = new Date();

    // Risk computation from upcoming list
    let secured = 0, atRisk = 0, atRiskCount = 0;
    const priorityItems = [];

    upcoming.forEach(a => {
      const risk = getRisk(a, now);
      const penalty = a.penalty_amount || 0;
      if (risk === 'secured') {
        secured += penalty;
      } else {
        atRisk += penalty;
        atRiskCount++;
      }
      if (risk === 'high') priorityItems.push(a);
    });

    return { now, secured, atRisk, atRiskCount, priorityItems, totalEngaged: secured + atRisk };
  }, [upcoming]);

  return (
    <div className="min-h-screen bg-background">
      {/* Delete Modal */}
      {deleteModal.open && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setDeleteModal({ open: false, appointment: null })}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-rose-100 flex items-center justify-center">
                <Trash2 className="w-5 h-5 text-rose-600" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900">Supprimer cet engagement</h3>
            </div>
            <p className="text-slate-600 mb-1">Voulez-vous vraiment supprimer cet engagement ?</p>
            <p className="text-sm text-slate-500 mb-6"><strong>"{deleteModal.appointment?.title}"</strong><br />Cette action est irréversible.</p>
            <div className="flex gap-3 justify-end">
              <Button variant="outline" onClick={() => setDeleteModal({ open: false, appointment: null })} disabled={deleting}>Annuler</Button>
              <Button variant="destructive" onClick={handleConfirmDelete} disabled={deleting} className="bg-rose-600 hover:bg-rose-700 text-white" data-testid="confirm-delete-btn">
                {deleting ? 'Suppression...' : 'Supprimer'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Nav */}
      <nav className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <h1 className="text-2xl font-bold text-slate-900">NLYT</h1>
            <div className="flex items-center gap-6">
              <Link to="/dashboard" className="text-sm font-medium text-slate-900">Tableau de bord</Link>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <Link to="/settings"><Button variant="ghost" size="sm"><Settings className="w-4 h-4 mr-2" />Paramètres</Button></Link>
            <Button variant="ghost" size="sm" onClick={logout} data-testid="logout-btn"><LogOut className="w-4 h-4 mr-2" />Déconnexion</Button>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Header + Workspace Switcher */}
        <div className="flex items-start justify-between mb-2">
          <HeaderStats user={user} stats={{ upcoming: upcomingTotal, atRisk: computed.atRiskCount, totalEngaged: computed.totalEngaged }} />
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

        <div className="mb-6">
          <Link to="/appointments/create">
            <Button size="lg" data-testid="create-appointment-btn">
              <CalendarPlus className="w-5 h-5 mr-2" />
              Créer un engagement
            </Button>
          </Link>
        </div>

        {/* Priority Section */}
        {!loading && <PrioritySection items={computed.priorityItems} onRemind={handleRemind} />}

        {/* Main list */}
        <div className="bg-white rounded-lg border border-slate-200 p-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Engagements</h3>

          {loading ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900 mx-auto"></div>
            </div>
          ) : upcoming.length === 0 && past.length === 0 ? (
            <div className="text-center py-12">
              <Calendar className="w-16 h-16 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-600 mb-4">Aucun engagement pour le moment</p>
              <Link to="/appointments/create"><Button variant="outline">Créer votre premier engagement</Button></Link>
            </div>
          ) : (
            <Tabs defaultValue="upcoming">
              <TabsList className="mb-6">
                <TabsTrigger value="upcoming" data-testid="tab-upcoming">
                  <Calendar className="w-4 h-4 mr-2" />
                  À venir
                  {upcomingTotal > 0 && (
                    <span className="ml-2 px-2 py-0.5 text-xs font-semibold bg-slate-900 text-white rounded-full">{upcomingTotal}</span>
                  )}
                </TabsTrigger>
                <TabsTrigger value="past" data-testid="tab-past">
                  <History className="w-4 h-4 mr-2" />
                  Passés
                  {pastTotal > 0 && (
                    <span className="ml-2 px-2 py-0.5 text-xs font-semibold bg-slate-200 text-slate-600 rounded-full">{pastTotal}</span>
                  )}
                </TabsTrigger>
                <TabsTrigger value="stats" data-testid="tab-stats" onClick={() => { if (!analytics) loadAnalytics(); }}>
                  <Eye className="w-4 h-4 mr-2" />
                  Statistiques
                </TabsTrigger>
              </TabsList>

              <TabsContent value="upcoming">
                {upcoming.length === 0 ? (
                  <div className="text-center py-12">
                    <Calendar className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">Aucun engagement à venir</p>
                    <Link to="/appointments/create" className="mt-3 inline-block"><Button variant="outline" size="sm">Planifier un engagement</Button></Link>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {upcoming.map(a => (
                      <EngagementCard key={a.appointment_id} appointment={a} isPast={false} onDelete={handleDeleteClick} onRemind={handleRemind} now={computed.now} />
                    ))}
                    {upcomingHasMore && (
                      <div className="pt-4 text-center">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={loadMoreUpcoming}
                          disabled={upcomingLoading}
                          className="text-slate-500 hover:text-slate-700"
                          data-testid="load-more-upcoming-btn"
                        >
                          {upcomingLoading ? (
                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                          ) : null}
                          Voir plus
                        </Button>
                        <p className="text-xs text-slate-400 mt-1">{upcoming.length} sur {upcomingTotal} engagements</p>
                      </div>
                    )}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="past">
                {past.length === 0 ? (
                  <div className="text-center py-12">
                    <History className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">Aucun engagement passé</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {past.map(a => (
                      <EngagementCard key={a.appointment_id} appointment={a} isPast={true} onDelete={handleDeleteClick} onRemind={handleRemind} now={computed.now} />
                    ))}
                    {pastHasMore && (
                      <div className="pt-4 text-center">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={loadMorePast}
                          disabled={pastLoading}
                          className="text-slate-500 hover:text-slate-700"
                          data-testid="load-more-past-btn"
                        >
                          {pastLoading ? (
                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                          ) : null}
                          Voir plus
                        </Button>
                        <p className="text-xs text-slate-400 mt-1">{past.length} sur {pastTotal} engagements</p>
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
                    {/* Global message */}
                    <div className={`px-4 py-3 rounded-lg text-sm font-medium ${
                      analytics.global_tone === 'positive' ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' :
                      analytics.global_tone === 'warning' ? 'bg-amber-50 text-amber-800 border border-amber-200' :
                      'bg-slate-50 text-slate-600 border border-slate-200'
                    }`} data-testid="analytics-global-message">
                      {analytics.global_message}
                    </div>

                    {/* KPI cards */}
                    <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
                      {/* Engagements créés */}
                      <div className="bg-slate-50 rounded-lg p-4 border border-slate-100" data-testid="kpi-engagements">
                        <p className="text-2xl font-bold text-slate-900">{analytics.total_engagements}</p>
                        <p className="text-xs text-slate-500 mt-1">Engagements créés</p>
                      </div>

                      {/* Taux de présence */}
                      <div className="bg-slate-50 rounded-lg p-4 border border-slate-100" data-testid="kpi-presence">
                        <p className="text-2xl font-bold text-slate-900">
                          {analytics.presence_rate !== null ? `${analytics.presence_rate}%` : '—'}
                        </p>
                        <p className="text-xs text-slate-500 mt-1">Taux de présence</p>
                      </div>

                      {/* Taux d'acceptation */}
                      <div className="bg-slate-50 rounded-lg p-4 border border-slate-100" data-testid="kpi-acceptance">
                        <p className="text-2xl font-bold text-slate-900">
                          {analytics.acceptance_rate !== null ? `${analytics.acceptance_rate}%` : '—'}
                        </p>
                        <p className="text-xs text-slate-500 mt-1">Taux d'acceptation</p>
                      </div>

                      {/* Dédommagement personnel */}
                      <div className="bg-slate-50 rounded-lg p-4 border border-slate-100" data-testid="kpi-compensation">
                        <p className="text-2xl font-bold text-slate-900">
                          {(analytics.personal_compensation_cents / 100).toFixed(0)} €
                        </p>
                        <p className="text-xs text-slate-500 mt-1">Dédommagement personnel</p>
                      </div>

                      {/* Impact caritatif */}
                      <div className="bg-slate-50 rounded-lg p-4 border border-slate-100" data-testid="kpi-charity">
                        <p className="text-2xl font-bold text-emerald-700">
                          {(analytics.charity_total_cents / 100).toFixed(0)} €
                        </p>
                        <p className="text-xs text-slate-500 mt-1">Impact caritatif</p>
                      </div>

                      {/* Engagements non honorés */}
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
