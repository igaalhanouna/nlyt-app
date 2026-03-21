import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { appointmentAPI, participantAPI, calendarAPI, invitationAPI, attendanceAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { ArrowLeft, Calendar, MapPin, Video, Clock, Users, Ban, Check, X, AlertTriangle, Download, Heart, ShieldCheck, CreditCard, RefreshCw, Loader2, Zap, ClipboardCheck, Eye, UserX, UserCheck, HelpCircle, ChevronDown } from 'lucide-react';
import { toast } from 'sonner';

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
      const attRes = await attendanceAPI.get(id);
      setAttendance(attRes.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erreur lors de l'évaluation");
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
    };
    return labels[basis] || basis;
  };

  // Check if appointment has ended (for showing evaluate button)
  const isAppointmentEnded = () => {
    if (!appointment?.start_datetime) return false;
    const start = new Date(appointment.start_datetime);
    const end = new Date(start.getTime() + (appointment.duration_minutes || 60) * 60000);
    return new Date() > end;
  };

  const reclassifyOptions = [
    { value: 'on_time', label: 'Présent', color: 'text-emerald-700' },
    { value: 'late', label: 'En retard', color: 'text-amber-700' },
    { value: 'no_show', label: 'Absent', color: 'text-red-700' },
    { value: 'waived', label: 'Dispensé', color: 'text-slate-600' },
  ];

  // Status badge helper
  const getParticipantStatusBadge = (status) => {
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
            <h2 className="text-lg font-semibold text-slate-900 mb-4">Informations générales</h2>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <Calendar className="w-5 h-5 text-slate-500 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-slate-700">Date et heure</p>
                  <p className="text-slate-900">
                    {new Date(appointment.start_datetime).toLocaleString('fr-FR', {
                      dateStyle: 'full',
                      timeStyle: 'short'
                    })}
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
                    {getParticipantStatusBadge(participant.status)}
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
                  {attendance.records?.map((record) => (
                    <div
                      key={record.record_id}
                      className="flex items-center justify-between p-3 border border-slate-200 rounded-lg"
                      data-testid={`attendance-record-${record.record_id}`}
                    >
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-slate-900 truncate">{record.participant_name || record.participant_email}</p>
                        <p className="text-xs text-slate-500">{getDecisionLabel(record.decision_basis)}</p>
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
                  ))}
                </div>

                <p className="text-xs text-slate-400 mt-3">
                  Évalué le {new Date(attendance.evaluated_at).toLocaleString('fr-FR')} — Décisions automatiques, modifiables par l'organisateur
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
