import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { appointmentAPI, participantAPI, calendarAPI, invitationAPI, attendanceAPI, checkinAPI, modificationAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { ArrowLeft, Calendar, MapPin, Video, Clock, Users, Ban, Check, X, AlertTriangle, Download, Heart, ShieldCheck, CreditCard, RefreshCw, Loader2, Zap, ClipboardCheck, Eye, UserX, UserCheck, HelpCircle, ChevronDown, ScanLine, QrCode, MapPinCheck, ExternalLink, Timer, Navigation, Pencil, Save, Send, FileEdit } from 'lucide-react';
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
  const [proposalHistory, setProposalHistory] = useState([]);
  const [showProposalForm, setShowProposalForm] = useState(false);
  const [proposalForm, setProposalForm] = useState({
    start_datetime: '', duration_minutes: '', location: '',
    meeting_provider: '', appointment_type: ''
  });
  const [submittingProposal, setSubmittingProposal] = useState(false);
  const [respondingProposal, setRespondingProposal] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

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
      setParticipants(participantsRes.data.participants || []);

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
    } catch (error) {
      toast.error('Erreur lors du chargement');
    } finally {
      setLoading(false);
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
    const labels = { manual_checkin: 'Check-in manuel', qr: 'QR code', gps: 'GPS', system: 'Système' };
    return labels[source] || source;
  };

  const formatEvidenceDate = (ts) => formatEvidenceDateFr(ts);

  const getSourceIcon = (source) => {
    if (source === 'manual_checkin') return <MapPinCheck className="w-4 h-4 text-emerald-600" />;
    if (source === 'qr') return <QrCode className="w-4 h-4 text-blue-600" />;
    if (source === 'gps') return <MapPin className="w-4 h-4 text-purple-600" />;
    return <ScanLine className="w-4 h-4 text-slate-500" />;
  };

  const getSourceColor = (source) => {
    if (source === 'manual_checkin') return 'border-l-emerald-500';
    if (source === 'qr') return 'border-l-blue-500';
    if (source === 'gps') return 'border-l-purple-500';
    return 'border-l-slate-300';
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
              appointment.status === 'draft' ? 'bg-slate-100 text-slate-800' :
              'bg-slate-100 text-slate-600'
            }`}>
              {appointment.status === 'active' ? 'Actif' : 
               appointment.status === 'cancelled' ? 'Annulé' :
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
          <div className={`bg-white rounded-lg border p-6 ${isCancelled ? 'border-slate-200 opacity-60' : 'border-slate-200'}`}>
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
                <div className="flex items-start gap-3">
                  <Video className="w-5 h-5 text-slate-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-slate-700">Plateforme</p>
                    <p className="text-slate-900">{appointment.meeting_provider}</p>
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
                <Input
                  id="prop-location" data-testid="proposal-location-input"
                  value={proposalForm.appointment_type === 'video' ? proposalForm.meeting_provider : proposalForm.location}
                  onChange={(e) => {
                    if (proposalForm.appointment_type === 'video') {
                      setProposalForm({...proposalForm, meeting_provider: e.target.value});
                    } else {
                      setProposalForm({...proposalForm, location: e.target.value});
                    }
                  }}
                  className="mt-1"
                />
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
                  <div>
                    <p className="font-medium text-slate-900">
                      {participant.first_name} {participant.last_name}
                    </p>
                    <p className="text-sm text-slate-600">{participant.email}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {getParticipantStatusBadge(participant.status, participant)}
                    {participant.status === 'invited' && !isCancelled && (
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
                                </div>

                                <p className="text-sm text-slate-600 mt-0.5" data-testid={`evidence-date-${e.evidence_id}`}>
                                  {e.source === 'manual_checkin' ? 'Arrivé le ' : 'Enregistré le '}
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
