import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { appointmentAPI, participantAPI, calendarAPI, invitationAPI, attendanceAPI, checkinAPI, modificationAPI, videoEvidenceAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { ArrowLeft, Calendar, MapPin, Video, Clock, Users, Ban, Check, X, AlertTriangle, Download, Heart, ShieldCheck, CreditCard, RefreshCw, Loader2, Zap, ClipboardCheck, Eye, UserX, UserCheck, HelpCircle, ChevronDown, ScanLine, QrCode, MapPinCheck, ExternalLink, Timer, Navigation, Pencil, Save, Send, FileEdit, Upload, Monitor, Shield, FileJson, Link2, UserCog, FileUp, PlayCircle, Settings2, DollarSign, CheckCircle, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import { formatDateTimeFr, formatTimeFr, formatEvidenceDateFr, parseUTC, utcToLocalInput, localInputToUTC } from '../../utils/dateFormat';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';

export default function AppointmentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [appointment, setAppointment] = useState(null);
  const [participants, setParticipants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [resendingToken, setResendingToken] = useState(null);
  const [syncStatus, setSyncStatus] = useState({ google: { synced: false, has_connection: false }, outlook: { synced: false, has_connection: false } });
  const [syncingProvider, setSyncingProvider] = useState(null);
  const [attendance, setAttendance] = useState(null);
  const [evaluating, setEvaluating] = useState(false);
  const [reclassifying, setReclassifying] = useState(null);
  const [reclassifyDropdown, setReclassifyDropdown] = useState(null);
  const [evidenceData, setEvidenceData] = useState(null);
  const [activeProposal, setActiveProposal] = useState(null);
  
  // Organizer check-in state
  const [organizerParticipant, setOrganizerParticipant] = useState(null);
  const [organizerCheckinDone, setOrganizerCheckinDone] = useState(false);
  const [checkingIn, setCheckingIn] = useState(false);
  const [proposalHistory, setProposalHistory] = useState([]);
  const [showProposalForm, setShowProposalForm] = useState(false);
  const [proposalForm, setProposalForm] = useState({
    start_datetime: '', duration_minutes: '', location: '',
    meeting_provider: null, appointment_type: ''
  });
  const [submittingProposal, setSubmittingProposal] = useState(false);
  const [respondingProposal, setRespondingProposal] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [videoEvidence, setVideoEvidence] = useState(null);
  const [showVideoIngest, setShowVideoIngest] = useState(false);
  const [videoIngestForm, setVideoIngestForm] = useState({
    provider: 'zoom', external_meeting_id: '', meeting_join_url: '', raw_json: ''
  });
  const [ingestingVideo, setIngestingVideo] = useState(false);
  const [videoIngestionLogs, setVideoIngestionLogs] = useState([]);
  const [creatingMeeting, setCreatingMeeting] = useState(false);
  const [fetchingAttendance, setFetchingAttendance] = useState(false);
  const [ingestMode, setIngestMode] = useState('file'); // 'file' or 'json'
  const [selectedFile, setSelectedFile] = useState(null);
  const [csvPreview, setCsvPreview] = useState(null);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [resumingGuarantee, setResumingGuarantee] = useState(false);
  const [checkingActivation, setCheckingActivation] = useState(false);

  useEffect(() => {
    loadData();
  }, [id]);

  const loadData = async () => {
    try {
      const [appointmentRes, participantsRes] = await Promise.all([
        appointmentAPI.get(id),
        participantAPI.list(id)
      ]);
      setAppointment(appointmentRes.data);
      const allParticipants = participantsRes.data.participants || [];
      setParticipants(allParticipants);
      
      // Detect organizer's participant record
      const orgP = allParticipants.find(p => p.is_organizer === true);
      setOrganizerParticipant(orgP || null);
      if (orgP && orgP.invitation_token) {
        checkinAPI.getStatus(id, orgP.invitation_token)
          .then(res => {
            if (res.data?.evidence_count > 0) setOrganizerCheckinDone(true);
          })
          .catch(() => {});
      }

      // Check calendar sync status for all providers (non-blocking)
      calendarAPI.getSyncStatus(id)
        .then(res => setSyncStatus(res.data))
        .catch(() => {});

      // Load attendance data (non-blocking)
      attendanceAPI.get(id)
        .then(res => setAttendance(res.data))
        .catch(() => {});

      // Load evidence data (non-blocking)
      checkinAPI.getEvidence(id)
        .then(res => setEvidenceData(res.data))
        .catch(() => {});

      // Load modification proposals (non-blocking)
      modificationAPI.getActive(id)
        .then(res => setActiveProposal(res.data?.proposal || null))
        .catch(() => {});
      modificationAPI.getForAppointment(id)
        .then(res => setProposalHistory(res.data?.proposals || []))
        .catch(() => {});

      // Load video evidence (non-blocking)
      videoEvidenceAPI.get(id)
        .then(res => setVideoEvidence(res.data))
        .catch(() => {});
      videoEvidenceAPI.getLogs(id)
        .then(res => setVideoIngestionLogs(res.data?.logs || []))
        .catch(() => {});
    } catch (error) {
      toast.error('Erreur lors du chargement');
    } finally {
      setLoading(false);
    }
  };


  const handleOrganizerCheckin = async () => {
    if (!organizerParticipant?.invitation_token) return;
    setCheckingIn(true);
    try {
      await checkinAPI.manual({
        appointment_id: id,
        invitation_token: organizerParticipant.invitation_token
      });
      setOrganizerCheckinDone(true);
      toast.success('Check-in organisateur enregistré');
      loadData(); // Refresh evidence
    } catch (error) {
      const msg = error.response?.data?.detail || 'Erreur lors du check-in';
      toast.error(msg);
    } finally {
      setCheckingIn(false);
    }
  };

  const handleSyncCalendar = async (provider) => {
    setSyncingProvider(provider);
    const label = provider === 'google' ? 'Google Calendar' : 'Outlook Calendar';
    try {
      const response = await calendarAPI.syncAppointment(id, provider);
      setSyncStatus(prev => ({
        ...prev,
        [provider]: { synced: true, out_of_sync: false, has_connection: true, html_link: response.data.html_link, external_event_id: response.data.external_event_id, sync_source: 'manual' }
      }));
      toast.success(`Rendez-vous synchronisé avec ${label}`);
    } catch (error) {
      const detail = error.response?.data?.detail;
      if (detail?.includes('non connecté')) {
        toast.error(`${label} non connecté. Allez dans Paramètres > Intégrations.`);
      } else if (error.response?.status === 401) {
        toast.error(`Session ${label} expirée. Reconnectez dans Paramètres > Intégrations.`);
      } else {
        toast.error(detail || `Erreur lors de la synchronisation avec ${label}`);
      }
    } finally {
      setSyncingProvider(null);
    }
  };

  const handleCancelAppointment = async () => {
    try {
      setCancelling(true);
      const response = await appointmentAPI.cancel(id);
      toast.success(`Rendez-vous annulé. ${response.data.participants_notified} participant(s) notifié(s).`);
      setShowCancelModal(false);
      // Reload data to show updated status
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Erreur lors de l\'annulation');
    } finally {
      setCancelling(false);
    }
  };

  const handleResendInvitation = async (token) => {
    setResendingToken(token);
    try {
      await invitationAPI.resend(token);
      toast.success('Invitation renvoyée avec succès');
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erreur lors du renvoi de l'invitation");
    } finally {
      setResendingToken(null);
    }
  };

  const handleEvaluateAttendance = async () => {
    setEvaluating(true);
    try {
      const res = await attendanceAPI.evaluate(id);
      if (res.data.skipped) {
        toast.info(res.data.reason);
      } else {
        toast.success(`Évaluation terminée : ${res.data.records_created} participant(s) évalué(s)`);
      }
      const [attRes, evRes] = await Promise.all([attendanceAPI.get(id), checkinAPI.getEvidence(id)]);
      setAttendance(attRes.data);
      setEvidenceData(evRes.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erreur lors de l'évaluation");
    } finally {
      setEvaluating(false);
    }
  };

  const handleReevaluateAttendance = async () => {
    setEvaluating(true);
    try {
      const res = await attendanceAPI.reevaluate(id);
      if (res.data.error) {
        toast.error(res.data.error);
      } else {
        toast.success(`Re-évaluation terminée avec preuves à jour`);
      }
      const [attRes, evRes] = await Promise.all([attendanceAPI.get(id), checkinAPI.getEvidence(id)]);
      setAttendance(attRes.data);
      setEvidenceData(evRes.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erreur lors de la re-évaluation");
    } finally {
      setEvaluating(false);
    }
  };

  const handleReclassify = async (recordId, newOutcome) => {
    setReclassifying(recordId);
    try {
      await attendanceAPI.reclassify(recordId, { new_outcome: newOutcome });
      toast.success('Statut mis à jour');
      setReclassifyDropdown(null);
      const attRes = await attendanceAPI.get(id);
      setAttendance(attRes.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Erreur lors de la reclassification');
    } finally {
      setReclassifying(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900"></div>
      </div>
    );
  }

  if (!appointment) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-600 mb-4">Rendez-vous introuvable</p>
          <Button onClick={() => navigate('/dashboard')}>Retour au tableau de bord</Button>
        </div>
      </div>
    );
  }

  const acceptedCount = participants.filter(p => ['accepted', 'accepted_pending_guarantee', 'accepted_guaranteed'].includes(p.status)).length;
  const pendingCount = participants.filter(p => p.status === 'invited').length;
  const isCancelled = appointment.status === 'cancelled';
  const isPendingGuarantee = appointment.status === 'pending_organizer_guarantee';

  // Resume organizer guarantee (get a new Stripe session or auto-activate)
  const handleResumeGuarantee = async () => {
    setResumingGuarantee(true);
    try {
      const res = await appointmentAPI.retryGuarantee(id);
      
      if (res.data.status === 'active' && res.data.activated) {
        // Auto-guaranteed with saved card
        toast.success('Garantie validée ! Invitations envoyées.');
        await loadData();
      } else if (res.data.checkout_url) {
        // Redirect to Stripe
        toast.info('Redirection vers Stripe pour valider votre garantie...');
        window.location.href = res.data.checkout_url;
      } else {
        toast.info(res.data.message || 'Statut mis à jour');
        await loadData();
      }
    } catch (error) {
      const msg = error.response?.data?.detail || 'Erreur lors de la reprise de la garantie';
      toast.error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setResumingGuarantee(false);
    }
  };

  // Check activation status (polling after Stripe return)
  const handleCheckActivation = async () => {
    setCheckingActivation(true);
    try {
      const res = await appointmentAPI.checkActivation(id);
      if (res.data.status === 'active' || res.data.activated) {
        toast.success('Rendez-vous activé ! Invitations envoyées.');
        await loadData();
      } else {
        toast.info('Garantie en cours de validation...');
      }
    } catch {
      toast.error('Erreur lors de la vérification');
    } finally {
      setCheckingActivation(false);
    }
  };

  const handleDownloadICS = () => {
    // Open ICS download in new tab/trigger download
    const icsUrl = calendarAPI.exportICS(id);
    window.open(icsUrl, '_blank');
    toast.success('Téléchargement du fichier calendrier...');
  };

  // Attendance outcome badge
  const getOutcomeBadge = (outcome, decisionBasis) => {
    const badges = {
      on_time: { bg: 'bg-emerald-100', text: 'text-emerald-800', icon: <UserCheck className="w-3 h-3" />, label: 'Présent' },
      late: { bg: 'bg-amber-100', text: 'text-amber-800', icon: <Clock className="w-3 h-3" />, label: 'En retard' },
      no_show: { bg: 'bg-red-100', text: 'text-red-800', icon: <UserX className="w-3 h-3" />, label: decisionBasis === 'cancelled_late' ? 'Annulation tardive' : 'Absent' },
      manual_review: { bg: 'bg-yellow-100', text: 'text-yellow-800', icon: <Eye className="w-3 h-3" />, label: 'À vérifier' },
      waived: { bg: 'bg-slate-100', text: 'text-slate-600', icon: <HelpCircle className="w-3 h-3" />, label: 'Dispensé' },
    };
    const b = badges[outcome] || badges.manual_review;
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-1 ${b.bg} ${b.text} rounded-full text-xs font-medium`}>
        {b.icon} {b.label}
      </span>
    );
  };

  const getDecisionLabel = (basis) => {
    const labels = {
      declined: 'A décliné l\'invitation',
      guarantee_released: 'Garantie libérée',
      no_response: 'N\'a jamais répondu',
      cancelled_in_time: 'Annulé dans les délais',
      cancelled_late: 'Annulé hors délai',
      cancellation_date_parse_error: 'Date d\'annulation non lisible',
      accepted_no_guarantee: 'Accepté sans garantie',
      pending_guarantee: 'Garantie en attente',
      no_proof_of_attendance: 'Pas de preuve de présence',
      strong_evidence_on_time: 'Preuve forte — à l\'heure',
      strong_evidence_late: 'Preuve forte — en retard',
      medium_evidence_on_time: 'Preuve moyenne — à l\'heure',
      medium_evidence_late: 'Preuve moyenne — en retard',
      weak_evidence: 'Preuve faible',
      video_strong_on_time: 'Visio — preuve forte, connecté à l\'heure',
      video_strong_late: 'Visio — preuve forte, connecté en retard',
      video_medium_joined_on_time: 'Visio — preuve moyenne, connecté à l\'heure',
      video_medium_joined_late: 'Visio — preuve moyenne, connecté en retard',
      video_ambiguous: 'Visio — signal ambigu, revue manuelle',
      meet_assisted_only: 'Google Meet — preuve assistée uniquement',
    };
    return labels[basis] || basis;
  };

  // Check if appointment has ended (for showing evaluate button)
  const isAppointmentEnded = () => {
    if (!appointment?.start_datetime) return false;
    const start = parseUTC(appointment.start_datetime);
    if (!start) return false;
    const end = new Date(start.getTime() + (appointment.duration_minutes || 60) * 60000);
    return new Date() > end;
  };

  // Check if appointment can be edited (not cancelled, not ended)
  const canEditDatetime = () => {
    if (!appointment) return false;
    if (appointment.status === 'cancelled') return false;
    if (activeProposal) return false;
    return !isAppointmentEnded();
  };

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
    const current = appointment;
    const form = proposalForm;
    const utcDt = localInputToUTC(form.start_datetime);
    if (utcDt && utcDt !== current.start_datetime) changes.start_datetime = utcDt;
    if (form.duration_minutes && Number(form.duration_minutes) !== current.duration_minutes) changes.duration_minutes = Number(form.duration_minutes);
    if (form.location !== (current.location || '')) changes.location = form.location;
    if (form.meeting_provider !== (current.meeting_provider || '')) changes.meeting_provider = form.meeting_provider;
    if (form.appointment_type !== (current.appointment_type || '')) changes.appointment_type = form.appointment_type;

    if (Object.keys(changes).length === 0) {
      toast.error('Aucune modification détectée');
      return;
    }
    if (changes.start_datetime && new Date(changes.start_datetime) <= new Date()) {
      toast.error("La nouvelle date doit être dans le futur");
      return;
    }

    setSubmittingProposal(true);
    try {
      await modificationAPI.create({ appointment_id: id, changes });
      toast.success('Proposition de modification envoyée');
      setShowProposalForm(false);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la création de la proposition');
    } finally {
      setSubmittingProposal(false);
    }
  };

  const handleRespondProposal = async (proposalId, action) => {
    setRespondingProposal(true);
    try {
      await modificationAPI.respond(proposalId, { action });
      toast.success(action === 'accept' ? 'Modification acceptée' : 'Modification refusée');
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Erreur');
    } finally {
      setRespondingProposal(false);
    }
  };

  const handleCancelProposal = async (proposalId) => {
    try {
      await modificationAPI.cancel(proposalId);
      toast.success('Proposition annulée');
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Erreur');
    }
  };

  const reclassifyOptions = [
    { value: 'on_time', label: 'Présent', color: 'text-emerald-700' },
    { value: 'late', label: 'En retard', color: 'text-amber-700' },
    { value: 'no_show', label: 'Absent', color: 'text-red-700' },
    { value: 'waived', label: 'Dispensé', color: 'text-slate-600' },
  ];

  // Evidence helper: get participant evidence from evidenceData
  const getParticipantEvidence = (participantId) => {
    if (!evidenceData?.participants) return null;
    return evidenceData.participants.find(p => p.participant_id === participantId);
  };

  const getEvidenceIcons = (pEvidence) => {
    if (!pEvidence?.evidence?.length) return null;
    const sources = new Set(pEvidence.evidence.map(e => e.source));
    return (
      <div className="flex items-center gap-1.5">
        {sources.has('manual_checkin') && <MapPinCheck className="w-3.5 h-3.5 text-emerald-500" title="Check-in manuel" />}
        {sources.has('qr') && <QrCode className="w-3.5 h-3.5 text-blue-500" title="QR vérifié" />}
        {sources.has('gps') && <MapPin className="w-3.5 h-3.5 text-purple-500" title="GPS" />}
        {sources.has('video_conference') && <Monitor className="w-3.5 h-3.5 text-indigo-500" title="Visioconférence" />}
      </div>
    );
  };

  const getStrengthBadge = (strength) => {
    const badges = {
      strong: { bg: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-700', label: 'Preuve forte' },
      medium: { bg: 'bg-amber-50 border-amber-200', text: 'text-amber-700', label: 'Preuve moyenne' },
      weak: { bg: 'bg-red-50 border-red-200', text: 'text-red-700', label: 'Preuve faible' },
      none: { bg: 'bg-slate-50 border-slate-200', text: 'text-slate-500', label: 'Aucune preuve' },
    };
    const b = badges[strength] || badges.none;
    return <span className={`text-xs px-2.5 py-1 rounded-full border ${b.bg} ${b.text} font-medium`}>{b.label}</span>;
  };

  const getTimingBadge = (timing) => {
    if (!timing) return null;
    if (timing === 'on_time') return <span className="text-xs px-2.5 py-1 rounded-full border bg-emerald-50 border-emerald-200 text-emerald-700 font-medium">À l'heure</span>;
    return <span className="text-xs px-2.5 py-1 rounded-full border bg-amber-50 border-amber-200 text-amber-700 font-medium">En retard</span>;
  };

  const formatSourceLabel = (source) => {
    const labels = { manual_checkin: 'Check-in manuel', qr: 'QR code', gps: 'GPS', system: 'Système', video_conference: 'Visioconférence' };
    return labels[source] || source;
  };

  const formatEvidenceDate = (ts) => formatEvidenceDateFr(ts);

  const getSourceIcon = (source) => {
    if (source === 'manual_checkin') return <MapPinCheck className="w-4 h-4 text-emerald-600" />;
    if (source === 'qr') return <QrCode className="w-4 h-4 text-blue-600" />;
    if (source === 'gps') return <MapPin className="w-4 h-4 text-purple-600" />;
    if (source === 'video_conference') return <Monitor className="w-4 h-4 text-indigo-600" />;
    return <ScanLine className="w-4 h-4 text-slate-500" />;
  };

  const getSourceColor = (source) => {
    if (source === 'manual_checkin') return 'border-l-emerald-500';
    if (source === 'qr') return 'border-l-blue-500';
    if (source === 'gps') return 'border-l-purple-500';
    if (source === 'video_conference') return 'border-l-indigo-500';
    return 'border-l-slate-300';
  };

  const getProviderIcon = (provider) => {
    const icons = {
      zoom: { label: 'Zoom', color: 'text-blue-600', bg: 'bg-blue-50' },
      teams: { label: 'Teams', color: 'text-purple-600', bg: 'bg-purple-50' },
      meet: { label: 'Google Meet', color: 'text-emerald-600', bg: 'bg-emerald-50' },
    };
    return icons[(provider || '').toLowerCase()] || { label: provider || 'Visio', color: 'text-slate-600', bg: 'bg-slate-50' };
  };

  const getVideoOutcomeBadge = (outcome) => {
    const badges = {
      joined_on_time: { bg: 'bg-emerald-100', text: 'text-emerald-800', label: 'Connecté à l\'heure' },
      joined_late: { bg: 'bg-amber-100', text: 'text-amber-800', label: 'Connecté en retard' },
      no_join_detected: { bg: 'bg-red-100', text: 'text-red-800', label: 'Aucune connexion' },
      manual_review: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'Revue manuelle' },
      partial_attendance: { bg: 'bg-orange-100', text: 'text-orange-800', label: 'Présence partielle' },
    };
    const b = badges[outcome] || badges.manual_review;
    return <span className={`inline-flex items-center gap-1 px-2 py-0.5 ${b.bg} ${b.text} rounded-full text-xs font-medium`}>{b.label}</span>;
  };

  const getIdentityConfidenceBadge = (confidence) => {
    const badges = {
      high: { bg: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-700', label: 'Identité forte' },
      medium: { bg: 'bg-amber-50 border-amber-200', text: 'text-amber-700', label: 'Identité moyenne' },
      low: { bg: 'bg-red-50 border-red-200', text: 'text-red-700', label: 'Identité faible' },
    };
    const b = badges[confidence] || badges.low;
    return <span className={`text-xs px-2 py-0.5 rounded-full border ${b.bg} ${b.text} font-medium`}>{b.label}</span>;
  };

  const handleVideoIngest = async () => {
    let parsed;
    try {
      parsed = JSON.parse(videoIngestForm.raw_json);
    } catch {
      toast.error('JSON invalide. Vérifiez le format du rapport de présence.');
      return;
    }
    setIngestingVideo(true);
    try {
      const res = await videoEvidenceAPI.ingest(id, {
        provider: videoIngestForm.provider,
        external_meeting_id: videoIngestForm.external_meeting_id || undefined,
        meeting_join_url: videoIngestForm.meeting_join_url || undefined,
        raw_payload: parsed,
      });
      const data = res.data;
      toast.success(`Ingestion terminée : ${data.records_created} preuve(s) créée(s), ${data.matched?.length || 0} matchée(s), ${data.unmatched?.length || 0} non-matchée(s)`);
      setShowVideoIngest(false);
      setVideoIngestForm({ provider: 'zoom', external_meeting_id: '', meeting_join_url: '', raw_json: '' });
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Erreur lors de l\'ingestion');
    } finally {
      setIngestingVideo(false);
    }
  };

  const handleCreateMeeting = async () => {
    setCreatingMeeting(true);
    try {
      const res = await videoEvidenceAPI.createMeeting(id);
      const data = res.data;
      if (data.already_exists) {
        toast.info('La réunion existe déjà.');
      } else {
        toast.success(`Réunion ${data.provider} créée ! Lien : ${data.join_url ? 'disponible' : 'en attente'}`);
      }
      loadData();
    } catch (err) {
      const detail = err.response?.data?.detail || 'Erreur lors de la création de la réunion';
      if (err.response?.status === 424) {
        toast.error(`Configuration requise : ${detail}`);
      } else {
        toast.error(detail);
      }
    } finally {
      setCreatingMeeting(false);
    }
  };

  const handleFetchAttendance = async () => {
    setFetchingAttendance(true);
    try {
      const res = await videoEvidenceAPI.fetchAttendance(id);
      const data = res.data;
      if (data.ingestion_result) {
        const ir = data.ingestion_result;
        toast.success(`Présences récupérées via API : ${ir.records_created || 0} preuve(s), ${ir.matched?.length || 0} matchée(s)`);
      } else {
        toast.success('Données de présence récupérées.');
      }
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la récupération des présences');
    } finally {
      setFetchingAttendance(false);
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedFile(file);
    setCsvPreview(null);

    // Preview CSV/JSON content
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target.result;
      try {
        if (file.name.endsWith('.csv')) {
          const lines = text.split('\n').filter(l => l.trim());
          const headers = lines[0]?.split(',').map(h => h.trim().replace(/"/g, ''));
          const rows = lines.slice(1, 6).map(line => {
            const vals = line.split(',').map(v => v.trim().replace(/"/g, ''));
            const obj = {};
            headers.forEach((h, i) => { obj[h] = vals[i] || ''; });
            return obj;
          });
          setCsvPreview({ type: 'csv', headers, rows, total: lines.length - 1 });
        } else {
          const json = JSON.parse(text);
          const participants = json.participants || json.attendanceRecords || [];
          setCsvPreview({ type: 'json', total: participants.length, participants: participants.slice(0, 5) });
        }
      } catch {
        setCsvPreview({ type: 'error', message: 'Impossible de lire le fichier' });
      }
    };
    reader.readAsText(file);
  };

  const handleFileUpload = async () => {
    if (!selectedFile) return;
    setUploadingFile(true);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('provider', videoIngestForm.provider);
      const res = await videoEvidenceAPI.ingestFile(id, formData);
      const data = res.data;
      toast.success(`Import terminé : ${data.records_created} preuve(s), ${data.matched?.length || 0} matchée(s), ${data.unmatched?.length || 0} non-matchée(s)`);
      setSelectedFile(null);
      setCsvPreview(null);
      setShowVideoIngest(false);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Erreur lors de l\'import du fichier');
    } finally {
      setUploadingFile(false);
    }
  };

  // Status badge helper
  const getParticipantStatusBadge = (status, participant = null) => {
    // Check if this participant's guarantee needs revalidation
    if (participant?.guarantee_requires_revalidation && status === 'accepted_guaranteed') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 bg-amber-100 text-amber-800 rounded-full text-xs font-medium" data-testid={`badge-revalidation-${participant.participant_id}`}>
          <AlertTriangle className="w-3 h-3" /> À reconfirmer
        </span>
      );
    }

    switch (status) {
      case 'accepted_guaranteed':
        return <span className="inline-flex items-center gap-1 px-2 py-1 bg-emerald-100 text-emerald-800 rounded-full text-xs font-medium"><ShieldCheck className="w-3 h-3" /> Garanti</span>;
      case 'accepted_pending_guarantee':
        return <span className="inline-flex items-center gap-1 px-2 py-1 bg-amber-100 text-amber-800 rounded-full text-xs font-medium"><CreditCard className="w-3 h-3" /> Garantie en cours</span>;
      case 'accepted':
        return <span className="inline-flex items-center gap-1 px-2 py-1 bg-emerald-100 text-emerald-800 rounded-full text-xs font-medium"><Check className="w-3 h-3" /> Accepté</span>;
      case 'declined':
        return <span className="inline-flex items-center gap-1 px-2 py-1 bg-red-100 text-red-800 rounded-full text-xs font-medium"><X className="w-3 h-3" /> Refusé</span>;
      case 'cancelled_by_participant':
        return <span className="inline-flex items-center gap-1 px-2 py-1 bg-orange-100 text-orange-800 rounded-full text-xs font-medium"><Ban className="w-3 h-3" /> Annulé</span>;
      default:
        return <span className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-medium"><Clock className="w-3 h-3" /> Invité</span>;
    }
  };

  return (
    <div className="min-h-screen bg-background py-8 px-4">
      <div className="max-w-6xl mx-auto">
        <Link to="/dashboard">
          <Button variant="ghost" className="mb-6">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Retour au tableau de bord
          </Button>
        </Link>

        {/* Cancelled Banner */}
        {isCancelled && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 flex items-center gap-3">
            <Ban className="w-6 h-6 text-red-600" />
            <div>
              <p className="font-semibold text-red-800">Ce rendez-vous a été annulé</p>
              <p className="text-sm text-red-600">
                Les participants ont été notifiés. Ce rendez-vous n'aura pas lieu.
              </p>
            </div>
          </div>
        )}

        <div className="mb-6 flex items-start justify-between">
          <div>
            <h1 className={`text-3xl font-bold mb-2 ${isCancelled ? 'text-slate-400 line-through' : 'text-slate-900'}`} data-testid="appointment-title">
              {appointment.title}
            </h1>
            <span className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${
              appointment.status === 'active' ? 'bg-emerald-100 text-emerald-800' :
              appointment.status === 'cancelled' ? 'bg-red-100 text-red-800' :
              appointment.status === 'pending_organizer_guarantee' ? 'bg-amber-100 text-amber-800' :
              appointment.status === 'draft' ? 'bg-slate-100 text-slate-800' :
              'bg-slate-100 text-slate-600'
            }`} data-testid="appointment-status-badge">
              {appointment.status === 'active' ? 'Actif' : 
               appointment.status === 'cancelled' ? 'Annulé' :
               appointment.status === 'pending_organizer_guarantee' ? 'En attente de votre garantie' :
               appointment.status === 'draft' ? 'Brouillon' : appointment.status}
            </span>
          </div>
          <div className="flex gap-2 flex-wrap">
            {/* ICS Download button */}
            <Button 
              variant="outline"
              onClick={handleDownloadICS}
              data-testid="download-ics-btn"
            >
              <Download className="w-4 h-4 mr-2" />
              ICS
            </Button>

            {/* Google Calendar sync button */}
            {syncStatus?.google?.synced ? (
              <Button variant="outline" className="text-emerald-700 border-emerald-300" disabled data-testid="google-synced-btn">
                {syncStatus.google.sync_source === 'auto' ? <Zap className="w-4 h-4 mr-2" /> : <Check className="w-4 h-4 mr-2" />}
                Google Calendar
              </Button>
            ) : syncStatus?.google?.out_of_sync ? (
              <Button
                variant="outline"
                className="text-amber-700 border-amber-300"
                onClick={() => handleSyncCalendar('google')}
                disabled={syncingProvider !== null}
                data-testid="google-out-of-sync-btn"
                title={syncStatus.google.sync_error_reason || 'Non synchronisé'}
              >
                {syncingProvider === 'google' ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <AlertTriangle className="w-4 h-4 mr-2" />}
                Google Calendar
              </Button>
            ) : syncStatus?.google?.has_connection && !isCancelled ? (
              <Button
                variant="outline"
                onClick={() => handleSyncCalendar('google')}
                disabled={syncingProvider !== null}
                data-testid="sync-google-btn"
              >
                {syncingProvider === 'google' ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Calendar className="w-4 h-4 mr-2" />}
                Google Calendar
              </Button>
            ) : null}

            {/* Outlook Calendar sync button */}
            {syncStatus?.outlook?.synced ? (
              <Button variant="outline" className="text-emerald-700 border-emerald-300" disabled data-testid="outlook-synced-btn">
                {syncStatus.outlook.sync_source === 'auto' ? <Zap className="w-4 h-4 mr-2" /> : <Check className="w-4 h-4 mr-2" />}
                Outlook Calendar
              </Button>
            ) : syncStatus?.outlook?.out_of_sync ? (
              <Button
                variant="outline"
                className="text-amber-700 border-amber-300"
                onClick={() => handleSyncCalendar('outlook')}
                disabled={syncingProvider !== null}
                data-testid="outlook-out-of-sync-btn"
                title={syncStatus.outlook.sync_error_reason || 'Non synchronisé'}
              >
                {syncingProvider === 'outlook' ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <AlertTriangle className="w-4 h-4 mr-2" />}
                Outlook Calendar
              </Button>
            ) : syncStatus?.outlook?.has_connection && !isCancelled ? (
              <Button
                variant="outline"
                onClick={() => handleSyncCalendar('outlook')}
                disabled={syncingProvider !== null}
                data-testid="sync-outlook-btn"
              >
                {syncingProvider === 'outlook' ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Calendar className="w-4 h-4 mr-2" />}
                Outlook Calendar
              </Button>
            ) : null}
            
            {!isCancelled && (
              <>
                <Link to={`/appointments/${id}/participants`}>
                  <Button variant="outline">
                    <Users className="w-4 h-4 mr-2" />
                    Gérer les participants
                  </Button>
                </Link>
                <Button 
                  variant="outline" 
                  className="text-red-600 border-red-300 hover:bg-red-50"
                  onClick={() => setShowCancelModal(true)}
                  data-testid="cancel-appointment-btn"
                >
                  <Ban className="w-4 h-4 mr-2" />
                  Annuler le rendez-vous
                </Button>
              </>
            )}
          </div>
        </div>

        {/* Banner for pending organizer guarantee */}
        {isPendingGuarantee && (
          <div className="mb-6 bg-amber-50 border border-amber-200 rounded-lg p-5 flex items-start gap-4" data-testid="pending-guarantee-banner">
            <AlertTriangle className="w-6 h-6 text-amber-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <h3 className="font-semibold text-amber-900">Rendez-vous en attente de votre garantie</h3>
              <p className="text-sm text-amber-800 mt-1">
                Les invitations ne seront envoyées aux participants qu'après validation de votre garantie organisateur.
                Complétez votre garantie ou configurez une carte par défaut dans vos paramètres.
              </p>
              <div className="flex gap-3 mt-3">
                <Button
                  size="sm"
                  onClick={handleResumeGuarantee}
                  disabled={resumingGuarantee}
                  className="bg-amber-600 hover:bg-amber-700"
                  data-testid="banner-resume-guarantee-btn"
                >
                  {resumingGuarantee ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <CreditCard className="w-4 h-4 mr-2" />}
                  Compléter ma garantie
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => navigate('/settings/payment')}
                  data-testid="banner-settings-btn"
                >
                  <Settings2 className="w-4 h-4 mr-2" />
                  Configurer une carte par défaut
                </Button>
              </div>
            </div>
          </div>
        )}

        <div className="grid md:grid-cols-3 gap-6 mb-6">
          <div className={`bg-white p-6 rounded-lg border ${isCancelled ? 'border-slate-200 opacity-60' : 'border-slate-200'}`}>
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Users className="w-5 h-5 text-blue-700" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">{participants.length}</p>
                <p className="text-sm text-slate-600">Participants</p>
              </div>
            </div>
            <div className="text-xs text-slate-500">
              {acceptedCount} accepté(s), {pendingCount} en attente
            </div>
          </div>

          <div className={`bg-white p-6 rounded-lg border ${isCancelled ? 'border-slate-200 opacity-60' : 'border-slate-200'}`}>
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-emerald-100 rounded-lg">
                <Clock className="w-5 h-5 text-emerald-700" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">{appointment.tolerated_delay_minutes}</p>
                <p className="text-sm text-slate-600">Minutes de retard</p>
              </div>
            </div>
            <div className="text-xs text-slate-500">Tolérance autorisée</div>
          </div>

          <div className={`bg-white p-6 rounded-lg border ${isCancelled ? 'border-slate-200 opacity-60' : 'border-slate-200'}`}>
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-amber-100 rounded-lg">
                <Calendar className="w-5 h-5 text-amber-700" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">{appointment.cancellation_deadline_hours}h</p>
                <p className="text-sm text-slate-600">Délai d'annulation</p>
              </div>
            </div>
            <div className="text-xs text-slate-500">Avant pénalité</div>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className={`bg-white rounded-lg border p-6 min-w-0 overflow-hidden ${isCancelled ? 'border-slate-200 opacity-60' : 'border-slate-200'}`}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900">Informations générales</h2>
              {canEditDatetime() && (
                <button
                  onClick={handleOpenProposalForm}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-slate-600 hover:text-blue-700 hover:bg-blue-50 border border-slate-200 hover:border-blue-200 rounded-lg transition-colors"
                  title="Modifier les informations générales (date, durée, lieu, type)"
                  data-testid="edit-general-info-btn"
                >
                  <Pencil className="w-3.5 h-3.5" />
                  Modifier
                </button>
              )}
            </div>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <Calendar className="w-5 h-5 text-slate-500 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-slate-700">Date et heure</p>
                  <p className="text-slate-900" data-testid="appointment-datetime-display">
                    {formatDateTimeFr(appointment.start_datetime)}
                  </p>
                  <p className="text-sm text-slate-500 mt-1">Durée : {appointment.duration_minutes} minutes</p>
                </div>
              </div>

              {appointment.appointment_type === 'physical' && appointment.location && (
                <div className="flex items-start gap-3">
                  <MapPin className="w-5 h-5 text-slate-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-slate-700">Lieu</p>
                    <p className="text-slate-900">{appointment.location}</p>
                  </div>
                </div>
              )}

              {appointment.appointment_type === 'video' && appointment.meeting_provider && (
                <div className="flex items-start gap-3 min-w-0">
                  <Video className="w-5 h-5 text-slate-500 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-700">Plateforme</p>
                    <div className="flex items-center gap-2">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-medium ${getProviderIcon(appointment.meeting_provider).bg} ${getProviderIcon(appointment.meeting_provider).color}`} data-testid="meeting-provider-badge">
                        <Monitor className="w-3.5 h-3.5" />
                        {getProviderIcon(appointment.meeting_provider).label}
                      </span>
                      {appointment.external_meeting_id && (
                        <span className="text-xs text-slate-400" data-testid="external-meeting-id">
                          ID: {appointment.external_meeting_id}
                        </span>
                      )}
                    </div>
                    {appointment.meeting_join_url ? (
                      <div className="flex flex-col gap-2 mt-1.5">
                        {/* Meeting links — Central mode (Zoom): single join link for everyone */}
                        {(() => {
                          const metadata = appointment.meeting_provider_metadata || {};
                          const isCentralMode = metadata.creation_mode === 'central';
                          
                          if (isCentralMode) {
                            return (
                              <a
                                href={appointment.meeting_join_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1.5 text-sm font-semibold text-blue-600 hover:text-blue-800 hover:underline"
                                data-testid="meeting-join-url"
                              >
                                <Link2 className="w-3.5 h-3.5" />
                                Rejoindre la réunion
                              </a>
                            );
                          }
                          
                          if (appointment.meeting_host_url) {
                            return (
                              <div className="flex flex-col gap-1.5">
                                <a
                                  href={appointment.meeting_host_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-600 hover:text-emerald-800 hover:underline"
                                  data-testid="meeting-host-url"
                                >
                                  <Link2 className="w-3.5 h-3.5" />
                                  Démarrer la réunion (organisateur)
                                </a>
                                <a
                                  href={appointment.meeting_join_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 hover:underline"
                                  data-testid="meeting-join-url"
                                >
                                  <ExternalLink className="w-3 h-3" />
                                  Lien participant
                                </a>
                              </div>
                            );
                          }
                          
                          return (
                            <a
                              href={appointment.meeting_join_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline"
                              data-testid="meeting-join-url"
                            >
                              <Link2 className="w-3.5 h-3.5" />
                              Rejoindre la réunion
                            </a>
                          );
                        })()}

                        {/* Unified organizer identity + proof availability block */}
                        {(() => {
                          const provider = (appointment.meeting_provider || '').toLowerCase();
                          const metadata = appointment.meeting_provider_metadata || {};
                          const creatorEmail = metadata.creator_email || metadata.host_email;
                          const creatorName = metadata.creator_name;

                          if (!creatorEmail && !appointment.meeting_host_url) return null;

                          const providerLabel = provider === 'zoom' ? 'Zoom' :
                            provider === 'teams' ? 'Microsoft Teams' :
                            provider === 'meet' ? 'Google' : appointment.meeting_provider;

                          // Detect personal Gmail vs Workspace
                          const isMeetPersonal = provider === 'meet' && creatorEmail &&
                            (creatorEmail.endsWith('@gmail.com') || creatorEmail.endsWith('@googlemail.com'));
                          const isMeetWorkspace = provider === 'meet' && creatorEmail && !isMeetPersonal;

                          return (
                            <div className="mt-3 space-y-3" data-testid="organizer-identity-block">
                              {/* Section 1: Account identity */}
                              <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
                                <p className="text-sm font-semibold text-slate-800 mb-1.5 flex items-center gap-2">
                                  <UserCog className="w-4 h-4 text-slate-500" />
                                  {metadata.creation_mode === 'central'
                                    ? 'Réunion gérée par NLYT'
                                    : 'Connexion en tant qu\'organisateur'
                                  }
                                </p>
                                {metadata.creation_mode === 'central' ? (
                                  <p className="text-sm text-slate-600" data-testid="zoom-central-mode-info">
                                    Cette réunion {providerLabel} est gérée automatiquement par NLYT. Aucun compte {providerLabel} n'est requis pour les participants.
                                  </p>
                                ) : (
                                  <>
                                    {creatorEmail && (
                                      <p className="text-sm text-slate-600">
                                        Réunion créée avec le compte {providerLabel} : <span className="font-semibold text-slate-900" data-testid="organizer-account-email">{creatorEmail}</span>
                                        {creatorName && <span className="text-slate-400"> ({creatorName})</span>}
                                      </p>
                                    )}
                                    {!(provider === 'zoom' && appointment.meeting_host_url) && creatorEmail && (
                                      <p className="text-sm text-slate-500 mt-1.5" data-testid="organizer-identity-hint">
                                        Rejoignez la réunion avec ce même compte pour être reconnu comme organisateur.
                                      </p>
                                    )}
                                    {provider === 'zoom' && appointment.meeting_host_url && (
                                      <p className="text-sm text-slate-500 mt-1.5" data-testid="organizer-identity-hint">
                                        Utilisez le lien "Démarrer la réunion" ci-dessus pour être reconnu automatiquement.
                                      </p>
                                    )}
                                  </>
                                )}
                              </div>

                              {/* Teams: Creation mode indicator */}
                              {provider === 'teams' && metadata.creation_mode === 'application_fallback' && (
                                <div className="p-4 bg-orange-50 border border-orange-300 rounded-lg" data-testid="teams-legacy-mode-warning">
                                  <div className="flex items-start gap-3">
                                    <AlertTriangle className="w-5 h-5 text-orange-600 mt-0.5 flex-shrink-0" />
                                    <div className="flex-1 min-w-0">
                                      <p className="text-sm font-semibold text-orange-900">Mode legacy — identité technique</p>
                                      <p className="text-sm text-orange-800 mt-1">
                                        Cette réunion a été créée via une identité technique (<span className="font-medium">{creatorEmail}</span>), et non via votre compte personnel.
                                      </p>
                                      <p className="text-sm text-orange-800 mt-1">
                                        Pour créer les prochaines réunions sous votre propre identité, reconnectez votre compte Outlook dans les{' '}
                                        <a href="/settings/integrations" className="underline font-semibold text-orange-900 hover:text-orange-950">paramètres d'intégration</a>.
                                      </p>
                                    </div>
                                  </div>
                                </div>
                              )}
                              {provider === 'teams' && metadata.creation_mode === 'delegated' && (
                                <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg" data-testid="teams-delegated-mode">
                                  <div className="flex items-center gap-3">
                                    <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                                    <div>
                                      <p className="text-sm font-semibold text-emerald-900">Identité Microsoft vérifiée</p>
                                      <p className="text-sm text-emerald-700 mt-0.5">Réunion créée sous votre propre identité Microsoft.</p>
                                    </div>
                                  </div>
                                </div>
                              )}

                              {/* Teams: Account warning for legacy mode */}
                              {provider === 'teams' && metadata.creation_mode !== 'delegated' && creatorEmail && (
                                <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-2.5" data-testid="teams-account-warning">
                                  <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
                                  <p className="text-sm text-amber-800">
                                    <span className="font-semibold">Attention :</span> utilisez votre compte professionnel (<span className="font-medium">{creatorEmail.split('@').pop()}</span>) dans Teams, et non un compte Microsoft personnel.
                                  </p>
                                </div>
                              )}

                              {/* Section 2: Proof availability — provider-specific */}
                              <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg" data-testid="proof-availability-block">
                                <p className="text-sm font-semibold text-slate-800 mb-2 flex items-center gap-2">
                                  <Shield className="w-4 h-4 text-slate-500" />
                                  Preuves de présence
                                </p>
                                {isMeetPersonal && (
                                  <div className="flex items-start gap-2.5 p-3 bg-red-50 border border-red-200 rounded-lg" data-testid="proof-status-no-auto">
                                    <XCircle className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
                                    <div>
                                      <p className="text-sm font-medium text-red-900">Pas de récupération automatique</p>
                                      <p className="text-sm text-red-700 mt-0.5">
                                        Avec un compte Google personnel ({creatorEmail.split('@')[1]}), Google Meet ne fournit pas de rapport de présence exploitable.
                                        Utilisez le check-in manuel ou importez une preuve alternative après la réunion.
                                      </p>
                                    </div>
                                  </div>
                                )}
                                {isMeetWorkspace && (
                                  <div className="flex items-start gap-2.5 p-3 bg-amber-50 border border-amber-200 rounded-lg" data-testid="proof-status-manual-import">
                                    <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" />
                                    <div>
                                      <p className="text-sm font-medium text-amber-900">Import manuel requis</p>
                                      <p className="text-sm text-amber-700 mt-0.5">
                                        Après la réunion, exportez le rapport de présence depuis Google Meet et importez-le dans la section "Preuves de présence visio" ci-dessous.
                                      </p>
                                    </div>
                                  </div>
                                )}
                                {(provider === 'teams' || provider === 'zoom') && (
                                  <div className="flex items-start gap-2.5 p-3 bg-emerald-50 border border-emerald-200 rounded-lg" data-testid="proof-status-auto">
                                    <CheckCircle className="w-5 h-5 text-emerald-500 mt-0.5 flex-shrink-0" />
                                    <div>
                                      <p className="text-sm font-medium text-emerald-900">Récupération automatique</p>
                                      <p className="text-sm text-emerald-700 mt-0.5">
                                        Les présences seront récupérées automatiquement depuis {providerLabel} après la fin de la réunion. Ce n'est pas une détection en temps réel.
                                      </p>
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                    ) : appointment.meeting_provider !== 'external' ? (
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-1.5 text-xs h-7 gap-1"
                        onClick={handleCreateMeeting}
                        disabled={creatingMeeting}
                        data-testid="inline-create-meeting-btn"
                      >
                        {creatingMeeting ? <Loader2 className="w-3 h-3 animate-spin" /> : <PlayCircle className="w-3 h-3" />}
                        Créer le lien de réunion
                      </Button>
                    ) : (
                      <p className="text-xs text-slate-400 mt-1.5" data-testid="meeting-link-unavailable">
                        Lien de réunion indisponible
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className={`bg-white rounded-lg border p-6 ${isCancelled ? 'border-slate-200 opacity-60' : 'border-slate-200'}`}>
            <h2 className="text-lg font-semibold text-slate-900 mb-4">Conditions financières</h2>
            <div className="space-y-3">
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg">
                <p className="text-sm font-medium text-rose-900">Pénalité</p>
                <p className="text-2xl font-bold text-rose-900">
                  {appointment.penalty_amount} {appointment.penalty_currency.toUpperCase()}
                </p>
              </div>
              
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-600">Compensation participants</span>
                  <span className="font-medium text-slate-900">{appointment.affected_compensation_percent}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">Commission plateforme</span>
                  <span className="font-medium text-slate-900">{appointment.platform_commission_percent}%</span>
                </div>
                {appointment.charity_percent > 0 && (
                  <div className="flex justify-between">
                    <span className="text-slate-600">Don caritatif</span>
                    <span className="font-medium text-slate-900">{appointment.charity_percent}%</span>
                  </div>
                )}
              </div>

              {appointment.charity_percent > 0 && appointment.charity_association_id && (
                <div className="mt-3 p-3 bg-teal-50 border border-teal-200 rounded-lg flex items-start gap-3" data-testid="charity-association-block">
                  <Heart className="w-5 h-5 text-teal-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-teal-900">
                      {appointment.charity_association_name || 'Association sélectionnée'}
                    </p>
                    <p className="text-xs text-teal-700 mt-0.5">
                      {appointment.charity_percent}% de la pénalité reversée
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Proposal Form Modal */}
        {showProposalForm && (
          <div className="bg-white rounded-lg border-2 border-blue-300 p-6 mt-6" data-testid="proposal-form">
            <div className="flex items-center gap-2 mb-4">
              <FileEdit className="w-5 h-5 text-blue-600" />
              <h2 className="text-lg font-semibold text-slate-900">Proposer une modification</h2>
            </div>
            <p className="text-sm text-slate-500 mb-4">
              Les participants devront accepter cette modification avant qu'elle ne soit appliquée.
            </p>
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="prop-datetime">Date et heure</Label>
                <Input
                  id="prop-datetime" type="datetime-local" data-testid="proposal-datetime-input"
                  value={proposalForm.start_datetime}
                  min={(() => { const n=new Date(); return `${n.getFullYear()}-${String(n.getMonth()+1).padStart(2,'0')}-${String(n.getDate()).padStart(2,'0')}T${String(n.getHours()).padStart(2,'0')}:${String(n.getMinutes()).padStart(2,'0')}`; })()}
                  onChange={(e) => setProposalForm({...proposalForm, start_datetime: e.target.value})}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="prop-duration">Durée (minutes)</Label>
                <Input
                  id="prop-duration" type="number" min="15" step="15" data-testid="proposal-duration-input"
                  value={proposalForm.duration_minutes}
                  onChange={(e) => setProposalForm({...proposalForm, duration_minutes: e.target.value})}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="prop-type">Type</Label>
                <select
                  id="prop-type" data-testid="proposal-type-select"
                  value={proposalForm.appointment_type}
                  onChange={(e) => setProposalForm({...proposalForm, appointment_type: e.target.value})}
                  className="mt-1 w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="physical">En personne</option>
                  <option value="video">Visioconférence</option>
                </select>
              </div>
              <div>
                <Label htmlFor="prop-location">{proposalForm.appointment_type === 'video' ? 'Plateforme visio' : 'Lieu'}</Label>
                {proposalForm.appointment_type === 'video' ? (
                  <select
                    id="prop-location" data-testid="proposal-provider-select"
                    value={proposalForm.meeting_provider || ''}
                    onChange={(e) => setProposalForm({...proposalForm, meeting_provider: e.target.value})}
                    className="mt-1 w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="">-- Sélectionner --</option>
                    <option value="zoom">Zoom</option>
                    <option value="teams">Microsoft Teams</option>
                    <option value="meet">Google Meet</option>
                    <option value="external">Lien externe</option>
                  </select>
                ) : (
                  <Input
                    id="prop-location" data-testid="proposal-location-input"
                    value={proposalForm.location}
                    onChange={(e) => setProposalForm({...proposalForm, location: e.target.value})}
                    className="mt-1"
                  />
                )}
              </div>
            </div>
            {proposalForm.start_datetime && new Date(proposalForm.start_datetime) <= new Date() && (
              <p className="text-sm text-red-600 mt-2" data-testid="proposal-datetime-past-error">
                La date et l'heure du rendez-vous doivent être dans le futur
              </p>
            )}
            <div className="flex gap-2 mt-4">
              <Button onClick={handleSubmitProposal} disabled={submittingProposal} data-testid="submit-proposal-btn">
                {submittingProposal ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Send className="w-4 h-4 mr-1" />}
                Envoyer la proposition
              </Button>
              <Button variant="outline" onClick={() => setShowProposalForm(false)} data-testid="cancel-proposal-form-btn">
                Annuler
              </Button>
            </div>
          </div>
        )}

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

            {/* Changes: old vs new */}
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

            {/* Responses tracker */}
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

            {/* Organizer must respond to participant proposals */}
            {activeProposal.proposed_by?.role === 'participant' && activeProposal.organizer_response?.status === 'pending' && (
              <div className="flex gap-2" data-testid="organizer-respond-proposal">
                <Button size="sm" onClick={() => handleRespondProposal(activeProposal.proposal_id, 'accept')} disabled={respondingProposal} data-testid="accept-proposal-btn">
                  <Check className="w-4 h-4 mr-1" /> Accepter
                </Button>
                <Button size="sm" variant="outline" className="text-red-600 border-red-300 hover:bg-red-50" onClick={() => handleRespondProposal(activeProposal.proposal_id, 'reject')} disabled={respondingProposal} data-testid="reject-proposal-btn">
                  <X className="w-4 h-4 mr-1" /> Refuser
                </Button>
              </div>
            )}

            {/* Cancel button for proposer */}
            {activeProposal.proposed_by?.role === 'organizer' && (
              <Button size="sm" variant="ghost" className="text-slate-500 mt-2" onClick={() => handleCancelProposal(activeProposal.proposal_id)} data-testid="cancel-active-proposal-btn">
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
          <div className="mt-4">
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
                      {Object.entries(p.changes || {}).map(([f, v]) => (
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


        {/* ORGANIZER CHECK-IN SECTION */}
        {organizerParticipant && organizerParticipant.status === 'accepted_guaranteed' && !isCancelled && (
          <div className="bg-white rounded-lg border border-indigo-200 p-6 mt-6" data-testid="organizer-checkin-section">
            <div className="flex items-center gap-2 mb-4">
              <UserCog className="w-5 h-5 text-indigo-600" />
              <h2 className="text-lg font-semibold text-slate-900">Mon check-in (organisateur)</h2>
            </div>
            {organizerCheckinDone ? (
              <div className="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
                <Check className="w-5 h-5 text-emerald-600" />
                <p className="text-sm font-medium text-emerald-700">Check-in enregistré</p>
              </div>
            ) : appointment.appointment_type === 'video' ? (
              <div className="space-y-3">
                {/* Provider-specific honest messaging */}
                {(() => {
                  const provider = (appointment.meeting_provider || '').toLowerCase();
                  const providerLabel = provider === 'zoom' ? 'Zoom' : provider === 'teams' ? 'Teams' : provider === 'meet' ? 'Google Meet' : appointment.meeting_provider;
                  const hasAutoFetch = provider === 'zoom' || provider === 'teams';
                  const creatorEmail = appointment.meeting_provider_metadata?.creator_email || '';
                  const isMeetPersonal = provider === 'meet' && (creatorEmail.endsWith('@gmail.com') || creatorEmail.endsWith('@googlemail.com'));

                  if (hasAutoFetch) {
                    return (
                      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg" data-testid="checkin-msg-auto-fetch">
                        <p className="text-sm font-medium text-blue-900 mb-1">Récupération automatique via {providerLabel}</p>
                        <p className="text-xs text-blue-700">
                          Après la fin de la réunion, les présences seront récupérées automatiquement depuis {providerLabel}. Ce n'est pas une détection en temps réel — les données sont disponibles une fois la réunion terminée.
                        </p>
                      </div>
                    );
                  } else if (isMeetPersonal) {
                    return (
                      <div className="p-3 bg-red-50 border border-red-200 rounded-lg" data-testid="checkin-msg-meet-personal">
                        <p className="text-sm font-medium text-red-900 mb-1">Aucune preuve automatique disponible</p>
                        <p className="text-xs text-red-700">
                          Avec un compte Google personnel ({creatorEmail.split('@')[1]}), Google Meet ne fournit pas de rapport de présence exploitable. Utilisez le check-in ci-dessous pour confirmer votre présence.
                        </p>
                      </div>
                    );
                  } else if (provider === 'meet') {
                    return (
                      <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg" data-testid="checkin-msg-manual-import">
                        <p className="text-sm font-medium text-amber-900 mb-1">Import manuel requis — Google Meet</p>
                        <p className="text-xs text-amber-700">
                          Après la réunion, importez le rapport de présence depuis la section "Preuves de présence visio" ci-dessous.
                        </p>
                      </div>
                    );
                  }
                  return (
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                      <p className="text-sm text-slate-700">Les preuves de présence seront vérifiées après la réunion.</p>
                    </div>
                  );
                })()}
                {/* Meet personal: check-in is PRIMARY action, not hidden */}
                {(() => {
                  const provider = (appointment.meeting_provider || '').toLowerCase();
                  const creatorEmail = appointment.meeting_provider_metadata?.creator_email || '';
                  const isMeetPersonal = provider === 'meet' && (creatorEmail.endsWith('@gmail.com') || creatorEmail.endsWith('@googlemail.com'));

                  if (isMeetPersonal) {
                    return (
                      <Button
                        onClick={handleOrganizerCheckin}
                        disabled={checkingIn}
                        className="gap-1.5"
                        data-testid="organizer-manual-checkin-btn"
                      >
                        {checkingIn ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                        Confirmer ma présence (check-in)
                      </Button>
                    );
                  }
                  // All other providers: check-in is a fallback
                  return (
                    <details className="group">
                      <summary className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer hover:text-slate-600 transition-colors">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        <span>Problème de connexion ? Check-in de secours</span>
                      </summary>
                      <div className="mt-2">
                        <Button
                          onClick={handleOrganizerCheckin}
                          disabled={checkingIn}
                          variant="outline"
                          className="gap-1.5 border-amber-300 text-amber-700 hover:bg-amber-50"
                          data-testid="organizer-manual-checkin-btn"
                        >
                          {checkingIn ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                          Check-in de secours
                        </Button>
                      </div>
                    </details>
                  );
                })()}
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-slate-600">Confirmez votre présence en tant qu'organisateur.</p>
                <div className="flex gap-2">
                  <Button
                    onClick={handleOrganizerCheckin}
                    disabled={checkingIn}
                    className="gap-1.5"
                    data-testid="organizer-manual-checkin-btn"
                  >
                    {checkingIn ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                    Check-in manuel
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
        
        {participants.length > 0 && (
          <div className={`bg-white rounded-lg border p-6 mt-6 ${isCancelled ? 'border-slate-200 opacity-60' : 'border-slate-200'}`}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900">Participants</h2>
              {!isCancelled && (
                <Link to={`/appointments/${id}/participants`}>
                  <Button variant="ghost" size="sm">
                    Voir tout
                  </Button>
                </Link>
              )}
            </div>
            <div className="space-y-2">
              {participants.slice(0, 5).map((participant) => (
                <div
                  key={participant.participant_id}
                  className="flex items-center justify-between p-3 border border-slate-200 rounded-lg"
                >
                  <div className="flex items-center gap-2">
                    <div>
                      <div className="flex items-center gap-1.5">
                        <p className="font-medium text-slate-900">
                          {participant.first_name} {participant.last_name}
                        </p>
                        {participant.is_organizer && (
                          <span className="text-xs px-1.5 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-medium" data-testid={`organizer-badge-${participant.participant_id}`}>
                            Organisateur
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-600">{participant.email}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {getParticipantStatusBadge(participant.status, participant)}
                    {participant.status === 'invited' && !isCancelled && !participant.is_organizer && (
                      <button
                        title="Renvoyer l'invitation"
                        data-testid={`resend-detail-btn-${participant.participant_id}`}
                        disabled={resendingToken === participant.invitation_token}
                        onClick={() => handleResendInvitation(participant.invitation_token)}
                        className="p-1.5 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors disabled:opacity-50"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${resendingToken === participant.invitation_token ? 'animate-spin' : ''}`} />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
            {participants.length > 5 && (
              <p className="text-sm text-slate-500 text-center mt-3">
                Et {participants.length - 5} autre(s) participant(s)
              </p>
            )}
          </div>
        )}

        {/* Live Evidence / Check-in Dashboard */}
        {!isCancelled && evidenceData?.participants?.length > 0 && (
          <div className="bg-white rounded-lg border border-slate-200 p-6 mt-6" data-testid="evidence-dashboard">
            <div className="flex items-center gap-2 mb-5">
              <ScanLine className="w-5 h-5 text-slate-700" />
              <h2 className="text-lg font-semibold text-slate-900">Check-ins & Preuves</h2>
            </div>

            <div className="space-y-5">
              {evidenceData.participants.map((p) => {
                const sources = [...new Set(p.evidence.map(e => formatSourceLabel(e.source)))];
                return (
                <div key={p.participant_id} className="border border-slate-200 rounded-xl overflow-hidden" data-testid={`evidence-participant-${p.participant_id}`}>
                  {/* Participant header */}
                  <div className="px-5 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between flex-wrap gap-2">
                    <div>
                      <p className="font-semibold text-slate-900">{p.participant_name || p.participant_email}</p>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {p.evidence.length} preuve{p.evidence.length > 1 ? 's' : ''} — Source{sources.length > 1 ? 's' : ''} : {sources.join(' + ')}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      {getStrengthBadge(p.aggregation?.strength)}
                      {getTimingBadge(p.aggregation?.timing)}
                      {p.aggregation?.temporal_flag && p.aggregation.temporal_flag !== 'valid' && p.aggregation.temporal_flag !== 'valid_late' && (
                        <span className="text-xs px-2.5 py-1 rounded-full border bg-orange-50 border-orange-200 text-orange-700 font-medium flex items-center gap-1">
                          <Timer className="w-3 h-3" />
                          {p.aggregation.temporal_flag === 'too_early' ? 'Hors fenêtre (trop tôt)' : 'Hors fenêtre (trop tard)'}
                        </span>
                      )}
                      {p.aggregation?.geographic_flag && (p.aggregation.geographic_flag === 'far' || p.aggregation.geographic_flag === 'incoherent') && (
                        <span className="text-xs px-2.5 py-1 rounded-full border bg-red-50 border-red-200 text-red-700 font-medium flex items-center gap-1">
                          <Navigation className="w-3 h-3" />
                          {p.aggregation.geographic_flag === 'incoherent' ? 'Lieu incohérent' : 'Lieu suspect'}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Evidence timeline */}
                  <div className="px-5 py-3">
                    <div className="space-y-3">
                      {p.evidence
                        .sort((a, b) => new Date(a.source_timestamp) - new Date(b.source_timestamp))
                        .map((e, idx) => {
                        const facts = e.derived_facts || {};
                        const hasGPS = facts.latitude != null && facts.longitude != null;

                        return (
                          <div key={e.evidence_id} className={`pl-4 border-l-[3px] ${getSourceColor(e.source)}`} data-testid={`evidence-item-${e.evidence_id}`}>
                            <div className="flex items-start gap-2">
                              {getSourceIcon(e.source)}
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <p className="text-sm font-medium text-slate-800">
                                    {formatSourceLabel(e.source)}
                                  </p>
                                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                                    e.confidence_score === 'high' ? 'bg-emerald-100 text-emerald-700' :
                                    e.confidence_score === 'medium' ? 'bg-amber-100 text-amber-700' :
                                    'bg-red-100 text-red-700'
                                  }`}>
                                    {e.confidence_score === 'high' ? 'Confiance haute' : e.confidence_score === 'medium' ? 'Confiance moyenne' : 'Confiance faible'}
                                  </span>
                                  {/* Source trust badge for video evidence */}
                                  {e.source === 'video_conference' && facts.source_trust && (
                                    <span
                                      data-testid={`source-trust-badge-${e.evidence_id}`}
                                      className={`text-xs px-1.5 py-0.5 rounded inline-flex items-center gap-1 ${
                                        facts.source_trust === 'api_verified'
                                          ? 'bg-blue-100 text-blue-700'
                                          : 'bg-orange-100 text-orange-700'
                                      }`}
                                    >
                                      {facts.source_trust === 'api_verified' ? (
                                        <><Shield className="w-3 h-3" /> Vérifié par API</>
                                      ) : (
                                        <><Upload className="w-3 h-3" /> Import manuel</>
                                      )}
                                    </span>
                                  )}
                                </div>

                                <p className="text-sm text-slate-600 mt-0.5" data-testid={`evidence-date-${e.evidence_id}`}>
                                  {e.source === 'manual_checkin' ? 'Arrivé le ' : e.source === 'video_conference' ? 'Connecté le ' : 'Enregistré le '}
                                  {formatEvidenceDate(e.source_timestamp)}
                                </p>

                                {/* Temporal consistency */}
                                {facts.temporal_detail && (
                                  <p className={`text-xs mt-1 flex items-center gap-1 ${
                                    facts.temporal_consistency === 'valid' ? 'text-emerald-600' :
                                    facts.temporal_consistency === 'valid_late' ? 'text-amber-600' :
                                    'text-red-600'
                                  }`}>
                                    <Timer className="w-3 h-3" />
                                    {facts.temporal_detail}
                                  </p>
                                )}

                                {/* GPS: address + coordinates + distance */}
                                {hasGPS && (
                                  <div className="mt-2 space-y-1">
                                    {facts.address_label && (
                                      <p className="text-xs text-slate-700">
                                        Adresse estimée : <span className="font-medium">{facts.address_label.split(',').slice(0, 3).join(', ')}</span>
                                      </p>
                                    )}
                                    <p className="text-xs text-slate-500">
                                      Coordonnées : {facts.latitude.toFixed(4)}, {facts.longitude.toFixed(4)}
                                    </p>

                                    {/* Distance from RDV */}
                                    {facts.distance_km != null && (
                                      <p className={`text-xs font-medium flex items-center gap-1 ${
                                        facts.geographic_consistency === 'close' ? 'text-emerald-600' :
                                        facts.geographic_consistency === 'nearby' ? 'text-emerald-600' :
                                        facts.geographic_consistency === 'far' ? 'text-amber-600' :
                                        facts.geographic_consistency === 'incoherent' ? 'text-red-600' :
                                        'text-slate-500'
                                      }`} data-testid={`evidence-distance-${e.evidence_id}`}>
                                        <Navigation className="w-3 h-3" />
                                        Distance du lieu du RDV : {facts.distance_km < 1 ? `${Math.round(facts.distance_meters)}m` : `${facts.distance_km} km`}
                                        {facts.geographic_consistency === 'close' && ' — sur place'}
                                        {facts.geographic_consistency === 'nearby' && ' — à proximité'}
                                        {facts.geographic_consistency === 'far' && ' — suspect'}
                                        {facts.geographic_consistency === 'incoherent' && ' — incohérent'}
                                      </p>
                                    )}

                                    {facts.gps_no_reference && !facts.distance_km && (
                                      <p className="text-xs text-slate-400">Pas de coordonnées de référence pour le RDV</p>
                                    )}

                                    <a
                                      href={`https://www.google.com/maps?q=${facts.latitude},${facts.longitude}`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 hover:underline"
                                      data-testid={`gps-map-link-${e.evidence_id}`}
                                    >
                                      <ExternalLink className="w-3 h-3" />
                                      Voir sur la carte
                                    </a>
                                  </div>
                                )}

                                {/* QR details */}
                                {e.source === 'qr' && facts.qr_valid && (
                                  <p className="text-xs text-blue-600 mt-1 flex items-center gap-1">
                                    <QrCode className="w-3 h-3" />
                                    QR valide (fenêtre #{facts.qr_window})
                                  </p>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Video Evidence Section — visible for video appointments */}
        {!isCancelled && appointment.appointment_type === 'video' && (
          <div className="bg-white rounded-lg border border-slate-200 p-6 mt-6" data-testid="video-evidence-section">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-2">
                <Monitor className="w-5 h-5 text-indigo-700" />
                <h2 className="text-lg font-semibold text-slate-900">Preuves de présence visio</h2>
                {appointment.meeting_provider && (
                  <span className={`text-xs px-2 py-0.5 rounded-full ${getProviderIcon(appointment.meeting_provider).bg} ${getProviderIcon(appointment.meeting_provider).color} font-medium`}>
                    {getProviderIcon(appointment.meeting_provider).label}
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                {/* Create Meeting button — shown if no meeting link yet */}
                {!appointment.meeting_join_url && appointment.meeting_provider && (
                  <Button
                    variant="default"
                    size="sm"
                    onClick={handleCreateMeeting}
                    disabled={creatingMeeting}
                    data-testid="create-meeting-btn"
                  >
                    {creatingMeeting ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <PlayCircle className="w-4 h-4 mr-1" />}
                    Créer la réunion
                  </Button>
                )}
              </div>
            </div>

            {/* Provider-specific action bar */}
            {(() => {
              const provider = (appointment.meeting_provider || '').toLowerCase();
              const hasAutoFetch = provider === 'zoom' || provider === 'teams';
              const providerLabel = provider === 'zoom' ? 'Zoom' : provider === 'teams' ? 'Teams' : 'Google Meet';
              const meetingEnd = appointment.start_datetime && appointment.duration_minutes
                ? new Date(new Date(appointment.start_datetime).getTime() + appointment.duration_minutes * 60000)
                : null;
              const isMeetingEnded = meetingEnd && new Date() > meetingEnd;
              const hasEvidence = videoEvidence?.total_video_evidence > 0;

              return (
                <div className="mb-5" data-testid="video-evidence-action-bar">
                  {hasAutoFetch ? (
                    <div className={`rounded-lg border p-4 ${hasEvidence ? 'bg-emerald-50 border-emerald-200' : isMeetingEnded ? 'bg-blue-50 border-blue-200' : 'bg-slate-50 border-slate-200'}`}>
                      <div className="flex items-center justify-between">
                        <div>
                          {hasEvidence ? (
                            <p className="text-sm font-medium text-emerald-800" data-testid="evidence-status-fetched">Présences récupérées via {providerLabel}</p>
                          ) : isMeetingEnded ? (
                            <>
                              <p className="text-sm font-medium text-blue-900" data-testid="evidence-status-ready">Réunion terminée — présences disponibles</p>
                              <p className="text-xs text-blue-700 mt-0.5">Récupérez les présences depuis {providerLabel}, ou attendez la récupération automatique.</p>
                            </>
                          ) : (
                            <>
                              <p className="text-sm font-medium text-slate-700" data-testid="evidence-status-waiting">Réunion en cours ou à venir</p>
                              <p className="text-xs text-slate-500 mt-0.5">Les présences seront récupérées automatiquement depuis {providerLabel} après la fin de la réunion.</p>
                            </>
                          )}
                        </div>
                        <div className="flex gap-2 ml-4 shrink-0">
                          {appointment.meeting_join_url && (
                            <Button
                              variant={isMeetingEnded && !hasEvidence ? 'default' : 'outline'}
                              size="sm"
                              onClick={handleFetchAttendance}
                              disabled={fetchingAttendance}
                              data-testid="fetch-attendance-btn"
                            >
                              {fetchingAttendance ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <RefreshCw className="w-4 h-4 mr-1" />}
                              Récupérer les présences
                            </Button>
                          )}
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setShowVideoIngest(!showVideoIngest)}
                            data-testid="toggle-video-ingest-btn"
                          >
                            <Upload className="w-4 h-4 mr-1" />
                            Import manuel
                          </Button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    /* Google Meet: manual import is the primary action */
                    <div className={`rounded-lg border p-4 ${hasEvidence ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}`}>
                      <div className="flex items-center justify-between">
                        <div>
                          {hasEvidence ? (
                            <p className="text-sm font-medium text-emerald-800" data-testid="evidence-status-fetched">Présences importées pour {providerLabel}</p>
                          ) : (
                            <>
                              <p className="text-sm font-medium text-amber-900" data-testid="evidence-status-meet-manual">Import requis — {providerLabel}</p>
                              <p className="text-xs text-amber-700 mt-0.5">Google Meet ne fournit pas de rapport automatique. Après la réunion, importez le rapport de présence (CSV ou JSON).</p>
                            </>
                          )}
                        </div>
                        <div className="ml-4 shrink-0">
                          <Button
                            variant={!hasEvidence ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => setShowVideoIngest(!showVideoIngest)}
                            className={!hasEvidence ? 'bg-amber-600 hover:bg-amber-700' : ''}
                            data-testid="toggle-video-ingest-btn"
                          >
                            <Upload className="w-4 h-4 mr-1" />
                            Importer le rapport de présence
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })()}

            {/* Ingestion Form — redesigned with file upload + JSON mode */}
            {showVideoIngest && (
              <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-5 mb-5" data-testid="video-ingest-form">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <FileJson className="w-4 h-4 text-indigo-600" />
                    <p className="text-sm font-semibold text-indigo-900">Importer un rapport de présence</p>
                  </div>
                  <div className="flex gap-1 bg-indigo-100 rounded-md p-0.5">
                    <button
                      onClick={() => setIngestMode('file')}
                      className={`text-xs px-3 py-1 rounded ${ingestMode === 'file' ? 'bg-white text-indigo-700 shadow-sm font-medium' : 'text-indigo-500'}`}
                      data-testid="ingest-mode-file"
                    >
                      Fichier (CSV/JSON)
                    </button>
                    <button
                      onClick={() => setIngestMode('json')}
                      className={`text-xs px-3 py-1 rounded ${ingestMode === 'json' ? 'bg-white text-indigo-700 shadow-sm font-medium' : 'text-indigo-500'}`}
                      data-testid="ingest-mode-json"
                    >
                      JSON avancé
                    </button>
                  </div>
                </div>

                <div className="grid md:grid-cols-3 gap-3 mb-3">
                  <div>
                    <Label htmlFor="video-provider" className="text-xs text-slate-700">Provider</Label>
                    <select
                      id="video-provider"
                      data-testid="video-provider-select"
                      value={videoIngestForm.provider}
                      onChange={(e) => setVideoIngestForm({...videoIngestForm, provider: e.target.value})}
                      className="mt-1 w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm"
                    >
                      <option value="zoom">Zoom</option>
                      <option value="teams">Microsoft Teams</option>
                      <option value="meet">Google Meet</option>
                    </select>
                  </div>
                  <div>
                    <Label htmlFor="video-meeting-id" className="text-xs text-slate-700">ID réunion externe (optionnel)</Label>
                    <Input
                      id="video-meeting-id"
                      data-testid="video-meeting-id-input"
                      value={videoIngestForm.external_meeting_id}
                      onChange={(e) => setVideoIngestForm({...videoIngestForm, external_meeting_id: e.target.value})}
                      placeholder="ex: 123456789"
                      className="mt-1 h-9"
                    />
                  </div>
                  <div>
                    <Label htmlFor="video-join-url" className="text-xs text-slate-700">URL de la réunion (optionnel)</Label>
                    <Input
                      id="video-join-url"
                      data-testid="video-join-url-input"
                      value={videoIngestForm.meeting_join_url}
                      onChange={(e) => setVideoIngestForm({...videoIngestForm, meeting_join_url: e.target.value})}
                      placeholder="https://zoom.us/j/..."
                      className="mt-1 h-9"
                    />
                  </div>
                </div>

                {/* File upload mode */}
                {ingestMode === 'file' && (
                  <div>
                    <p className="text-xs text-indigo-700 mb-3">
                      Importez le rapport de présence {videoIngestForm.provider === 'zoom' ? 'Zoom' : videoIngestForm.provider === 'teams' ? 'Teams' : 'Google Meet'} (export CSV ou JSON).
                      {videoIngestForm.provider === 'zoom' && ' Dans Zoom, allez dans Reports > Meeting > Participants pour exporter le CSV.'}
                    </p>
                    <div className="border-2 border-dashed border-indigo-300 rounded-lg p-6 text-center bg-white/50 hover:bg-white transition-colors">
                      <input
                        type="file"
                        accept=".csv,.json"
                        onChange={handleFileSelect}
                        className="hidden"
                        id="attendance-file-input"
                        data-testid="attendance-file-input"
                      />
                      <label htmlFor="attendance-file-input" className="cursor-pointer">
                        <FileUp className="w-8 h-8 mx-auto mb-2 text-indigo-400" />
                        <p className="text-sm text-indigo-700 font-medium">Cliquez pour choisir un fichier</p>
                        <p className="text-xs text-indigo-500 mt-1">CSV ou JSON — max 5 Mo</p>
                      </label>
                    </div>

                    {/* File preview */}
                    {selectedFile && (
                      <div className="mt-3 p-3 bg-white rounded-lg border border-indigo-200">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <FileJson className="w-4 h-4 text-indigo-500" />
                            <span className="text-sm font-medium text-slate-700">{selectedFile.name}</span>
                            <span className="text-xs text-slate-400">({(selectedFile.size / 1024).toFixed(1)} Ko)</span>
                          </div>
                          <button onClick={() => { setSelectedFile(null); setCsvPreview(null); }} className="text-xs text-red-500 hover:text-red-700">Supprimer</button>
                        </div>

                        {/* CSV/JSON preview */}
                        {csvPreview && csvPreview.type === 'csv' && (
                          <div>
                            <p className="text-xs text-slate-500 mb-2">{csvPreview.total} participant(s) détecté(s) — aperçu :</p>
                            <div className="overflow-x-auto">
                              <table className="w-full text-xs">
                                <thead>
                                  <tr className="bg-slate-50">
                                    {csvPreview.headers?.slice(0, 5).map((h, i) => (
                                      <th key={i} className="px-2 py-1 text-left font-medium text-slate-600 border-b">{h}</th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {csvPreview.rows?.map((row, i) => (
                                    <tr key={i} className="border-b border-slate-100">
                                      {csvPreview.headers?.slice(0, 5).map((h, j) => (
                                        <td key={j} className="px-2 py-1 text-slate-500">{row[h] || '—'}</td>
                                      ))}
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                            {csvPreview.total > 5 && <p className="text-xs text-slate-400 mt-1">...et {csvPreview.total - 5} autre(s)</p>}
                          </div>
                        )}
                        {csvPreview && csvPreview.type === 'json' && (
                          <div>
                            <p className="text-xs text-slate-500 mb-1">{csvPreview.total} participant(s) détecté(s)</p>
                            {csvPreview.participants?.map((p, i) => (
                              <div key={i} className="text-xs text-slate-500 py-0.5">
                                {p.user_email || p.emailAddress || p.email || p.name || 'Anonyme'}
                              </div>
                            ))}
                          </div>
                        )}
                        {csvPreview && csvPreview.type === 'error' && (
                          <p className="text-xs text-red-500">{csvPreview.message}</p>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* JSON mode (advanced) */}
                {ingestMode === 'json' && (
                  <div>
                    <Label htmlFor="video-raw-json" className="text-xs text-slate-700">Rapport de présence (JSON)</Label>
                    <textarea
                      id="video-raw-json"
                      data-testid="video-raw-json-input"
                      rows={6}
                      value={videoIngestForm.raw_json}
                      onChange={(e) => setVideoIngestForm({...videoIngestForm, raw_json: e.target.value})}
                      placeholder={videoIngestForm.provider === 'zoom'
                        ? '{\n  "meeting_id": "123456789",\n  "participants": [\n    {"user_email": "john@example.com", "name": "John Doe", "join_time": "2026-01-01T10:00:00Z", "leave_time": "2026-01-01T11:00:00Z", "duration": 3600}\n  ]\n}'
                        : videoIngestForm.provider === 'teams'
                        ? '{\n  "meeting_id": "AAMkAG...",\n  "attendanceRecords": [\n    {"emailAddress": "john@example.com", "identity": {"displayName": "John Doe"}, "totalAttendanceInSeconds": 3600, "attendanceIntervals": [{"joinDateTime": "2026-01-01T10:00:00Z", "leaveDateTime": "2026-01-01T11:00:00Z"}]}\n  ]\n}'
                        : '{\n  "meeting_id": "abc-defg-hij",\n  "participants": [\n    {"name": "John Doe", "email": "john@example.com", "join_time": "2026-01-01T10:00:00Z", "leave_time": "2026-01-01T11:00:00Z", "duration": 3600}\n  ]\n}'
                      }
                      className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                    />
                  </div>
                )}

                {videoIngestForm.provider === 'meet' && (
                  <div className="flex items-start gap-2 mt-3 p-2.5 bg-amber-50 border border-amber-200 rounded-md">
                    <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
                    <p className="text-xs text-amber-800">
                      <strong>Google Meet = preuve assistée uniquement.</strong> Les identités Meet ne sont pas vérifiées par Google.
                      Toute preuve Meet sera marquée comme confiance faible et nécessitera une revue manuelle.
                    </p>
                  </div>
                )}
                <div className="flex gap-2 mt-4">
                  {ingestMode === 'file' ? (
                    <Button onClick={handleFileUpload} disabled={uploadingFile || !selectedFile} size="sm" data-testid="submit-file-upload-btn">
                      {uploadingFile ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Upload className="w-4 h-4 mr-1" />}
                      Analyser et ingérer ({selectedFile?.name || 'aucun fichier'})
                    </Button>
                  ) : (
                    <Button onClick={handleVideoIngest} disabled={ingestingVideo || !videoIngestForm.raw_json.trim()} size="sm" data-testid="submit-video-ingest-btn">
                      {ingestingVideo ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Upload className="w-4 h-4 mr-1" />}
                      Analyser et ingérer
                    </Button>
                  )}
                  <Button variant="outline" size="sm" onClick={() => { setShowVideoIngest(false); setSelectedFile(null); setCsvPreview(null); }}>Annuler</Button>
                </div>
              </div>
            )}

            {/* Video Evidence Timeline */}
            {videoEvidence?.video_evidence?.length > 0 ? (
              <div className="space-y-4">
                {videoEvidence.video_evidence.map((ve) => {
                  const facts = ve.derived_facts || {};
                  const providerInfo = getProviderIcon(facts.provider);
                  return (
                    <div key={ve.evidence_id} className="border border-slate-200 rounded-xl overflow-hidden" data-testid={`video-evidence-${ve.evidence_id}`}>
                      <div className="px-5 py-3 bg-indigo-50/50 border-b border-slate-200 flex items-center justify-between flex-wrap gap-2">
                        <div className="flex items-center gap-3">
                          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${providerInfo.bg} ${providerInfo.color}`}>
                            <Monitor className="w-3 h-3" />
                            {providerInfo.label}
                          </span>
                          {facts.participant_email_from_provider && (
                            <span className="text-xs text-slate-500">{facts.participant_email_from_provider}</span>
                          )}
                          {facts.participant_name_from_provider && !facts.participant_email_from_provider && (
                            <span className="text-xs text-slate-500">{facts.participant_name_from_provider}</span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 flex-wrap">
                          {getVideoOutcomeBadge(facts.video_attendance_outcome)}
                          {getIdentityConfidenceBadge(facts.identity_confidence)}
                          {facts.provider_evidence_ceiling === 'assisted' && (
                            <span className="text-xs px-2 py-0.5 rounded-full border bg-amber-50 border-amber-200 text-amber-700 font-medium flex items-center gap-1">
                              <AlertTriangle className="w-3 h-3" />
                              Preuve assistée
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="px-5 py-3 space-y-2">
                        {/* Join / Leave times */}
                        <div className="flex items-center gap-4 text-sm">
                          {facts.joined_at && (
                            <span className="flex items-center gap-1 text-emerald-700">
                              <Check className="w-3.5 h-3.5" />
                              Connecté : {formatEvidenceDate(facts.joined_at)}
                            </span>
                          )}
                          {facts.left_at && (
                            <span className="flex items-center gap-1 text-slate-500">
                              <X className="w-3.5 h-3.5" />
                              Déconnecté : {formatEvidenceDate(facts.left_at)}
                            </span>
                          )}
                          {facts.duration_seconds != null && (
                            <span className="text-xs text-slate-400">
                              Durée : {Math.round(facts.duration_seconds / 60)} min
                            </span>
                          )}
                        </div>

                        {/* Temporal info */}
                        {facts.temporal_detail && (
                          <p className={`text-xs flex items-center gap-1 ${
                            facts.temporal_consistency === 'valid' ? 'text-emerald-600' :
                            facts.temporal_consistency === 'valid_late' ? 'text-amber-600' :
                            'text-red-600'
                          }`}>
                            <Timer className="w-3 h-3" />
                            {facts.temporal_detail}
                          </p>
                        )}

                        {/* Identity matching info */}
                        <div className="flex items-center gap-2 text-xs text-slate-500">
                          <UserCog className="w-3 h-3" />
                          <span>{facts.identity_match_detail}</span>
                        </div>

                        {/* Confidence badge */}
                        <div className="flex items-center gap-2">
                          <span className={`text-xs px-1.5 py-0.5 rounded ${
                            ve.confidence_score === 'high' ? 'bg-emerald-100 text-emerald-700' :
                            ve.confidence_score === 'medium' ? 'bg-amber-100 text-amber-700' :
                            'bg-red-100 text-red-700'
                          }`}>
                            Confiance {ve.confidence_score === 'high' ? 'haute' : ve.confidence_score === 'medium' ? 'moyenne' : 'faible'}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-8 text-slate-400" data-testid="no-video-evidence">
                <Monitor className="w-10 h-10 mx-auto mb-2 text-slate-300" />
                {(() => {
                  const provider = (appointment.meeting_provider || '').toLowerCase();
                  if (provider === 'meet') {
                    return (
                      <>
                        <p className="text-sm text-slate-500">Aucune preuve de présence importée.</p>
                        <p className="text-xs text-amber-600 mt-1 font-medium">Google Meet requiert un import manuel du rapport de présence.</p>
                      </>
                    );
                  }
                  if (provider === 'zoom' || provider === 'teams') {
                    return (
                      <>
                        <p className="text-sm text-slate-500">Aucune preuve de présence récupérée.</p>
                        <p className="text-xs text-slate-400 mt-1">Les présences seront récupérées automatiquement après la fin de la réunion, ou utilisez le bouton ci-dessus.</p>
                      </>
                    );
                  }
                  return <p className="text-sm">Aucune preuve de présence visio pour le moment.</p>;
                })()}
              </div>
            )}

            {/* Ingestion Logs */}
            {videoIngestionLogs.length > 0 && (
              <div className="mt-5 pt-4 border-t border-slate-200">
                <p className="text-sm font-medium text-slate-600 mb-2">Historique d'ingestion</p>
                <div className="space-y-2">
                  {videoIngestionLogs.map((log) => (
                    <div key={log.ingestion_log_id} className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg text-xs" data-testid={`ingestion-log-${log.ingestion_log_id}`}>
                      <div className="flex items-center gap-3">
                        <span className={`px-2 py-0.5 rounded-full font-medium ${getProviderIcon(log.provider).bg} ${getProviderIcon(log.provider).color}`}>
                          {getProviderIcon(log.provider).label}
                        </span>
                        <span className="text-slate-500">
                          {log.matched_count || 0} matché(s), {log.unmatched_count || 0} non-matché(s)
                        </span>
                        {log.provider_evidence_ceiling === 'assisted' && (
                          <span className="text-amber-600 font-medium">Preuve assistée</span>
                        )}
                      </div>
                      <span className="text-slate-400">{formatEvidenceDate(log.ingested_at)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Attendance Section */}
        {!isCancelled && isAppointmentEnded() && (
          <div className="bg-white rounded-lg border border-slate-200 p-6 mt-6" data-testid="attendance-section">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <ClipboardCheck className="w-5 h-5 text-slate-700" />
                <h2 className="text-lg font-semibold text-slate-900">Détection de présence</h2>
              </div>
              {!attendance?.evaluated && (
                <Button
                  onClick={handleEvaluateAttendance}
                  disabled={evaluating}
                  size="sm"
                  data-testid="evaluate-attendance-btn"
                >
                  {evaluating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ClipboardCheck className="w-4 h-4 mr-2" />}
                  Évaluer la présence
                </Button>
              )}
              {attendance?.evaluated && (
                <Button
                  onClick={handleReevaluateAttendance}
                  disabled={evaluating}
                  size="sm"
                  variant="outline"
                  data-testid="reevaluate-attendance-btn"
                >
                  {evaluating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
                  Re-évaluer
                </Button>
              )}
            </div>

            {attendance?.evaluated ? (
              <>
                {/* Summary cards */}
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-5">
                  {[
                    { key: 'on_time', label: 'Présents', color: 'emerald' },
                    { key: 'late', label: 'En retard', color: 'amber' },
                    { key: 'no_show', label: 'Absents', color: 'red' },
                    { key: 'manual_review', label: 'À vérifier', color: 'yellow' },
                    { key: 'waived', label: 'Dispensés', color: 'slate' },
                  ].map(({ key, label, color }) => (
                    <div key={key} className={`text-center p-3 rounded-lg bg-${color}-50 border border-${color}-200`} data-testid={`attendance-summary-${key}`}>
                      <p className={`text-xl font-bold text-${color}-800`}>{attendance.summary?.[key] || 0}</p>
                      <p className={`text-xs text-${color}-600`}>{label}</p>
                    </div>
                  ))}
                </div>

                {/* Individual records */}
                <div className="space-y-2">
                  {attendance.records?.map((record) => {
                    const pEvidence = getParticipantEvidence(record.participant_id);
                    return (
                    <div
                      key={record.record_id}
                      className="flex items-center justify-between p-3 border border-slate-200 rounded-lg"
                      data-testid={`attendance-record-${record.record_id}`}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="font-medium text-slate-900 truncate">{record.participant_name || record.participant_email}</p>
                          {getEvidenceIcons(pEvidence)}
                        </div>
                        <p className="text-xs text-slate-500">{getDecisionLabel(record.decision_basis)}</p>
                        {pEvidence?.aggregation && pEvidence.aggregation.evidence_count > 0 && (
                          <div className="flex items-center gap-2 mt-1">
                            {getStrengthBadge(pEvidence.aggregation.strength)}
                            {pEvidence.aggregation.earliest_evidence && (
                              <span className="text-xs text-slate-400">
                                Check-in {formatTimeFr(pEvidence.aggregation.earliest_evidence)}
                              </span>
                            )}
                          </div>
                        )}
                        {record.notes && <p className="text-xs text-slate-400 mt-0.5 italic">{record.notes}</p>}
                      </div>
                      <div className="flex items-center gap-2 ml-3 flex-shrink-0">
                        {getOutcomeBadge(record.outcome, record.decision_basis)}

                        {/* Reclassify dropdown */}
                        <div className="relative">
                          <button
                            onClick={() => setReclassifyDropdown(reclassifyDropdown === record.record_id ? null : record.record_id)}
                            className="p-1.5 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                            title="Reclassifier"
                            data-testid={`reclassify-btn-${record.record_id}`}
                            disabled={reclassifying === record.record_id}
                          >
                            {reclassifying === record.record_id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <ChevronDown className="w-4 h-4" />
                            )}
                          </button>
                          {reclassifyDropdown === record.record_id && (
                            <div className="absolute right-0 top-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-20 py-1 min-w-[150px]">
                              {reclassifyOptions
                                .filter(o => o.value !== record.outcome)
                                .map(option => (
                                  <button
                                    key={option.value}
                                    onClick={() => handleReclassify(record.record_id, option.value)}
                                    className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-50 ${option.color}`}
                                    data-testid={`reclassify-option-${option.value}`}
                                  >
                                    {option.label}
                                  </button>
                                ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                    );
                  })}
                </div>

                <p className="text-xs text-slate-400 mt-3">
                  Évalué le {formatDateTimeFr(attendance.evaluated_at)} — Décisions automatiques, modifiables par l'organisateur
                </p>
              </>
            ) : (
              <div className="text-center py-6 text-slate-500">
                <ClipboardCheck className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                <p className="text-sm">L'évaluation de présence n'a pas encore été effectuée.</p>
                <p className="text-xs text-slate-400 mt-1">Cliquez sur "Évaluer la présence" ou attendez l'évaluation automatique (toutes les 10 min après fin du RDV + 30 min).</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Cancel Confirmation Modal */}
      {showCancelModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => !cancelling && setShowCancelModal(false)}>
          <div 
            className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            <div className="bg-red-50 p-4 flex items-center gap-3 border-b border-red-100">
              <div className="p-2 bg-red-100 rounded-full">
                <AlertTriangle className="w-6 h-6 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-red-800">Annuler le rendez-vous</h3>
            </div>
            
            <div className="p-6">
              <p className="text-slate-700 mb-4">
                Voulez-vous vraiment annuler ce rendez-vous ?
              </p>
              <ul className="text-sm text-slate-600 space-y-2 mb-6">
                <li className="flex items-start gap-2">
                  <span className="text-red-500">•</span>
                  Les {participants.length} participant(s) seront immédiatement notifié(s) par email.
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-red-500">•</span>
                  Le rendez-vous sera conservé dans l'historique avec le statut "Annulé".
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-red-500">•</span>
                  Les invitations ne pourront plus être acceptées.
                </li>
              </ul>
            </div>
            
            <div className="flex gap-3 p-4 bg-slate-50 border-t border-slate-100">
              <Button
                variant="outline"
                onClick={() => setShowCancelModal(false)}
                disabled={cancelling}
                className="flex-1"
              >
                Retour
              </Button>
              <Button
                onClick={handleCancelAppointment}
                disabled={cancelling}
                className="flex-1 bg-red-600 hover:bg-red-700 text-white"
                data-testid="confirm-cancel-btn"
              >
                {cancelling ? 'Annulation...' : 'Confirmer l\'annulation'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
