import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { appointmentAPI, participantAPI, calendarAPI, invitationAPI, attendanceAPI, checkinAPI, modificationAPI, videoEvidenceAPI, proofAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { Loader2, ChevronDown, Activity, Fingerprint, ShieldCheck, Check, X } from 'lucide-react';
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
import OrganizerCheckinBlock from './OrganizerCheckinBlock';
import CancelModal from './CancelModal';
import ModificationProposals from './ModificationProposals';
import EditProposalModal from './EditProposalModal';
import ProofSessionsPanel from './ProofSessionsPanel';
import VideoEvidencePanel from './VideoEvidencePanel';
import AttendancePanel from './AttendancePanel';
import EvidenceDashboard from './EvidenceDashboard';
import ResultCardSection from './ResultCardSection';

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

function ParticipantCheckinBlock({ appointmentId, viewerParticipantId, viewerInvitationToken }) {
  const [checkinDone, setCheckinDone] = useState(false);
  const [checkingIn, setCheckingIn] = useState(false);

  useEffect(() => {
    if (!viewerInvitationToken) return;
    checkinAPI.getStatus(appointmentId, viewerInvitationToken).then(res => {
      const myCheckin = (res.data?.checkins || []).find(c => c.participant_id === viewerParticipantId);
      if (myCheckin) setCheckinDone(true);
    }).catch(() => {});
  }, [appointmentId, viewerParticipantId, viewerInvitationToken]);

  const handleCheckin = async () => {
    setCheckingIn(true);
    try {
      await checkinAPI.manual({
        appointment_id: appointmentId,
        participant_id: viewerParticipantId,
        method: 'manual',
        source: 'participant_self',
      });
      setCheckinDone(true);
      toast.success('Check-in confirmé');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Erreur lors du check-in');
    } finally {
      setCheckingIn(false);
    }
  };

  return (
    <div className="mb-4 bg-white border border-slate-200 rounded-xl p-4" data-testid="participant-checkin-block">
      <h3 className="text-sm font-semibold text-slate-900 mb-2">Votre check-in</h3>
      {checkinDone ? (
        <div className="flex items-center gap-2 text-emerald-600 text-sm">
          <Check className="w-4 h-4" /> Check-in confirmé
        </div>
      ) : (
        <Button size="sm" className="h-10" onClick={handleCheckin} disabled={checkingIn} data-testid="participant-checkin-btn">
          {checkingIn ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Check className="w-4 h-4 mr-1.5" />}
          Confirmer ma présence
        </Button>
      )}
    </div>
  );
}

export default function AppointmentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

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

  // Attendance & Evidence
  const [attendance, setAttendance] = useState(null);
  const [evaluating, setEvaluating] = useState(false);
  const [reclassifying, setReclassifying] = useState(null);
  const [reclassifyDropdown, setReclassifyDropdown] = useState(null);
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

      // Organizer-only loads
      if (viewerIsOrganizer) {
        calendarAPI.getSyncStatus(id).then(res => setSyncStatus(res.data)).catch(() => {});
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

  const handleEvaluateAttendance = async () => {
    setEvaluating(true);
    try {
      const res = await attendanceAPI.evaluate(id);
      if (res.data.skipped) toast.info(res.data.reason);
      else toast.success(`Évaluation : ${res.data.records_created} participant(s) évalué(s)`);
      const [attRes, evRes] = await Promise.all([attendanceAPI.get(id), checkinAPI.getEvidence(id)]);
      setAttendance(attRes.data); setEvidenceData(evRes.data);
    } catch (error) { toast.error(error.response?.data?.detail || "Erreur lors de l'évaluation"); }
    finally { setEvaluating(false); }
  };

  const handleReevaluateAttendance = async () => {
    setEvaluating(true);
    try {
      const res = await attendanceAPI.reevaluate(id);
      if (res.data.error) toast.error(res.data.error);
      else toast.success('Re-évaluation terminée');
      const [attRes, evRes] = await Promise.all([attendanceAPI.get(id), checkinAPI.getEvidence(id)]);
      setAttendance(attRes.data); setEvidenceData(evRes.data);
    } catch (error) { toast.error(error.response?.data?.detail || "Erreur lors de la re-évaluation"); }
    finally { setEvaluating(false); }
  };

  const handleReclassify = async (recordId, newOutcome) => {
    setReclassifying(recordId);
    try {
      await attendanceAPI.reclassify(recordId, { new_outcome: newOutcome });
      toast.success('Statut mis à jour');
      setReclassifyDropdown(null);
      const attRes = await attendanceAPI.get(id);
      setAttendance(attRes.data);
    } catch (error) { toast.error(error.response?.data?.detail || 'Erreur lors de la reclassification'); }
    finally { setReclassifying(null); }
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
    try { await modificationAPI.create({ appointment_id: id, changes }); toast.success('Proposition envoyée'); setShowProposalForm(false); loadData(); }
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
        <Button onClick={() => navigate('/dashboard')}>Retour au tableau de bord</Button>
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
      <AppBreadcrumb items={[{ label: 'Tableau de bord', href: '/dashboard' }, { label: appointment.title }]} />

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

        {/* Trust signal for participants */}
        {!isOrganizer && guaranteedCount > 0 && (
          <div className="mb-4 flex items-center gap-2 px-4 py-2.5 bg-emerald-50 border border-emerald-200 rounded-lg text-xs font-medium text-emerald-700" data-testid="trust-signal-banner">
            <ShieldCheck className="w-4 h-4 flex-shrink-0" />
            {guaranteedCount} participant{guaranteedCount > 1 ? 's' : ''} {guaranteedCount > 1 ? 'ont' : 'a'} déjà confirmé {guaranteedCount > 1 ? 'leur' : 'son'} engagement
          </div>
        )}

        {/* #2 — Essentials (date, lieu, lien, confiance) */}
        <AppointmentEssentials
          appointment={appointment} isCancelled={isCancelled} organizerParticipant={organizerParticipant}
          guaranteedCount={guaranteedCount} canEdit={isOrganizer && canEdit} onEdit={isOrganizer ? handleOpenProposalForm : undefined}
        />

        {/* #3 — Actions organisateur (calendrier + annuler) */}
        {isOrganizer && (
          <SecondaryActions
            appointment={appointment} isCancelled={isCancelled}
            syncStatus={syncStatus} syncingProvider={syncingProvider}
            onSyncCalendar={handleSyncCalendar} onDownloadICS={handleDownloadICS}
            onShowCancelModal={() => setShowCancelModal(true)}
          />
        )}

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

        {/* #6 — Check-in / Confirmation */}
        {isOrganizer && (
          <OrganizerCheckinBlock
            appointment={appointment} organizerParticipant={organizerParticipant}
            organizerCheckinDone={organizerCheckinDone} organizerCheckinData={organizerCheckinData}
            checkingIn={checkingIn} handleOrganizerCheckin={handleOrganizerCheckin}
            isCancelled={isCancelled} isPendingGuarantee={isPendingGuarantee}
          />
        )}

        {/* Participant check-in section */}
        {!isOrganizer && ['accepted', 'accepted_guaranteed'].includes(viewerParticipantStatus) && !isCancelled && (
          <ParticipantCheckinBlock appointmentId={id} viewerParticipantId={appointment.viewer_participant_id} viewerInvitationToken={viewerInvitationToken} />
        )}

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
                  attendance={attendance} evaluating={evaluating}
                  onEvaluate={handleEvaluateAttendance} onReevaluate={handleReevaluateAttendance}
                  onReclassify={handleReclassify} reclassifying={reclassifying}
                  reclassifyDropdown={reclassifyDropdown} setReclassifyDropdown={setReclassifyDropdown}
                  participants={participants}
                  getParticipantEvidence={(pid) => {
                    const pe = evidenceData?.participants?.find(p => p.participant_id === pid);
                    return pe?.evidence || [];
                  }}
                />
              )}
            </div>
          </details>
        )}

        {/* #7b — Result Card (viral share) — visible for both roles */}
        {isEnded && attendance && (
          <ResultCardSection
            attendance={attendance}
            appointment={appointment}
            userId={user?.user_id}
          />
        )}

        {/* #8 — Modal de modification (organisateur only) */}
        {isOrganizer && (
          <EditProposalModal
            open={showProposalForm} onClose={() => setShowProposalForm(false)}
            proposalForm={proposalForm} setProposalForm={setProposalForm}
            submittingProposal={submittingProposal} onSubmitProposal={handleSubmitProposal}
          />
        )}

        {/* #9 — Proposition active + Historique (visible for both) */}
        {(activeProposal || proposalHistory.length > 0) && (
          <details className="mb-4 bg-white border border-slate-200 rounded-xl overflow-hidden group" data-testid="modifications-details">
            <summary className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-slate-50 transition-colors select-none min-h-[44px]">
              <span className="text-sm font-semibold text-slate-900">Modifications</span>
              <div className="flex items-center gap-2">
                {activeProposal && <span className="text-xs px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full font-medium">En cours</span>}
                <ChevronDown className="w-4 h-4 text-slate-400 transition-transform group-open:rotate-180" />
              </div>
            </summary>
            <div className="border-t border-slate-100">
              <ModificationProposals
                activeProposal={activeProposal}
                respondingProposal={respondingProposal} onRespondProposal={handleRespondProposal} onCancelProposal={isOrganizer ? handleCancelProposal : undefined}
                proposalHistory={proposalHistory} showHistory={showHistory} setShowHistory={setShowHistory}
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
