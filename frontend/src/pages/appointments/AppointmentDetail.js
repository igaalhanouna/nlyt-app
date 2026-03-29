import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { appointmentAPI, participantAPI, calendarAPI, invitationAPI, attendanceAPI, checkinAPI, modificationAPI, videoEvidenceAPI, proofAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { Loader2, ChevronDown, Activity, Fingerprint, ShieldCheck, Check, X, CreditCard, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import { toast } from 'sonner';
import { parseUTC, utcToLocalInput, localInputToUTC } from '../../utils/dateFormat';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';
import { useAuth } from '../../contexts/AuthContext';

// Sub-components
import AppointmentHeader from './AppointmentHeader';
import AppointmentEssentials from './AppointmentEssentials';
import EngagementSummary from './EngagementSummary';
import FinancialBreakdown from './FinancialBreakdown';
import ParticipantsSection from './ParticipantsSection';
import SecondaryActions from './SecondaryActions';
import CheckinBlock from './CheckinBlock';
import CancelModal from './CancelModal';
import ModificationProposals from './ModificationProposals';
import EditProposalModal from './EditProposalModal';
import ProofSessionsPanel from './ProofSessionsPanel';
import VideoEvidencePanel from './VideoEvidencePanel';
import AttendancePanel from './AttendancePanel';
import EvidenceDashboard from './EvidenceDashboard';

// ── Participant-specific inline components ──

function ParticipantActionBanner({ token, onActionComplete }) {
  const [responding, setResponding] = useState(false);
  const API_URL = process.env.REACT_APP_BACKEND_URL;

  const handleRespond = async (action) => {
    setResponding(true);
    try {
      const resp = await fetch(`${API_URL}/api/invitations/${token}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
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
        toast.success(action === 'accept' ? 'Invitation acceptée' : 'Invitation refusée');
      }
      onActionComplete();
    } catch (err) {
      toast.error(err.message || 'Erreur');
    } finally {
      setResponding(false);
    }
  };

  return (
    <div className="mb-4 bg-blue-50 border border-blue-200 rounded-xl p-4" data-testid="participant-action-banner">
      <p className="text-sm font-semibold text-blue-800 mb-3">Votre réponse est attendue</p>
      <div className="flex gap-2">
        <Button size="sm" className="h-10 bg-emerald-600 hover:bg-emerald-700 text-white" onClick={() => handleRespond('accept')} disabled={responding} data-testid="participant-accept-btn">
          <Check className="w-4 h-4 mr-1.5" /> Accepter
        </Button>
        <Button size="sm" variant="outline" className="h-10 border-slate-200" onClick={() => handleRespond('decline')} disabled={responding} data-testid="participant-decline-btn">
          <X className="w-4 h-4 mr-1.5" /> Refuser
        </Button>
      </div>
    </div>
  );
}

function ParticipantGuaranteeBanner({ token, onActionComplete }) {
  const [processing, setProcessing] = useState(false);
  const API_URL = process.env.REACT_APP_BACKEND_URL;

  const handleFinalize = async () => {
    setProcessing(true);
    try {
      const resp = await fetch(`${API_URL}/api/invitations/${token}/respond`, {
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
        toast.success('Garantie finalisée');
      }
      onActionComplete();
    } catch (err) {
      toast.error(err.message || 'Erreur lors de la finalisation');
    } finally {
      setProcessing(false);
    }
  };

  const handleDecline = async () => {
    setProcessing(true);
    try {
      const resp = await fetch(`${API_URL}/api/invitations/${token}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'decline' }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Erreur');
      toast.success('Invitation refusée');
      onActionComplete();
    } catch (err) {
      toast.error(err.message || 'Erreur');
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="mb-4 bg-amber-50 border border-amber-200 rounded-xl p-4" data-testid="participant-guarantee-banner">
      <p className="text-sm font-semibold text-amber-800 mb-3">Votre garantie n'est pas encore finalisée</p>
      <div className="flex gap-2">
        <Button size="sm" className="h-10 bg-amber-600 hover:bg-amber-700 text-white" onClick={handleFinalize} disabled={processing} data-testid="finalize-guarantee-btn">
          {processing ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <CreditCard className="w-4 h-4 mr-1.5" />}
          Finaliser ma garantie
        </Button>
        <Button size="sm" variant="outline" className="h-10 border-slate-200" onClick={handleDecline} disabled={processing} data-testid="decline-guarantee-btn">
          <X className="w-4 h-4 mr-1.5" /> Refuser
        </Button>
      </div>
    </div>
  );
}

function FinancialResultSection({ appointment, participants, isOrganizer }) {
  const financialSummary = appointment?.financial_summary;
  if (!financialSummary || financialSummary.length === 0) return null;

  const penaltyAmount = appointment?.penalty_amount || 0;
  const currency = (appointment?.penalty_currency || 'eur').toUpperCase();
  const symbol = currency === 'EUR' ? '€' : currency;

  const getName = (pid) => {
    const p = participants?.find(pp => pp.participant_id === pid);
    if (!p) return 'Participant';
    return [p.first_name, p.last_name].filter(Boolean).join(' ') || p.email || 'Participant';
  };

  const formatAmount = (cents) => {
    if (!cents || cents <= 0) return null;
    return `${(cents / 100).toFixed(2)} ${symbol}`;
  };

  // Sort: penalized first, then compensated, then on_time, then review
  const sorted = [...financialSummary].sort((a, b) => {
    const order = { no_show: 0, late_penalized: 1, late: 2, on_time: 3, manual_review: 4, waived: 5 };
    return (order[a.outcome] ?? 5) - (order[b.outcome] ?? 5);
  });

  return (
    <div className="mb-4 bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid="financial-result-section">
      <div className="px-4 py-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <CreditCard className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-semibold text-slate-900">Resultat financier</span>
        </div>
      </div>
      <div className="divide-y divide-slate-50">
        {sorted.map((f) => {
          const name = getName(f.participant_id);
          const isPenalized = (f.outcome === 'late_penalized' || f.outcome === 'no_show') && !f.review_required;
          const isCompensated = f.compensation_received_cents > 0;
          const isOnTime = (f.outcome === 'on_time' || f.outcome === 'late') && !f.review_required;
          const isWaived = f.outcome === 'waived';
          const isReview = f.review_required;
          const capturedCents = f.capture_amount_cents || (f.penalty_amount ? f.penalty_amount * 100 : 0);

          let statusIcon, statusColor, statusBg, statusText, explanation;

          if (isPenalized) {
            statusIcon = <AlertTriangle className="w-4 h-4" />;
            statusColor = 'text-red-700';
            statusBg = 'bg-red-50';
            statusText = f.outcome === 'no_show' ? 'Absent' : `En retard pénalisé (${Math.round(f.delay_minutes || 0)} min)`;
            explanation = `Penalise de ${formatAmount(capturedCents) || penaltyAmount + ' ' + symbol}`;
            if (f.captured) {
              explanation += ' — montant preleve';
            } else if (f.guarantee_status === 'completed') {
              explanation += ' — prelevement en cours';
            }
            if (isCompensated) {
              explanation += `. Compensation recue de ${formatAmount(f.compensation_received_cents)} (en tant qu'organisateur)`;
            }
          } else if (isCompensated && isOnTime) {
            statusIcon = <CheckCircle className="w-4 h-4" />;
            statusColor = 'text-emerald-700';
            statusBg = 'bg-emerald-50';
            statusText = 'Present';
            explanation = `Compensation recue : +${formatAmount(f.compensation_received_cents)}`;
          } else if (isOnTime) {
            statusIcon = <CheckCircle className="w-4 h-4" />;
            statusColor = 'text-emerald-700';
            statusBg = 'bg-emerald-50';
            statusText = 'Present';
            explanation = 'Engagement respecte — garantie liberee';
          } else if (isWaived) {
            statusIcon = <CheckCircle className="w-4 h-4" />;
            statusColor = 'text-slate-500';
            statusBg = 'bg-slate-50';
            statusText = 'Dispense';
            explanation = 'Aucune penalite applicable';
          } else if (isReview) {
            statusIcon = <Clock className="w-4 h-4" />;
            statusColor = 'text-amber-700';
            statusBg = 'bg-amber-50';
            statusText = 'En cours de verification';
            explanation = 'Decision en attente — aucune action financiere pour le moment';
          } else {
            statusIcon = <CreditCard className="w-4 h-4" />;
            statusColor = 'text-slate-500';
            statusBg = 'bg-slate-50';
            statusText = f.outcome || 'Inconnu';
            explanation = '';
          }

          return (
            <div key={f.participant_id} className="px-4 py-3" data-testid={`financial-row-${f.participant_id}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-900">{name}</p>
                  <div className={`inline-flex items-center gap-1.5 mt-1 text-xs font-medium px-2 py-0.5 rounded-full ${statusColor} ${statusBg}`}>
                    {statusIcon}
                    {statusText}
                  </div>
                  {explanation && (
                    <p className="text-xs text-slate-500 mt-1.5">{explanation}</p>
                  )}
                </div>

                {/* Amount column */}
                <div className="flex-shrink-0 text-right space-y-1">
                  {isPenalized && capturedCents > 0 && (
                    <div data-testid={`penalty-amount-${f.participant_id}`}>
                      <span className="text-base font-bold text-red-600">
                        -{formatAmount(capturedCents)}
                      </span>
                      <span className="block text-[10px] text-slate-400 mt-0.5">penalite</span>
                    </div>
                  )}
                  {isCompensated && (
                    <div data-testid={`compensation-amount-${f.participant_id}`}>
                      <span className="text-base font-bold text-emerald-600">
                        +{formatAmount(f.compensation_received_cents)}
                      </span>
                      <span className="block text-[10px] text-slate-400 mt-0.5">compensation</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Distribution breakdown (only for penalized, organizer view) */}
              {isPenalized && f.beneficiaries?.length > 0 && isOrganizer && (
                <div className="mt-2.5 bg-slate-50 rounded-lg p-3">
                  <span className="text-xs font-semibold text-slate-600 mb-1.5 block">Repartition de la penalite</span>
                  {f.beneficiaries.map((b, i) => {
                    const roleLabel = {
                      organizer: 'Organisateur',
                      affected: 'Participant(s) present(s)',
                      charity: 'Association caritative',
                      platform: 'Commission plateforme',
                    }[b.role] || b.role;
                    return (
                      <div key={i} className="flex justify-between text-xs py-0.5">
                        <span className="text-slate-600">{roleLabel}</span>
                        <span className="font-medium text-slate-800">+{formatAmount(b.amount_cents)}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function AppointmentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const cameFromDisputes = location.state?.from === 'litiges';
  const cameFromPresences = location.state?.from === 'presences';
  const cameFromContributions = location.state?.from === 'contributions';
  const cameFromAgenda = location.state?.from === 'agenda';
  const fromTab = location.state?.fromTab;
  const { user } = useAuth();

  const TAB_LABELS = { upcoming: 'A venir', past: 'Historique', action_required: 'Action requise', stats: 'Statistiques' };
  const backLabel = fromTab ? TAB_LABELS[fromTab] || 'Tableau de bord' : null;
  const backHref = fromTab ? `/dashboard?tab=${fromTab}` : '/dashboard';

  // Core state
  const [appointment, setAppointment] = useState(null);
  const [participants, setParticipants] = useState([]);
  const [loading, setLoading] = useState(true);

  // UI state
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [resendingToken, setResendingToken] = useState(null);

  // Calendar sync
  const [syncStatus, setSyncStatus] = useState({ google: { synced: false, has_connection: false }, outlook: { synced: false, has_connection: false } });
  const [syncingProvider, setSyncingProvider] = useState(null);

  // Attendance (read-only)
  const [attendance, setAttendance] = useState(null);
  const [evidenceData, setEvidenceData] = useState(null);

  // Modification proposals
  const [activeProposal, setActiveProposal] = useState(null);
  const [proposalHistory, setProposalHistory] = useState([]);
  const [showProposalForm, setShowProposalForm] = useState(false);
  const [proposalForm, setProposalForm] = useState({ start_datetime: '', duration_minutes: '', location: '', meeting_provider: null, appointment_type: '' });
  const [submittingProposal, setSubmittingProposal] = useState(false);
  const [respondingProposal, setRespondingProposal] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  // Organizer check-in
  const [organizerParticipant, setOrganizerParticipant] = useState(null);
  const [organizerCheckinDone, setOrganizerCheckinDone] = useState(false);
  const [organizerCheckinData, setOrganizerCheckinData] = useState(null);
  const [checkingIn, setCheckingIn] = useState(false);

  // Video evidence
  const [videoEvidence, setVideoEvidence] = useState(null);
  const [showVideoIngest, setShowVideoIngest] = useState(false);
  const [videoIngestForm, setVideoIngestForm] = useState({ provider: 'zoom', external_meeting_id: '', meeting_join_url: '', raw_json: '' });
  const [ingestingVideo, setIngestingVideo] = useState(false);
  const [videoIngestionLogs, setVideoIngestionLogs] = useState([]);
  const [creatingMeeting, setCreatingMeeting] = useState(false);
  const [fetchingAttendance, setFetchingAttendance] = useState(false);
  const [fetchAttendanceError, setFetchAttendanceError] = useState(null);

  // Proof sessions
  const [proofSessions, setProofSessions] = useState([]);
  const [validatingSession, setValidatingSession] = useState(null);

  // File ingest
  const [ingestMode, setIngestMode] = useState('file');
  const [selectedFile, setSelectedFile] = useState(null);
  const [csvPreview, setCsvPreview] = useState(null);
  const [uploadingFile, setUploadingFile] = useState(false);

  // Guarantee
  const [resumingGuarantee, setResumingGuarantee] = useState(false);
  const [checkingActivation, setCheckingActivation] = useState(false);

  // ─── Data Loading ───
  useEffect(() => { loadData(); }, [id]);

  const loadData = async () => {
    try {
      const [appointmentRes, participantsRes] = await Promise.all([
        appointmentAPI.get(id), participantAPI.list(id)
      ]);
      const apt = appointmentRes.data;
      setAppointment(apt);
      const allParticipants = participantsRes.data.participants || [];
      setParticipants(allParticipants);

      const viewerIsOrganizer = apt.viewer_role !== 'participant';
      const orgP = allParticipants.find(p => p.is_organizer === true);
      setOrganizerParticipant(orgP || null);

      // Organizer check-in status — only fetch for organizer viewers
      if (viewerIsOrganizer && orgP?.invitation_token) {
        checkinAPI.getStatus(id, orgP.invitation_token).then(res => {
          if (res.data?.evidence_count > 0) {
            setOrganizerCheckinDone(true);
            const gpsEv = res.data.evidence?.find(e => e.source === 'gps' || e.derived_facts?.latitude);
            if (gpsEv) setOrganizerCheckinData(gpsEv);
          }
        }).catch(() => {});
      }

      // Shared loads (both roles see the same evidence + attendance)
      checkinAPI.getEvidence(id).then(res => setEvidenceData(res.data)).catch(() => {});
      attendanceAPI.get(id).then(res => setAttendance(res.data)).catch(() => {});
      modificationAPI.getActive(id).then(res => setActiveProposal(res.data?.proposal || null)).catch(() => {});
      modificationAPI.getForAppointment(id).then(res => setProposalHistory(res.data?.proposals || [])).catch(() => {});
      proofAPI.getSessions(id).then(res => setProofSessions(res.data?.sessions || [])).catch(() => {});

      // Calendar sync — loaded for the current viewer (backend uses viewer's own connections)
      calendarAPI.getSyncStatus(id).then(res => setSyncStatus(res.data)).catch(() => {});

      // Organizer-only loads
      if (viewerIsOrganizer) {
        videoEvidenceAPI.get(id).then(res => setVideoEvidence(res.data)).catch(() => {});
        videoEvidenceAPI.getLogs(id).then(res => setVideoIngestionLogs(res.data?.logs || [])).catch(() => {});
      }
    } catch { toast.error('Erreur lors du chargement'); }
    finally { setLoading(false); }
  };

  // ─── Polling: reload every 30s when appointment is active ───
  useEffect(() => {
    if (!appointment || loading) return;
    const start = parseUTC(appointment.start_datetime);
    if (!start) return;
    const end = new Date(start.getTime() + (appointment.duration_minutes || 60) * 60000);
    const now = new Date();
    // Only poll if appointment is upcoming (< 2h before) or ongoing
    const twoHoursBefore = new Date(start.getTime() - 2 * 3600000);
    if (now < twoHoursBefore || now > new Date(end.getTime() + 3600000)) return;

    let intervalId;
    const poll = () => {
      if (document.hidden) return;
      // Silent refresh — don't set loading
      Promise.all([
        participantAPI.list(id),
        checkinAPI.getEvidence(id),
        attendanceAPI.get(id),
        proofAPI.getSessions(id),
      ]).then(([partRes, evRes, attRes, proofRes]) => {
        setParticipants(partRes.data.participants || []);
        setEvidenceData(evRes.data);
        setAttendance(attRes.data);
        setProofSessions(proofRes.data?.sessions || []);
      }).catch(() => {});
    };
    intervalId = setInterval(poll, 30000);
    return () => clearInterval(intervalId);
  }, [appointment?.appointment_id, loading]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Handlers ───
  const handleOrganizerCheckin = async () => {
    if (!organizerParticipant?.invitation_token) return;
    setCheckingIn(true);
    try {
      const payload = { appointment_id: id, invitation_token: organizerParticipant.invitation_token, device_info: navigator.userAgent };
      if (appointment.appointment_type === 'physical' && navigator.geolocation) {
        try {
          const pos = await new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 8000, enableHighAccuracy: true }));
          payload.latitude = pos.coords.latitude; payload.longitude = pos.coords.longitude; payload.gps_consent = true;
        } catch (geoErr) {
          if (geoErr.code === 1) toast.warning('Localisation refusée. Check-in enregistré sans GPS.');
          else toast.warning('GPS indisponible. Check-in enregistré sans coordonnées.');
        }
      }
      await checkinAPI.manual(payload);
      setOrganizerCheckinDone(true);
      toast.success('Check-in organisateur enregistré');
      loadData();
    } catch (error) {
      const status = error.response?.status;
      const detail = error.response?.data?.detail;
      if (status === 409) { toast.info('Check-in déjà effectué.'); setOrganizerCheckinDone(true); }
      else if (status === 400) toast.error(detail || "Impossible d'effectuer le check-in.");
      else if (!error.response) toast.error('Impossible de contacter le serveur.');
      else toast.error(detail || 'Erreur lors du check-in.');
    } finally { setCheckingIn(false); }
  };

  const handleSyncCalendar = async (provider) => {
    setSyncingProvider(provider);
    const label = provider === 'google' ? 'Google Calendar' : 'Outlook Calendar';
    try {
      const response = await calendarAPI.syncAppointment(id, provider);
      setSyncStatus(prev => ({ ...prev, [provider]: { synced: true, out_of_sync: false, has_connection: true, html_link: response.data.html_link, external_event_id: response.data.external_event_id, sync_source: 'manual' } }));
      toast.success(`Synchronisé avec ${label}`);
    } catch (error) {
      const detail = error.response?.data?.detail;
      if (detail?.includes('non connecté')) toast.error(`${label} non connecté. Allez dans Paramètres > Intégrations.`);
      else if (error.response?.status === 401) toast.error(`Session ${label} expirée. Reconnectez dans Paramètres.`);
      else toast.error(detail || `Erreur de synchronisation ${label}`);
    } finally { setSyncingProvider(null); }
  };

  const handleCancelAppointment = async () => {
    setCancelling(true);
    try {
      const response = await appointmentAPI.cancel(id);
      toast.success(`Annulé. ${response.data.participants_notified} participant(s) notifié(s).`);
      setShowCancelModal(false);
      loadData();
    } catch (error) { toast.error(error.response?.data?.detail || "Erreur lors de l'annulation"); }
    finally { setCancelling(false); }
  };

  const handleResendInvitation = async (token) => {
    setResendingToken(token);
    try { await invitationAPI.resend(token); toast.success('Invitation renvoyée'); }
    catch (error) { toast.error(error.response?.data?.detail || "Erreur lors du renvoi"); }
    finally { setResendingToken(null); }
  };

  const handleValidateSession = async (sessionId, status) => {
    setValidatingSession(sessionId);
    try {
      await proofAPI.validate(id, sessionId, status);
      toast.success(`Session validée : ${status === 'present' ? 'Présent' : status === 'partial' ? 'Partiel' : 'Absent'}`);
      const res = await proofAPI.getSessions(id);
      setProofSessions(res.data?.sessions || []);
    } catch (error) { toast.error(error.response?.data?.detail || "Erreur lors de la validation"); }
    finally { setValidatingSession(null); }
  };

  const handleResumeGuarantee = async () => {
    setResumingGuarantee(true);
    try {
      const res = await appointmentAPI.retryGuarantee(id);
      if (res.data.status === 'active' && res.data.activated) { toast.success('Garantie validée ! Invitations envoyées.'); await loadData(); }
      else if (res.data.checkout_url) { toast.info('Redirection vers Stripe...'); window.location.href = res.data.checkout_url; }
      else { toast.info(res.data.message || 'Statut mis à jour'); await loadData(); }
    } catch (error) { const msg = error.response?.data?.detail || 'Erreur'; toast.error(typeof msg === 'string' ? msg : JSON.stringify(msg)); }
    finally { setResumingGuarantee(false); }
  };

  const handleCheckActivation = async () => {
    setCheckingActivation(true);
    try {
      const res = await appointmentAPI.checkActivation(id);
      if (res.data.status === 'active' || res.data.activated) { toast.success('Rendez-vous activé !'); await loadData(); }
      else toast.info('Garantie en cours de validation...');
    } catch { toast.error('Erreur lors de la vérification'); }
    finally { setCheckingActivation(false); }
  };

  const handleDownloadICS = () => { window.open(calendarAPI.exportICS(id), '_blank'); toast.success('Fichier iCalendar téléchargé'); };

  // Modification proposal handlers
  const handleOpenProposalForm = () => {
    setProposalForm({
      start_datetime: utcToLocalInput(appointment.start_datetime),
      duration_minutes: String(appointment.duration_minutes || 60),
      location: appointment.location || '',
      meeting_provider: appointment.meeting_provider || '',
      appointment_type: appointment.appointment_type || 'physical'
    });
    setShowProposalForm(true);
  };

  const handleSubmitProposal = async () => {
    const changes = {};
    const utcDt = localInputToUTC(proposalForm.start_datetime);
    if (utcDt && utcDt !== appointment.start_datetime) changes.start_datetime = utcDt;
    if (proposalForm.duration_minutes && Number(proposalForm.duration_minutes) !== appointment.duration_minutes) changes.duration_minutes = Number(proposalForm.duration_minutes);
    if (proposalForm.location !== (appointment.location || '')) changes.location = proposalForm.location;
    if (proposalForm.meeting_provider !== (appointment.meeting_provider || '')) changes.meeting_provider = proposalForm.meeting_provider;
    if (proposalForm.appointment_type !== (appointment.appointment_type || '')) changes.appointment_type = proposalForm.appointment_type;
    if (!Object.keys(changes).length) { toast.error('Aucune modification détectée'); return; }
    if (changes.start_datetime && new Date(changes.start_datetime) <= new Date()) { toast.error("La nouvelle date doit être dans le futur"); return; }
    setSubmittingProposal(true);
    try { const res = await modificationAPI.create({ appointment_id: id, changes }); toast.success(res.data?.mode === 'direct' ? 'Modification appliquée' : 'Proposition envoyée'); setShowProposalForm(false); loadData(); }
    catch (err) { toast.error(err.response?.data?.detail || 'Erreur'); }
    finally { setSubmittingProposal(false); }
  };

  const handleRespondProposal = async (proposalId, action) => {
    setRespondingProposal(true);
    try { await modificationAPI.respond(proposalId, { action }); toast.success(action === 'accept' ? 'Modification acceptée' : 'Modification refusée'); loadData(); }
    catch (err) { toast.error(err.response?.data?.detail || 'Erreur'); }
    finally { setRespondingProposal(false); }
  };

  const handleCancelProposal = async (proposalId) => {
    try { await modificationAPI.cancel(proposalId); toast.success('Proposition annulée'); loadData(); }
    catch (err) { toast.error(err.response?.data?.detail || 'Erreur'); }
  };

  // Video evidence handlers
  const handleVideoIngest = async () => {
    let parsed;
    try { parsed = JSON.parse(videoIngestForm.raw_json); } catch { toast.error('JSON invalide.'); return; }
    setIngestingVideo(true);
    try {
      const res = await videoEvidenceAPI.ingest(id, { provider: videoIngestForm.provider, external_meeting_id: videoIngestForm.external_meeting_id || undefined, meeting_join_url: videoIngestForm.meeting_join_url || undefined, raw_payload: parsed });
      toast.success(`Ingestion : ${res.data.records_created} preuve(s)`);
      setShowVideoIngest(false); setVideoIngestForm({ provider: 'zoom', external_meeting_id: '', meeting_join_url: '', raw_json: '' }); loadData();
    } catch (err) { toast.error(err.response?.data?.detail || "Erreur lors de l'ingestion"); }
    finally { setIngestingVideo(false); }
  };

  const handleCreateMeeting = async () => {
    setCreatingMeeting(true);
    try {
      const res = await videoEvidenceAPI.createMeeting(id);
      if (res.data.already_exists) toast.info('La réunion existe déjà.');
      else toast.success(`Réunion ${res.data.provider} créée !`);
      loadData();
    } catch (err) { toast.error(err.response?.data?.detail || 'Erreur'); }
    finally { setCreatingMeeting(false); }
  };

  const handleFetchAttendance = async () => {
    setFetchingAttendance(true); setFetchAttendanceError(null);
    try {
      const res = await videoEvidenceAPI.fetchAttendance(id);
      if (res.data.ingestion_result) toast.success(`Présences récupérées : ${res.data.ingestion_result.records_created || 0} preuve(s)`);
      else toast.success('Données récupérées.');
      loadData();
    } catch (err) {
      const detail = err.response?.data?.detail || 'Erreur';
      setFetchAttendanceError({ message: detail, isPlanError: detail.toLowerCase().includes('paid'), isLegacyError: detail.toLowerCase().includes('legacy') });
      if (!detail.toLowerCase().includes('paid')) toast.error(detail);
    } finally { setFetchingAttendance(false); }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedFile(file); setCsvPreview(null);
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target.result;
      try {
        if (file.name.endsWith('.csv')) {
          const lines = text.split('\n').filter(l => l.trim());
          const headers = lines[0]?.split(',').map(h => h.trim().replace(/"/g, ''));
          const rows = lines.slice(1, 6).map(line => { const vals = line.split(',').map(v => v.trim().replace(/"/g, '')); const obj = {}; headers.forEach((h, i) => { obj[h] = vals[i] || ''; }); return obj; });
          setCsvPreview({ type: 'csv', headers, rows, total: lines.length - 1 });
        } else {
          const json = JSON.parse(text);
          const pts = json.participants || json.attendanceRecords || [];
          setCsvPreview({ type: 'json', total: pts.length, participants: pts.slice(0, 5) });
        }
      } catch { setCsvPreview({ type: 'error', message: 'Impossible de lire le fichier' }); }
    };
    reader.readAsText(file);
  };

  const handleFileUpload = async () => {
    if (!selectedFile) return;
    setUploadingFile(true);
    try {
      const formData = new FormData(); formData.append('file', selectedFile); formData.append('provider', videoIngestForm.provider);
      const res = await videoEvidenceAPI.ingestFile(id, formData);
      toast.success(`Import : ${res.data.records_created} preuve(s)`);
      setSelectedFile(null); setCsvPreview(null); setShowVideoIngest(false); loadData();
    } catch (err) { toast.error(err.response?.data?.detail || "Erreur lors de l'import"); }
    finally { setUploadingFile(false); }
  };

  // ─── Computed Values ───
  if (loading) return <div className="min-h-screen flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-slate-400" /></div>;
  if (!appointment) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <p className="text-slate-600 mb-4">Rendez-vous introuvable</p>
        <Button onClick={() => navigate(backHref)}>Retour au tableau de bord</Button>
      </div>
    </div>
  );

  const isCancelled = appointment.status === 'cancelled';
  const isPendingGuarantee = appointment.status === 'pending_organizer_guarantee';
  const acceptedCount = participants.filter(p => ['accepted', 'accepted_pending_guarantee', 'accepted_guaranteed'].includes(p.status)).length;
  const pendingCount = participants.filter(p => p.status === 'invited').length;
  const guaranteedCount = participants.filter(p => p.status === 'accepted_guaranteed').length;

  // Viewer role: organizer sees everything, participant sees read-only
  const isOrganizer = appointment.viewer_role !== 'participant';
  const viewerParticipantStatus = appointment.viewer_participant_status;
  const viewerInvitationToken = appointment.viewer_invitation_token;

  const isEnded = (() => {
    if (!appointment?.start_datetime) return false;
    const start = parseUTC(appointment.start_datetime);
    if (!start) return false;
    return new Date() > new Date(start.getTime() + (appointment.duration_minutes || 60) * 60000);
  })();

  const canEdit = !isCancelled && !activeProposal && !isEnded;

  // Determine if modification will be direct (no vote) or proposal (vote needed)
  const ACCEPTED_STATUSES = ['accepted', 'accepted_pending_guarantee', 'accepted_guaranteed', 'guaranteed'];
  const hasAcceptedNonOrgParticipants = participants.some(
    p => !p.is_organizer && ACCEPTED_STATUSES.includes(p.status)
  );
  const isDirectModification = !hasAcceptedNonOrgParticipants;

  // Viewer's participant record (for participants responding to proposals)
  const viewerParticipant = participants.find(p => p.user_id === user?.user_id && !p.is_organizer);
  const viewerCanPropose = !isOrganizer && canEdit && viewerParticipant
    && ACCEPTED_STATUSES.includes(viewerParticipant.status);

  // Proof summary for <details>
  const proofSessionCount = proofSessions.length;
  const validatedCount = proofSessions.filter(s => s.validated_status).length;
  const proofSummary = proofSessionCount > 0
    ? `${proofSessionCount} session${proofSessionCount > 1 ? 's' : ''} · ${validatedCount} validée${validatedCount > 1 ? 's' : ''}`
    : 'Aucune session';

  // ─── Render ───
  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <AppBreadcrumb items={
        cameFromPresences
          ? [{ label: 'Tableau de bord', href: '/dashboard' }, { label: 'Présences', href: '/presences' }, { label: appointment.title }]
          : cameFromDisputes
            ? [{ label: 'Tableau de bord', href: '/dashboard' }, { label: 'Litiges', href: '/litiges' }, { label: appointment.title }]
            : cameFromContributions
              ? [{ label: 'Tableau de bord', href: '/dashboard' }, { label: 'Contributions', href: '/mes-resultats' }, { label: appointment.title }]
              : cameFromAgenda
                ? [{ label: 'Agenda', href: '/agenda' }, { label: appointment.title }]
                : fromTab
                  ? [{ label: 'Tableau de bord', href: backHref }, { label: backLabel, href: backHref }, { label: appointment.title }]
                  : [{ label: 'Tableau de bord', href: '/dashboard' }, { label: appointment.title }]
      } />

      <div className="max-w-6xl mx-auto px-4 md:px-6 pb-12">

        {/* #1 — Header + CTA */}
        <AppointmentHeader
          appointment={appointment} isCancelled={isCancelled} isPendingGuarantee={isPendingGuarantee}
          organizerParticipant={organizerParticipant} organizerCheckinDone={organizerCheckinDone} checkingIn={checkingIn}
          handleOrganizerCheckin={isOrganizer ? handleOrganizerCheckin : undefined}
          handleResumeGuarantee={isOrganizer ? handleResumeGuarantee : undefined} resumingGuarantee={resumingGuarantee}
          handleCheckActivation={isOrganizer ? handleCheckActivation : undefined} checkingActivation={checkingActivation} navigate={navigate}
          isOrganizer={isOrganizer}
        />

        {/* Participant action banner — accept/decline if invited */}
        {!isOrganizer && viewerParticipantStatus === 'invited' && !isCancelled && (
          <ParticipantActionBanner token={viewerInvitationToken} onActionComplete={() => {
            setLoading(true);
            appointmentAPI.get(id).then(res => { setAppointment(res.data); setLoading(false); }).catch(() => setLoading(false));
          }} />
        )}

        {/* Participant guarantee banner — finalize or decline if accepted_pending_guarantee */}
        {!isOrganizer && viewerParticipantStatus === 'accepted_pending_guarantee' && !isCancelled && (
          <ParticipantGuaranteeBanner token={viewerInvitationToken} onActionComplete={() => {
            setLoading(true);
            appointmentAPI.get(id).then(res => { setAppointment(res.data); setLoading(false); }).catch(() => setLoading(false));
          }} />
        )}

        {/* Declarative phase CTA */}
        {appointment.declarative_phase === 'collecting' && (
          <div className="mb-4 flex items-center justify-between gap-3 px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg" data-testid="declarative-cta-banner">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
              <p className="text-xs font-medium text-amber-700">
                Certaines présences n'ont pas pu être vérifiées automatiquement. Aidez-nous en confirmant ce que vous avez observé.
              </p>
            </div>
            <button
              onClick={() => navigate('/presences')}
              className="flex-shrink-0 px-3 py-1.5 bg-amber-600 text-white text-xs font-medium rounded-lg hover:bg-amber-700 transition-colors"
              data-testid="go-to-sheet-btn"
            >
              Aller aux déclarations
            </button>
          </div>
        )}

        {/* Dispute active CTA */}
        {appointment.declarative_phase === 'disputed' && (
          <div className="mb-4 flex items-center justify-between gap-3 px-4 py-3 bg-red-50 border border-red-200 rounded-lg" data-testid="dispute-active-banner">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0" />
              <p className="text-xs font-medium text-red-700">
                Un litige est en cours pour ce rendez-vous suite à des déclarations divergentes.
              </p>
            </div>
            <button
              onClick={() => navigate('/litiges')}
              className="flex-shrink-0 px-3 py-1.5 bg-red-600 text-white text-xs font-medium rounded-lg hover:bg-red-700 transition-colors"
              data-testid="go-to-disputes-btn"
            >
              Voir le litige
            </button>
          </div>
        )}

        {/* Modification banner — TOP POSITION for immediate visibility */}
        {activeProposal && activeProposal.status === 'pending' && (
          <ModificationProposals
            activeProposal={activeProposal}
            respondingProposal={respondingProposal} onRespondProposal={handleRespondProposal} onCancelProposal={handleCancelProposal}
            proposalHistory={[]} showHistory={false} setShowHistory={() => {}}
            viewerParticipantId={viewerParticipant?.participant_id}
            isOrganizer={isOrganizer}
          />
        )}

        {/* #2 — Essentials (date, lieu, lien, confiance) */}
        <AppointmentEssentials
          appointment={appointment} isCancelled={isCancelled} organizerParticipant={organizerParticipant}
          guaranteedCount={guaranteedCount} canEdit={(isOrganizer || viewerCanPropose) && canEdit} onEdit={(isOrganizer || viewerCanPropose) ? handleOpenProposalForm : undefined}
        />

        {/* #3 — Actions (calendrier, annuler) — available for both roles */}
        <SecondaryActions
          appointment={appointment} isCancelled={isCancelled}
          syncStatus={syncStatus} syncingProvider={syncingProvider}
          onSyncCalendar={handleSyncCalendar}
          onDownloadICS={handleDownloadICS}
          onShowCancelModal={isOrganizer ? () => setShowCancelModal(true) : undefined}
          isOrganizer={isOrganizer}
          viewerInvitationToken={viewerInvitationToken}
          viewerParticipantStatus={viewerParticipantStatus}
          onParticipantCancelComplete={loadData}
        />

        {/* #4 — Engagement financier */}
        <EngagementSummary appointment={appointment} isCancelled={isCancelled} />
        <FinancialBreakdown appointment={appointment} isCancelled={isCancelled} />

        {/* #5 — Participants */}
        <ParticipantsSection
          participants={participants} isCancelled={isCancelled} appointmentId={id}
          resendingToken={isOrganizer ? resendingToken : null} onResend={isOrganizer ? handleResendInvitation : undefined}
          acceptedCount={acceptedCount} pendingCount={pendingCount} guaranteedCount={guaranteedCount}
          isOrganizer={isOrganizer}
        />

        {/* #6 — Check-in / Confirmation — unified for both roles */}
        <CheckinBlock
          appointment={appointment}
          participantRecord={isOrganizer ? organizerParticipant : { invitation_token: viewerInvitationToken, status: viewerParticipantStatus }}
          isOrganizer={isOrganizer}
          onCheckinComplete={loadData}
          isCancelled={isCancelled}
          isPendingGuarantee={isPendingGuarantee}
          initialCheckinDone={isOrganizer ? organizerCheckinDone : false}
          initialCheckinData={isOrganizer ? organizerCheckinData : null}
        />

        {/* #7 — Preuves & Tracking — visible for both roles (read-only for participant) */}
        {!isCancelled && (
          <details className="mb-4 bg-white border border-slate-200 rounded-xl overflow-hidden group" data-testid="proof-tracking-details">
            <summary className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-slate-50 transition-colors select-none min-h-[44px]">
              <div className="flex items-center gap-2">
                <Fingerprint className="w-4 h-4 text-slate-400" />
                <span className="text-sm font-semibold text-slate-900">Preuves de présence</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">{proofSummary}</span>
                <ChevronDown className="w-4 h-4 text-slate-400 transition-transform group-open:rotate-180" />
              </div>
            </summary>
            <div className="border-t border-slate-100 p-0">
              {appointment.appointment_type === 'physical' && (
                <EvidenceDashboard participants={participants} evidenceData={evidenceData} appointment={appointment} />
              )}
              {appointment.appointment_type === 'video' && (
                <EvidenceDashboard participants={participants} evidenceData={evidenceData} appointment={appointment} />
              )}
              {appointment.appointment_type === 'video' && (
                <ProofSessionsPanel participants={participants} proofSessions={proofSessions} validatingSession={validatingSession} onValidateSession={isOrganizer ? handleValidateSession : undefined} />
              )}
              {isOrganizer && appointment.appointment_type === 'video' && (
                <VideoEvidencePanel
                  appointment={appointment} videoEvidence={videoEvidence} videoIngestionLogs={videoIngestionLogs}
                  showVideoIngest={showVideoIngest} setShowVideoIngest={setShowVideoIngest}
                  videoIngestForm={videoIngestForm} setVideoIngestForm={setVideoIngestForm}
                  ingestMode={ingestMode} setIngestMode={setIngestMode}
                  selectedFile={selectedFile} setSelectedFile={setSelectedFile}
                  csvPreview={csvPreview} setCsvPreview={setCsvPreview}
                  creatingMeeting={creatingMeeting} onCreateMeeting={handleCreateMeeting}
                  fetchingAttendance={fetchingAttendance} onFetchAttendance={handleFetchAttendance}
                  fetchAttendanceError={fetchAttendanceError} setFetchAttendanceError={setFetchAttendanceError}
                  ingestingVideo={ingestingVideo} onVideoIngest={handleVideoIngest}
                  uploadingFile={uploadingFile} onFileUpload={handleFileUpload}
                  onFileSelect={handleFileSelect}
                />
              )}
              {isOrganizer && isEnded && (
                <AttendancePanel
                  attendance={attendance}
                  participants={participants}
                  declarativePhase={appointment.declarative_phase}
                />
              )}
            </div>
          </details>
        )}

        {/* #7b — Résultat financier — visible for both roles */}
        {appointment.attendance_evaluated && appointment.financial_summary && (
          <FinancialResultSection appointment={appointment} participants={participants} isOrganizer={isOrganizer} />
        )}

        {/* #8 — Modal de modification (organisateur only) */}
        {isOrganizer && (
          <EditProposalModal
            open={showProposalForm} onClose={() => setShowProposalForm(false)}
            proposalForm={proposalForm} setProposalForm={setProposalForm}
            submittingProposal={submittingProposal} onSubmitProposal={handleSubmitProposal}
            isDirect={isDirectModification}
          />
        )}

        {/* #9 — Historique des modifications */}
        {proposalHistory.length > 0 && (
          <details className="mb-4 bg-white border border-slate-200 rounded-xl overflow-hidden group" data-testid="modifications-details">
            <summary className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-slate-50 transition-colors select-none min-h-[44px]">
              <span className="text-sm font-semibold text-slate-900">Historique des modifications</span>
              <ChevronDown className="w-4 h-4 text-slate-400 transition-transform group-open:rotate-180" />
            </summary>
            <div className="border-t border-slate-100">
              <ModificationProposals
                activeProposal={null}
                respondingProposal={false} onRespondProposal={() => {}} onCancelProposal={() => {}}
                proposalHistory={proposalHistory} showHistory={true} setShowHistory={() => {}}
                viewerParticipantId={viewerParticipant?.participant_id}
                isOrganizer={isOrganizer}
              />
            </div>
          </details>
        )}
      </div>

      {isOrganizer && (
        <CancelModal
          show={showCancelModal} onClose={() => setShowCancelModal(false)}
          onConfirm={handleCancelAppointment} cancelling={cancelling}
          participantCount={participants.length}
        />
      )}
    </div>
  );
}
