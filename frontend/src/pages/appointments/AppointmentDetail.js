import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { appointmentAPI, participantAPI, calendarAPI, invitationAPI, attendanceAPI, checkinAPI, modificationAPI, videoEvidenceAPI, proofAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { ArrowLeft, Calendar, MapPin, Video, Clock, Users, Ban, Check, X, AlertTriangle, Download, Heart, ShieldCheck, CreditCard, RefreshCw, Loader2, Zap, ClipboardCheck, Eye, UserX, UserCheck, HelpCircle, ChevronDown, ScanLine, QrCode, MapPinCheck, ExternalLink, Timer, Navigation, Pencil, Save, Send, FileEdit, Upload, Monitor, Shield, FileJson, Link2, UserCog, FileUp, PlayCircle, Settings2, DollarSign, CheckCircle, XCircle, Copy, Activity, Fingerprint } from 'lucide-react';
import { toast } from 'sonner';
import { formatDateTimeFr, formatTimeFr, formatEvidenceDateFr, parseUTC, utcToLocalInput, localInputToUTC } from '../../utils/dateFormat';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import ProofSessionsPanel from './ProofSessionsPanel';
import VideoEvidencePanel from './VideoEvidencePanel';
import AttendancePanel from './AttendancePanel';
import ModificationProposals from './ModificationProposals';
import EvidenceDashboard from './EvidenceDashboard';

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
  const [organizerCheckinData, setOrganizerCheckinData] = useState(null);
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
  const [fetchAttendanceError, setFetchAttendanceError] = useState(null);
  const [proofSessions, setProofSessions] = useState([]);
  const [validatingSession, setValidatingSession] = useState(null);
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
            if (res.data?.evidence_count > 0) {
              setOrganizerCheckinDone(true);
              const gpsEv = res.data.evidence?.find(e => e.source === 'gps' || (e.derived_facts?.latitude));
              if (gpsEv) setOrganizerCheckinData(gpsEv);
            }
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
      // Load proof sessions (non-blocking)
      proofAPI.getSessions(id)
        .then(res => setProofSessions(res.data?.sessions || []))
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
      const payload = {
        appointment_id: id,
        invitation_token: organizerParticipant.invitation_token,
        device_info: navigator.userAgent,
      };

      // Request GPS for physical appointments — handle each browser error explicitly
      if (appointment.appointment_type === 'physical' && navigator.geolocation) {
        try {
          console.log('[CHECKIN:ORG] Requesting GPS position...');
          const pos = await new Promise((resolve, reject) =>
            navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 8000, enableHighAccuracy: true })
          );
          payload.latitude = pos.coords.latitude;
          payload.longitude = pos.coords.longitude;
          payload.gps_consent = true;
          console.log(`[CHECKIN:ORG] GPS acquired: lat=${pos.coords.latitude}, lon=${pos.coords.longitude}, accuracy=${pos.coords.accuracy}m`);
        } catch (geoErr) {
          console.warn(`[CHECKIN:ORG] GPS error: code=${geoErr.code}, message=${geoErr.message}`);
          if (geoErr.code === 1) {
            toast.warning('Localisation refusée. Le check-in sera enregistré sans coordonnées GPS. Vous pouvez autoriser la localisation dans les paramètres de votre navigateur.');
          } else if (geoErr.code === 2) {
            toast.warning('Position GPS indisponible. Le check-in continuera sans coordonnées.');
          } else if (geoErr.code === 3) {
            toast.warning('Délai GPS dépassé. Le check-in continuera sans coordonnées.');
          }
          // Continue without GPS — not a blocker
        }
      }

      console.log(`[CHECKIN:ORG] Sending organizer check-in: hasGPS=${!!payload.latitude}`);
      const checkinRes = await checkinAPI.manual(payload);
      console.log('[CHECKIN:ORG] Success');
      setOrganizerCheckinDone(true);
      if (checkinRes.data?.evidence?.derived_facts) {
        setOrganizerCheckinData(checkinRes.data.evidence);
      } else if (payload.latitude) {
        setOrganizerCheckinData({ derived_facts: { latitude: payload.latitude, longitude: payload.longitude } });
      }
      toast.success('Check-in organisateur enregistré');
      loadData();
    } catch (error) {
      console.error('[CHECKIN:ORG] Error:', error.response?.status, error.response?.data);
      const status = error.response?.status;
      const detail = error.response?.data?.detail;
      if (status === 409) {
        toast.info('Check-in déjà effectué. Votre présence est enregistrée.');
        setOrganizerCheckinDone(true);
      } else if (status === 400) {
        toast.error(detail || 'Impossible d\'effectuer le check-in. Vérifiez que l\'invitation est bien acceptée.');
      } else if (status === 404) {
        toast.error(detail || 'Invitation introuvable.');
      } else if (!error.response) {
        toast.error('Impossible de contacter le serveur. Vérifiez votre connexion internet et réessayez.');
      } else {
        toast.error(detail || 'Erreur lors du check-in.');
      }
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

  const handleValidateSession = async (sessionId, status) => {
    setValidatingSession(sessionId);
    try {
      await proofAPI.validate(id, sessionId, status);
      toast.success(`Session validée : ${status === 'present' ? 'Présent' : status === 'partial' ? 'Partiel' : 'Absent'}`);
      const res = await proofAPI.getSessions(id);
      setProofSessions(res.data?.sessions || []);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erreur lors de la validation");
    } finally {
      setValidatingSession(null);
    }
  };

  const handleCopyProofLink = (participant) => {
    const frontendUrl = window.location.origin;
    const link = `${frontendUrl}/proof/${id}?token=${participant.invitation_token}`;
    navigator.clipboard.writeText(link).then(() => {
      toast.success(`Lien copié pour ${participant.first_name || participant.email}`);
    }).catch(() => {
      toast.error('Impossible de copier le lien');
    });
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
    const icsUrl = calendarAPI.exportICS(id);
    window.open(icsUrl, '_blank');
    toast.success('Fichier iCalendar téléchargé');
  };

  // Attendance outcome badge
  const getOutcomeBadge = (outcome, decisionBasis) => {
    const badges = {
      on_time: { bg: 'bg-emerald-100', text: 'text-emerald-800', icon: <UserCheck className="w-3 h-3" />, label: 'Présent' },
      late: { bg: 'bg-amber-100', text: 'text-amber-800', icon: <Clock className="w-3 h-3" />, label: 'Dépassement' },
      no_show: { bg: 'bg-red-100', text: 'text-red-800', icon: <UserX className="w-3 h-3" />, label: decisionBasis === 'cancelled_late' ? 'Désengagement tardif' : 'Absent' },
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
      cancellation_date_parse_error: 'Date de désengagement non lisible',
      accepted_no_guarantee: 'Accepté sans garantie',
      pending_guarantee: 'Garantie en attente',
      no_proof_of_attendance: 'Pas de preuve de présence',
      strong_evidence_on_time: 'Preuve forte — à l\'heure',
      strong_evidence_late: 'Preuve forte — dépassement',
      medium_evidence_on_time: 'Preuve moyenne — à l\'heure',
      medium_evidence_late: 'Preuve moyenne — dépassement',
      weak_evidence: 'Preuve faible',
      video_strong_on_time: 'Visio — preuve forte, connecté à l\'heure',
      video_strong_late: 'Visio — preuve forte, connecté en dépassement',
      video_medium_joined_on_time: 'Visio — preuve moyenne, connecté à l\'heure',
      video_medium_joined_late: 'Visio — preuve moyenne, connecté en dépassement',
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
    { value: 'late', label: 'Dépassement', color: 'text-amber-700' },
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
    return <span className="text-xs px-2.5 py-1 rounded-full border bg-amber-50 border-amber-200 text-amber-700 font-medium">Dépassement</span>;
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
      joined_late: { bg: 'bg-amber-100', text: 'text-amber-800', label: 'Connecté en dépassement' },
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
    setFetchAttendanceError(null);
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
      const detail = err.response?.data?.detail || 'Erreur lors de la récupération des présences';
      const isPlanError = detail.toLowerCase().includes('paid') || detail.toLowerCase().includes('plan');
      const isLegacyError = detail.toLowerCase().includes('legacy');
      setFetchAttendanceError({ message: detail, isPlanError, isLegacyError });
      if (!isPlanError) {
        toast.error(detail);
      }
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
        <div className="flex items-center justify-between mb-6">
          <Link to="/dashboard">
            <Button variant="ghost">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Retour au tableau de bord
            </Button>
          </Link>
          <div>
            <span className="block text-lg font-bold tracking-[0.35em] text-slate-900 text-right">N<span className="text-slate-400">·</span>L<span className="text-slate-400">·</span>Y<span className="text-slate-400">·</span>T</span>
            <span className="block text-[10px] font-medium tracking-[0.25em] text-slate-400 uppercase text-right">Never Lose Your Time</span>
          </div>
        </div>

        {/* Cancelled Banner */}
        {isCancelled && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 flex items-center gap-3">
            <Ban className="w-6 h-6 text-red-600" />
            <div>
              <p className="font-semibold text-red-800">Cet engagement a été annulé</p>
              <p className="text-sm text-red-600">
                Les participants ont été notifiés. Cet engagement n'aura pas lieu.
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
            {/* Apple Calendar / ICS export button */}
            <div className="relative group">
              <Button 
                variant="outline"
                onClick={handleDownloadICS}
                data-testid="download-ics-btn"
                className="gap-2"
              >
                <Download className="w-4 h-4" />
                Autres calendriers (.ics)
              </Button>
              <div className="absolute left-0 top-full mt-1 w-64 bg-slate-800 text-white text-xs rounded-lg px-3 py-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-lg">
                Télécharge un fichier iCalendar (.ics) compatible avec Apple Calendar, Thunderbird et tout calendrier standard.
              </div>
            </div>

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
                  Annuler l'engagement
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
                <p className="text-sm text-slate-600">Minutes de dépassement</p>
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
                <p className="text-sm text-slate-600">Délai de désengagement</p>
                {appointment.cancellation_deadline_hours_original && appointment.cancellation_deadline_hours_original !== appointment.cancellation_deadline_hours && (
                  <p className="text-xs text-amber-600 mt-0.5" data-testid="deadline-adjusted-note">
                    Ajusté de {appointment.cancellation_deadline_hours_original}h (short notice)
                  </p>
                )}
              </div>
            </div>
            <div className="text-xs text-slate-500">Avant compensation</div>
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
                        {(() => {
                          // Organizer MUST go through NLYT Proof (no direct visio bypass)
                          const orgToken = organizerParticipant?.invitation_token;
                          if (orgToken) {
                            return (
                              <div className="flex flex-col gap-1.5">
                                <a
                                  href={`/proof/${appointment.appointment_id}?token=${orgToken}`}
                                  className="inline-flex items-center gap-1.5 text-sm font-semibold text-blue-600 hover:text-blue-800 hover:underline"
                                  data-testid="organizer-proof-link"
                                >
                                  <Shield className="w-3.5 h-3.5" />
                                  Confirmer ma présence et rejoindre
                                </a>
                                <p className="text-xs text-slate-400 flex items-center gap-1">
                                  <Fingerprint className="w-3 h-3" />
                                  Votre présence sera enregistrée avant d'ouvrir la visio
                                </p>
                              </div>
                            );
                          }

                          // Fallback: no organizer token (should not happen)
                          return (
                            <div className="flex flex-col gap-1.5">
                              <p className="text-xs text-amber-600 flex items-center gap-1">
                                <AlertTriangle className="w-3.5 h-3.5" />
                                Lien NLYT Proof indisponible — token organisateur manquant
                              </p>
                            </div>
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
                              {creatorEmail && (
                                <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
                                  <p className="text-sm font-semibold text-slate-800 mb-1.5 flex items-center gap-2">
                                    <UserCog className="w-4 h-4 text-slate-500" />
                                    Connexion en tant qu'organisateur
                                  </p>
                                  <p className="text-sm text-slate-600">
                                    Réunion créée avec le compte {providerLabel} : <span className="font-semibold text-slate-900" data-testid="organizer-account-email">{creatorEmail}</span>
                                    {creatorName && <span className="text-slate-400"> ({creatorName})</span>}
                                  </p>
                                  {!(provider === 'zoom' && appointment.meeting_host_url) && (
                                    <p className="text-sm text-slate-500 mt-1.5" data-testid="organizer-identity-hint">
                                      Rejoignez la réunion via le lien NLYT Proof pour enregistrer votre présence automatiquement.
                                    </p>
                                  )}
                                  {provider === 'zoom' && appointment.meeting_host_url && (
                                    <p className="text-sm text-slate-500 mt-1.5" data-testid="organizer-identity-hint">
                                      Le lien NLYT Proof ci-dessus ouvrira automatiquement la visio après votre check-in.
                                    </p>
                                  )}
                                </div>
                              )}

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
                                <div className="flex items-start gap-2.5 p-3 bg-blue-50 border border-blue-200 rounded-lg" data-testid="proof-status-nlyt">
                                  <CheckCircle className="w-5 h-5 text-blue-500 mt-0.5 flex-shrink-0" />
                                  <div>
                                    <p className="text-sm font-medium text-blue-900">Vérification NLYT Proof</p>
                                    <p className="text-sm text-blue-700 mt-0.5">
                                      Les participants utilisent leur lien NLYT personnel pour confirmer leur présence (check-in + heartbeat). C'est le mode principal de vérification.
                                    </p>
                                  </div>
                                </div>
                                {(provider === 'teams' || provider === 'zoom') && (
                                  <div className="flex items-start gap-2.5 p-3 bg-emerald-50 border border-emerald-200 rounded-lg mt-2" data-testid="proof-status-auto">
                                    <CheckCircle className="w-5 h-5 text-emerald-500 mt-0.5 flex-shrink-0" />
                                    <div>
                                      <p className="text-sm font-medium text-emerald-900">Bonus : récupération API {providerLabel}</p>
                                      <p className="text-sm text-emerald-700 mt-0.5">
                                        Si votre compte {providerLabel} le permet, les présences seront aussi récupérées automatiquement après la fin de la réunion.
                                      </p>
                                    </div>
                                  </div>
                                )}
                                {isMeetPersonal && (
                                  <div className="flex items-start gap-2.5 p-3 bg-slate-100 border border-slate-200 rounded-lg mt-2" data-testid="proof-status-no-auto">
                                    <HelpCircle className="w-5 h-5 text-slate-400 mt-0.5 flex-shrink-0" />
                                    <div>
                                      <p className="text-sm font-medium text-slate-700">Pas de récupération API Google Meet</p>
                                      <p className="text-sm text-slate-500 mt-0.5">
                                        Avec un compte Google personnel, la récupération API n'est pas disponible. NLYT Proof reste votre source de vérification principale.
                                      </p>
                                    </div>
                                  </div>
                                )}
                                {isMeetWorkspace && (
                                  <div className="flex items-start gap-2.5 p-3 bg-amber-50 border border-amber-200 rounded-lg mt-2" data-testid="proof-status-manual-import">
                                    <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" />
                                    <div>
                                      <p className="text-sm font-medium text-amber-900">Import manuel Google Meet possible</p>
                                      <p className="text-sm text-amber-700 mt-0.5">
                                        Après la réunion, vous pouvez exporter le rapport de présence Google Meet et l'importer comme preuve complémentaire.
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
                <p className="text-sm font-medium text-rose-900">Compensation</p>
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
                      {appointment.charity_percent}% de la compensation reversée
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Modification Proposals */}
        <ModificationProposals
          showProposalForm={showProposalForm} setShowProposalForm={setShowProposalForm}
          proposalForm={proposalForm} setProposalForm={setProposalForm}
          submittingProposal={submittingProposal} onSubmitProposal={handleSubmitProposal}
          activeProposal={activeProposal}
          respondingProposal={respondingProposal} onRespondProposal={handleRespondProposal} onCancelProposal={handleCancelProposal}
          proposalHistory={proposalHistory}
          showHistory={showHistory} setShowHistory={setShowHistory}
        />

        {/* ORGANIZER CHECK-IN SECTION */}
        {organizerParticipant && organizerParticipant.status === 'accepted_guaranteed' && !isCancelled && (
          <div className="bg-white rounded-lg border border-indigo-200 p-6 mt-6" data-testid="organizer-checkin-section">
            <div className="flex items-center gap-2 mb-4">
              <UserCog className="w-5 h-5 text-indigo-600" />
              <h2 className="text-lg font-semibold text-slate-900">Mon check-in (organisateur)</h2>
            </div>
            {organizerCheckinDone ? (
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg space-y-2">
                <div className="flex items-center gap-2">
                  <Check className="w-5 h-5 text-emerald-600" />
                  <p className="text-sm font-medium text-emerald-700">Check-in enregistré</p>
                </div>
                {organizerCheckinData?.derived_facts && (
                  <div className="pl-7 space-y-1" data-testid="organizer-gps-details">
                    {organizerCheckinData.derived_facts.latitude && (
                      <p className="text-xs text-slate-500">
                        <MapPin className="w-3 h-3 inline mr-1" />
                        {Number(organizerCheckinData.derived_facts.latitude).toFixed(5)}, {Number(organizerCheckinData.derived_facts.longitude).toFixed(5)}
                      </p>
                    )}
                    {organizerCheckinData.derived_facts.distance_km != null && (
                      <p className="text-xs text-slate-500">
                        Distance : {organizerCheckinData.derived_facts.distance_km < 1
                          ? `${Math.round(organizerCheckinData.derived_facts.distance_km * 1000)} m`
                          : `${organizerCheckinData.derived_facts.distance_km.toFixed(2)} km`
                        } du lieu de l'engagement
                      </p>
                    )}
                    {organizerCheckinData.derived_facts.address_label && (
                      <p className="text-xs text-slate-400">{organizerCheckinData.derived_facts.address_label}</p>
                    )}
                  </div>
                )}
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
                <p className="text-sm text-slate-600">Confirmez votre présence en tant qu'organisateur. Vos coordonnées GPS seront enregistrées.</p>
                <div className="flex gap-2">
                  <Button
                    onClick={handleOrganizerCheckin}
                    disabled={checkingIn}
                    className="gap-1.5"
                    data-testid="organizer-manual-checkin-btn"
                  >
                    {checkingIn ? <Loader2 className="w-4 h-4 animate-spin" /> : <><MapPin className="w-4 h-4" /><Check className="w-4 h-4" /></>}
                    Check-in avec GPS
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

        {/* Evidence Dashboard — PHYSICAL appointments only */}
        {!isCancelled && appointment.appointment_type === 'physical' && (
          <EvidenceDashboard
            participants={participants}
            evidenceData={evidenceData}
            appointment={appointment}
          />
        )}

        {/* NLYT Proof Sessions Section */}
        {!isCancelled && appointment.appointment_type === 'video' && (
          <ProofSessionsPanel
            participants={participants}
            proofSessions={proofSessions}
            validatingSession={validatingSession}
            onValidateSession={handleValidateSession}
          />
        )}

        {/* Video Evidence Section */}
        {!isCancelled && appointment.appointment_type === 'video' && (
          <VideoEvidencePanel
            appointment={appointment}
            videoEvidence={videoEvidence}
            videoIngestionLogs={videoIngestionLogs}
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

        {/* Attendance Section */}
        {!isCancelled && isAppointmentEnded() && (
          <AttendancePanel
            attendance={attendance}
            evaluating={evaluating}
            onEvaluate={handleEvaluateAttendance}
            onReevaluate={handleReevaluateAttendance}
            onReclassify={handleReclassify}
            reclassifying={reclassifying}
            reclassifyDropdown={reclassifyDropdown}
            setReclassifyDropdown={setReclassifyDropdown}
            participants={participants}
            getParticipantEvidence={(pid) => {
              if (!evidenceData?.participants) return null;
              const pe = evidenceData.participants.find(p => p.participant_id === pid);
              return pe?.evidence || [];
            }}
          />
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
              <h3 className="text-lg font-semibold text-red-800">Annuler l'engagement</h3>
            </div>
            
            <div className="p-6">
              <p className="text-slate-700 mb-4">
                Voulez-vous vraiment annuler cet engagement ?
              </p>
              <ul className="text-sm text-slate-600 space-y-2 mb-6">
                <li className="flex items-start gap-2">
                  <span className="text-red-500">•</span>
                  Les {participants.length} participant(s) seront immédiatement notifié(s) par email.
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-red-500">•</span>
                  L'engagement sera conservé dans l'historique avec le statut "Annulé".
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
