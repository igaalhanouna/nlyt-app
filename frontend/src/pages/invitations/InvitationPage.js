import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { Calendar, MapPin, Clock, Users, AlertTriangle, Check, X, Loader2, Ban, Download, CreditCard, ShieldCheck, MapPinCheck, QrCode, ScanLine, FileEdit, Send, Pencil } from 'lucide-react';
import QRCheckin from '../../components/QRCheckin';
import { formatDateTimeFr, formatTimeFr, formatDateShortFr, formatEvidenceDateFr, formatActionDateFr, parseUTC, utcToLocalInput, localInputToUTC } from '../../utils/dateFormat';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function InvitationPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [invitation, setInvitation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [responding, setResponding] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState(null);
  const [responseStatus, setResponseStatus] = useState(null);
  const [guaranteeMessage, setGuaranteeMessage] = useState(null);
  const [checkinStatus, setCheckinStatus] = useState(null);
  const [checkingIn, setCheckingIn] = useState(false);
  const [showQRScanner, setShowQRScanner] = useState(false);
  const [showQRDisplay, setShowQRDisplay] = useState(false);
  const [qrData, setQrData] = useState(null);
  const [qrRefreshInterval, setQrRefreshInterval] = useState(null);
  const [activeProposal, setActiveProposal] = useState(null);
  const [respondingProposal, setRespondingProposal] = useState(false);
  const [showProposeForm, setShowProposeForm] = useState(false);
  const [proposalForm, setProposalForm] = useState({ start_datetime: '', duration_minutes: '', location: '' });
  const [submittingProposal, setSubmittingProposal] = useState(false);
  const [guaranteeRevalidation, setGuaranteeRevalidation] = useState(null);
  const [reconfirming, setReconfirming] = useState(false);

  useEffect(() => {
    // Check for Stripe redirect params
    const guaranteeStatus = searchParams.get('guarantee_status');
    const sessionId = searchParams.get('session_id');
    
    if (guaranteeStatus === 'success' && sessionId) {
      // Poll for guarantee confirmation
      pollGuaranteeStatus(sessionId);
    } else if (guaranteeStatus === 'cancelled') {
      setGuaranteeMessage({
        type: 'warning',
        text: 'Vous avez annulé la configuration de la garantie. Votre participation n\'est pas encore confirmée.'
      });
    }
    
    fetchInvitation();
  }, [token]);

  const pollGuaranteeStatus = async (sessionId, attempts = 0) => {
    const maxAttempts = 10;
    const pollInterval = 2000;

    if (attempts >= maxAttempts) {
      setGuaranteeMessage({
        type: 'info',
        text: 'Vérification en cours... Veuillez rafraîchir la page dans quelques instants.'
      });
      return;
    }

    try {
      const response = await fetch(`${API_URL}/api/invitations/${token}/guarantee-status?session_id=${sessionId}`);
      const data = await response.json();

      if (data.is_guaranteed) {
        setResponseStatus('accepted_guaranteed');
        setGuaranteeMessage({
          type: 'success',
          text: 'Garantie confirmée ! Votre participation est maintenant validée.'
        });
        fetchInvitation(); // Refresh data
        return;
      }

      // Continue polling
      setTimeout(() => pollGuaranteeStatus(sessionId, attempts + 1), pollInterval);
    } catch (error) {
      console.error('Error polling guarantee status:', error);
    }
  };

  const fetchInvitation = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/api/invitations/${token}`);
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Invitation non trouvée');
      }
      
      const data = await response.json();
      setInvitation(data);
      
      // Check guarantee revalidation status
      if (data.guarantee_revalidation?.requires_revalidation) {
        setGuaranteeRevalidation(data.guarantee_revalidation);
      } else {
        setGuaranteeRevalidation(null);
      }

      // Check if already responded
      if (['accepted', 'accepted_guaranteed', 'accepted_pending_guarantee', 'declined', 'cancelled_by_participant'].includes(data.participant.status)) {
        setResponseStatus(data.participant.status);
      }

      // Load active proposal for this appointment
      if (data.appointment?.appointment_id) {
        try {
          const propRes = await fetch(`${API_URL}/api/modifications/active/${data.appointment.appointment_id}`);
          if (propRes.ok) {
            const propData = await propRes.json();
            setActiveProposal(propData.proposal || null);
          }
        } catch {}
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResponse = async (action) => {
    try {
      setResponding(true);
      setError(null);
      
      const response = await fetch(`${API_URL}/api/invitations/${token}/respond`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ action }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Erreur lors de la réponse');
      }
      
      const data = await response.json();
      
      // Check if Stripe redirect is required
      if (data.requires_guarantee && data.checkout_url) {
        setGuaranteeMessage({
          type: 'info',
          text: 'Redirection vers la page de garantie...'
        });
        // Redirect to Stripe Checkout
        window.location.href = data.checkout_url;
        return;
      }
      
      setResponseStatus(data.status);
      
      // Update invitation data
      setInvitation(prev => ({
        ...prev,
        participant: {
          ...prev.participant,
          status: data.status,
          accepted_at: data.participant?.accepted_at,
          declined_at: data.participant?.declined_at,
        },
        engagement_rules: {
          ...prev.engagement_rules,
          can_cancel: ['accepted', 'accepted_guaranteed'].includes(data.status) && !prev.engagement_rules.cancellation_deadline_passed
        }
      }));
    } catch (err) {
      setError(err.message);
    } finally {
      setResponding(false);
    }
  };

  // --- Modification proposal functions ---
  const handleRespondToProposal = async (action) => {
    if (!activeProposal) return;
    setRespondingProposal(true);
    try {
      const res = await fetch(`${API_URL}/api/modifications/${activeProposal.proposal_id}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, invitation_token: token })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Erreur');
      }
      const data = await res.json();
      setActiveProposal(data.status === 'pending' ? data : null);
      if (data.status === 'accepted') {
        fetchInvitation(); // Reload to reflect applied changes
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setRespondingProposal(false);
    }
  };

  const handleSubmitParticipantProposal = async () => {
    const changes = {};
    const apt = invitation.appointment;
    const f = proposalForm;
    const utcDt = f.start_datetime ? localInputToUTC(f.start_datetime) : '';
    if (utcDt && utcDt !== apt.start_datetime) changes.start_datetime = utcDt;
    if (f.duration_minutes && Number(f.duration_minutes) !== apt.duration_minutes) changes.duration_minutes = Number(f.duration_minutes);
    if (f.location && f.location !== (apt.location || '')) changes.location = f.location;

    if (Object.keys(changes).length === 0) { setError('Aucune modification détectée'); return; }
    if (changes.start_datetime && new Date(changes.start_datetime) <= new Date()) { setError('La nouvelle date doit être dans le futur'); return; }

    setSubmittingProposal(true);
    try {
      const res = await fetch(`${API_URL}/api/modifications/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          appointment_id: apt.appointment_id,
          invitation_token: token,
          changes
        })
      });
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Erreur'); }
      const data = await res.json();
      setActiveProposal(data);
      setShowProposeForm(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmittingProposal(false);
    }
  };

  // --- Guarantee reconfirmation ---
  const handleReconfirmGuarantee = async () => {
    setReconfirming(true);
    try {
      const res = await fetch(`${API_URL}/api/invitations/${token}/reconfirm-guarantee`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Erreur lors de la reconfirmation');
      }
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setReconfirming(false);
    }
  };

  // --- Check-in functions ---
  const loadCheckinStatus = useCallback(async () => {
    if (!invitation?.appointment?.appointment_id) return;
    try {
      const res = await fetch(`${API_URL}/api/checkin/status/${invitation.appointment.appointment_id}?invitation_token=${token}`);
      if (res.ok) {
        const data = await res.json();
        setCheckinStatus(data);
      }
    } catch (e) { /* silent */ }
  }, [invitation?.appointment?.appointment_id, token]);

  useEffect(() => {
    if (invitation && ['accepted', 'accepted_guaranteed', 'accepted_pending_guarantee'].includes(invitation.participant?.status)) {
      loadCheckinStatus();
    }
  }, [invitation, loadCheckinStatus]);

  const handleManualCheckin = async () => {
    setCheckingIn(true);
    try {
      const payload = { invitation_token: token, device_info: navigator.userAgent };

      // Ask for GPS if available
      if (navigator.geolocation) {
        try {
          const pos = await new Promise((resolve, reject) =>
            navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000, enableHighAccuracy: true })
          );
          payload.latitude = pos.coords.latitude;
          payload.longitude = pos.coords.longitude;
          payload.gps_consent = true;
        } catch (e) { /* GPS not available, continue without */ }
      }

      const res = await fetch(`${API_URL}/api/checkin/manual`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        if (res.status === 409) {
          // Already checked in
        } else {
          alert(data.detail || 'Erreur');
        }
      }
      loadCheckinStatus();
    } catch (e) {
      alert('Erreur réseau');
    } finally {
      setCheckingIn(false);
    }
  };

  const handleShowQR = async () => {
    try {
      const res = await fetch(`${API_URL}/api/checkin/qr/${invitation.appointment.appointment_id}?invitation_token=${token}`);
      if (res.ok) {
        const data = await res.json();
        setQrData(data);
        setShowQRDisplay(true);
        // Auto-refresh QR
        const interval = setInterval(async () => {
          try {
            const r = await fetch(`${API_URL}/api/checkin/qr/${invitation.appointment.appointment_id}?invitation_token=${token}`);
            if (r.ok) setQrData(await r.json());
          } catch (e) { /* ignore */ }
        }, (data.rotation_seconds || 60) * 1000);
        setQrRefreshInterval(interval);
      }
    } catch (e) { /* ignore */ }
  };

  const handleCloseQR = () => {
    setShowQRDisplay(false);
    if (qrRefreshInterval) {
      clearInterval(qrRefreshInterval);
      setQrRefreshInterval(null);
    }
  };

  const handleQRScanSuccess = () => {
    setShowQRScanner(false);
    loadCheckinStatus();
  };

  const handleCancelParticipation = async () => {
    try {
      setCancelling(true);
      const response = await fetch(`${API_URL}/api/invitations/${token}/cancel`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Erreur lors de l\'annulation');
      }
      
      const data = await response.json();
      setResponseStatus(data.status);
      
      // Update invitation data
      setInvitation(prev => ({
        ...prev,
        participant: {
          ...prev.participant,
          status: data.status,
          cancelled_at: data.participant.cancelled_at,
        },
        engagement_rules: {
          ...prev.engagement_rules,
          can_cancel: false
        }
      }));
    } catch (err) {
      setError(err.message);
    } finally {
      setCancelling(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center" data-testid="invitation-loading">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-slate-600 mx-auto mb-4" />
          <p className="text-slate-600">Chargement de l'invitation...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4" data-testid="invitation-error">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <X className="w-8 h-8 text-red-600" />
          </div>
          <h1 className="text-2xl font-bold text-slate-800 mb-2">Invitation introuvable</h1>
          <p className="text-slate-600 mb-6">{error}</p>
          <button
            onClick={() => navigate('/')}
            className="px-6 py-2 bg-slate-800 text-white rounded-lg hover:bg-slate-700 transition-colors"
          >
            Retour à l'accueil
          </button>
        </div>
      </div>
    );
  }

  const { participant, appointment, organizer, engagement_rules, other_participants } = invitation;

  // Determine status badge
  const getStatusBadge = (status) => {
    // If guarantee needs revalidation, show specific badge
    if (guaranteeRevalidation?.requires_revalidation && status === 'accepted_guaranteed') {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-sm font-medium" data-testid="status-badge-revalidation">
          <AlertTriangle className="w-4 h-4" /> À reconfirmer
        </span>
      );
    }

    switch (status) {
      case 'accepted_guaranteed':
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium" data-testid="status-badge-guaranteed">
            <ShieldCheck className="w-4 h-4" /> Garanti
          </span>
        );
      case 'accepted_pending_guarantee':
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-sm font-medium" data-testid="status-badge-pending-guarantee">
            <CreditCard className="w-4 h-4" /> Garantie en cours
          </span>
        );
      case 'accepted':
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium" data-testid="status-badge-accepted">
            <Check className="w-4 h-4" /> Accepté
          </span>
        );
      case 'declined':
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 bg-red-100 text-red-800 rounded-full text-sm font-medium" data-testid="status-badge-declined">
            <X className="w-4 h-4" /> Refusé
          </span>
        );
      case 'cancelled_by_participant':
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 bg-orange-100 text-orange-800 rounded-full text-sm font-medium" data-testid="status-badge-cancelled">
            <Ban className="w-4 h-4" /> Annulé
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-sm font-medium" data-testid="status-badge-invited">
            <Clock className="w-4 h-4" /> En attente
          </span>
        );
    }
  };

  // Check if appointment is cancelled or deleted
  const isAppointmentCancelled = appointment.status === 'cancelled';
  const isAppointmentDeleted = appointment.status === 'deleted';
  const isAppointmentUnavailable = isAppointmentCancelled || isAppointmentDeleted;
  const isAppointmentPast = (() => {
    const start = parseUTC(appointment.start_datetime);
    if (!start) return true;
    const end = new Date(start.getTime() + (appointment.duration_minutes || 60) * 60000);
    return new Date() > end;
  })();

  // Check-in section (shared between accepted states)
  const renderCheckinSection = () => {
    const isCheckedIn = checkinStatus?.checked_in;

    // Parse UTC start datetime — backend always returns UTC (with 'Z')
    const startStr = appointment.start_datetime;
    const startDate = parseUTC(startStr);
    if (!startDate) return null;

    const durationMin = appointment.duration_minutes || 60;
    const toleratedDelay = appointment.tolerated_delay_minutes || engagement_rules?.tolerated_delay_minutes || 0;
    const WINDOW_BEFORE_MIN = 30;

    const windowOpen = new Date(startDate.getTime() - WINDOW_BEFORE_MIN * 60000);
    const windowClose = new Date(startDate.getTime() + (durationMin + toleratedDelay) * 60000);
    const now = new Date();

    const isBefore = now < windowOpen;
    const isDuring = now >= windowOpen && now <= windowClose;
    const isAfter = now > windowClose;

    // Format countdown
    const formatCountdown = () => {
      const diff = windowOpen - now;
      const days = Math.floor(diff / 86400000);
      const hours = Math.floor((diff % 86400000) / 3600000);
      const mins = Math.floor((diff % 3600000) / 60000);
      if (days > 0) return `${days}j ${hours}h`;
      if (hours > 0) return `${hours}h ${mins}min`;
      return `${mins} min`;
    };

    const formatTime = (d) => formatTimeFr(d.toISOString());
    const formatDate = (d) => formatDateShortFr(d.toISOString());

    return (
      <div className="bg-white rounded-2xl border-2 border-slate-200 overflow-hidden mt-6" data-testid="checkin-section">
        {/* Header band */}
        <div className={`px-5 py-3 text-center font-semibold text-sm ${
          isCheckedIn ? 'bg-emerald-600 text-white' :
          isDuring ? 'bg-blue-600 text-white' :
          isBefore ? 'bg-slate-100 text-slate-600' :
          'bg-slate-100 text-slate-500'
        }`}>
          {isCheckedIn ? 'Présence confirmée' :
           isDuring ? 'Confirmer votre présence' :
           isBefore ? 'Check-in bientôt disponible' :
           'Fenêtre de check-in terminée'}
        </div>

        <div className="p-5">
          {/* STATE: Already checked in */}
          {isCheckedIn && (
            <div className="text-center" data-testid="checkin-done">
              <div className="w-14 h-14 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <Check className="w-7 h-7 text-emerald-600" />
              </div>
              <p className="font-semibold text-emerald-800 text-base">Présence enregistrée</p>
              {checkinStatus.earliest_checkin && (
                <p className="text-sm text-emerald-600 mt-1">
                  le {formatEvidenceDateFr(checkinStatus.earliest_checkin)}
                </p>
              )}
              <div className="flex items-center justify-center gap-4 mt-3">
                {checkinStatus.has_manual_checkin && (
                  <span className="inline-flex items-center gap-1.5 text-xs bg-emerald-50 text-emerald-700 px-3 py-1.5 rounded-full font-medium">
                    <MapPinCheck className="w-3.5 h-3.5" /> Arrivée confirmée
                  </span>
                )}
                {checkinStatus.has_qr_checkin && (
                  <span className="inline-flex items-center gap-1.5 text-xs bg-blue-50 text-blue-700 px-3 py-1.5 rounded-full font-medium">
                    <QrCode className="w-3.5 h-3.5" /> QR validé
                  </span>
                )}
                {checkinStatus.has_gps && (
                  <span className="inline-flex items-center gap-1.5 text-xs bg-purple-50 text-purple-700 px-3 py-1.5 rounded-full font-medium">
                    <MapPin className="w-3.5 h-3.5" /> Position GPS
                  </span>
                )}
              </div>
            </div>
          )}

          {/* STATE: Before window */}
          {!isCheckedIn && isBefore && (
            <div className="text-center" data-testid="checkin-before">
              <div className="w-14 h-14 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <Clock className="w-7 h-7 text-slate-400" />
              </div>
              <p className="font-medium text-slate-700 text-sm">
                Le check-in ouvrira dans <span className="font-bold text-slate-900">{formatCountdown()}</span>
              </p>
              <p className="text-xs text-slate-500 mt-2">
                Disponible à partir du {formatDate(windowOpen)} à {formatTime(windowOpen)}, soit 30 min avant le rendez-vous
              </p>
              <div className="flex items-center justify-center gap-3 mt-4 opacity-50">
                <button disabled className="flex items-center gap-2 px-4 py-2.5 bg-slate-200 text-slate-400 rounded-xl text-sm font-medium cursor-not-allowed">
                  <MapPinCheck className="w-4 h-4" /> Je suis arrivé
                </button>
                <button disabled className="flex items-center gap-2 px-4 py-2.5 bg-slate-200 text-slate-400 rounded-xl text-sm font-medium cursor-not-allowed">
                  <ScanLine className="w-4 h-4" /> Scanner un QR
                </button>
              </div>
            </div>
          )}

          {/* STATE: During window — ACTIVE */}
          {!isCheckedIn && isDuring && (
            <div data-testid="checkin-active">
              <div className="text-center mb-5">
                <p className="text-sm text-slate-600">
                  Fenêtre ouverte jusqu'à <span className="font-semibold">{formatTime(windowClose)}</span>
                </p>
              </div>

              {/* Primary action */}
              <button
                onClick={handleManualCheckin}
                disabled={checkingIn}
                className="w-full flex items-center justify-center gap-3 px-5 py-4 bg-emerald-600 text-white rounded-xl hover:bg-emerald-700 active:scale-[0.98] transition-all font-semibold text-base disabled:opacity-50 mb-3"
                data-testid="manual-checkin-btn"
              >
                {checkingIn ? <Loader2 className="w-5 h-5 animate-spin" /> : <MapPinCheck className="w-5 h-5" />}
                Je suis arrivé
              </button>

              {/* Secondary actions */}
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => setShowQRScanner(true)}
                  className="flex items-center justify-center gap-2 px-4 py-3 border-2 border-slate-200 text-slate-700 rounded-xl hover:bg-slate-50 hover:border-slate-300 active:scale-[0.98] transition-all font-medium text-sm"
                  data-testid="scan-qr-btn"
                >
                  <ScanLine className="w-4 h-4" />
                  Scanner un QR
                </button>
                <button
                  onClick={handleShowQR}
                  className="flex items-center justify-center gap-2 px-4 py-3 border-2 border-slate-200 text-slate-700 rounded-xl hover:bg-slate-50 hover:border-slate-300 active:scale-[0.98] transition-all font-medium text-sm"
                  data-testid="show-qr-btn"
                >
                  <QrCode className="w-4 h-4" />
                  Afficher mon QR
                </button>
              </div>

              <p className="text-xs text-slate-400 text-center mt-4">
                La position GPS sera capturée automatiquement si autorisée par votre navigateur.
              </p>
            </div>
          )}

          {/* STATE: After window (not checked in) */}
          {!isCheckedIn && isAfter && (
            <div className="text-center" data-testid="checkin-closed">
              <div className="w-14 h-14 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-3">
                <AlertTriangle className="w-7 h-7 text-red-400" />
              </div>
              <p className="font-medium text-slate-700 text-sm">La fenêtre de check-in est fermée</p>
              <p className="text-xs text-slate-500 mt-1">
                Elle était ouverte de {formatTime(windowOpen)} à {formatTime(windowClose)}
              </p>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 py-8 px-4" data-testid="invitation-page">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-slate-800 mb-2">NLYT</h1>
          <p className="text-slate-600">Rendez-vous avec engagement</p>
        </div>

        {/* Cancelled/Deleted Appointment Message */}
        {isAppointmentUnavailable && (
          <div className="bg-white rounded-2xl shadow-xl overflow-hidden mb-6" data-testid="appointment-unavailable">
            <div className={`px-6 py-4 ${isAppointmentCancelled ? 'bg-red-600' : 'bg-slate-600'} text-white text-center`}>
              <h2 className="text-xl font-semibold">
                {isAppointmentCancelled ? 'Ce rendez-vous a été annulé' : 'Ce rendez-vous n\'est plus disponible'}
              </h2>
            </div>
            <div className="p-6">
              <div className="text-center">
                <div className={`w-16 h-16 ${isAppointmentCancelled ? 'bg-red-100' : 'bg-slate-100'} rounded-full flex items-center justify-center mx-auto mb-4`}>
                  <Ban className={`w-8 h-8 ${isAppointmentCancelled ? 'text-red-600' : 'text-slate-600'}`} />
                </div>
                <h3 className="text-lg font-semibold text-slate-800 mb-2">{appointment.title}</h3>
                <p className="text-slate-600 mb-4">
                  {isAppointmentCancelled 
                    ? `L'organisateur (${organizer.name}) a annulé ce rendez-vous.`
                    : 'Ce rendez-vous a été supprimé par l\'organisateur.'}
                </p>
                <p className="text-sm text-slate-500">
                  <strong>Prévu le :</strong> {formatDateTimeFr(appointment.start_datetime)}
                </p>
                {appointment.location && (
                  <p className="text-sm text-slate-500">
                    <strong>Lieu :</strong> {appointment.location}
                  </p>
                )}
                <p className="text-slate-600 mt-4 font-medium">
                  Vous n'avez plus besoin de vous présenter à ce rendez-vous.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Main Card - Only show if appointment is still active */}
        {!isAppointmentUnavailable && (
        <div className="bg-white rounded-2xl shadow-xl overflow-hidden" data-testid="invitation-card">
          {/* Status Header */}
          <div className={`px-6 py-4 ${
            responseStatus === 'accepted' || responseStatus === 'accepted_guaranteed' ? 'bg-green-500' :
            responseStatus === 'accepted_pending_guarantee' ? 'bg-amber-500' :
            responseStatus === 'declined' ? 'bg-red-500' :
            responseStatus === 'cancelled_by_participant' ? 'bg-orange-500' :
            'bg-slate-800'
          } text-white`}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm opacity-90">Invitation de</p>
                <p className="text-xl font-semibold">{organizer.name}</p>
              </div>
              {getStatusBadge(responseStatus || participant.status)}
            </div>
          </div>

          {/* Guarantee Revalidation Banner */}
          {guaranteeRevalidation?.requires_revalidation && (responseStatus === 'accepted_guaranteed' || participant.status === 'accepted_guaranteed') && (
            <div className="p-5 bg-amber-50 border-b-2 border-amber-300" data-testid="guarantee-revalidation-banner">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 bg-amber-100 rounded-full flex items-center justify-center flex-shrink-0">
                  <AlertTriangle className="w-5 h-5 text-amber-600" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-amber-900 mb-1">Garantie à reconfirmer</h3>
                  <p className="text-sm text-amber-800 mb-3">
                    Les conditions du rendez-vous ont changé de manière significative. Veuillez reconfirmer votre garantie.
                  </p>
                  <div className="flex flex-wrap gap-2 mb-3">
                    {(guaranteeRevalidation.reason || '').split(', ').map((r, i) => {
                      let label = r;
                      if (r.includes('city_change')) label = 'Changement de ville';
                      else if (r.includes('date_shift')) label = 'Décalage de date > 24h';
                      else if (r.includes('type_change')) label = 'Changement de type';
                      return (
                        <span key={i} className="text-xs bg-amber-200 text-amber-900 px-2 py-1 rounded-full font-medium" data-testid={`revalidation-reason-${i}`}>
                          {label}
                        </span>
                      );
                    })}
                  </div>
                  <button
                    onClick={handleReconfirmGuarantee}
                    disabled={reconfirming}
                    className="inline-flex items-center gap-2 px-5 py-2.5 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors font-semibold text-sm disabled:opacity-50"
                    data-testid="reconfirm-guarantee-btn"
                  >
                    {reconfirming ? <Loader2 className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
                    Reconfirmer ma garantie
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Appointment Details */}
          <div className="p-6 border-b border-slate-100">
            <h2 className="text-2xl font-bold text-slate-800 mb-4" data-testid="appointment-title">
              {appointment.title}
            </h2>
            
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-slate-600">
                <Calendar className="w-5 h-5 text-slate-400" />
                <span data-testid="appointment-date">{formatDateTimeFr(appointment.start_datetime)}</span>
              </div>
              
              <div className="flex items-center gap-3 text-slate-600">
                <Clock className="w-5 h-5 text-slate-400" />
                <span>{appointment.duration_minutes} minutes</span>
              </div>
              
              <div className="flex items-center gap-3 text-slate-600">
                <MapPin className="w-5 h-5 text-slate-400" />
                <span data-testid="appointment-location">
                  {appointment.location || appointment.meeting_provider || 'Non spécifié'}
                </span>
              </div>
              
              {other_participants && other_participants.length > 0 && (
                <div className="flex items-start gap-3 text-slate-600">
                  <Users className="w-5 h-5 text-slate-400 mt-0.5" />
                  <div>
                    <span className="font-medium">{other_participants.length + 1} participants</span>
                    <div className="flex flex-wrap gap-2 mt-1">
                      {other_participants.map((p, idx) => (
                        <span 
                          key={idx} 
                          className={`text-xs px-2 py-1 rounded-full ${
                            ['accepted', 'accepted_guaranteed'].includes(p.status) ? 'bg-green-100 text-green-700' :
                            p.status === 'accepted_pending_guarantee' ? 'bg-amber-100 text-amber-700' :
                            p.status === 'declined' ? 'bg-red-100 text-red-700' :
                            'bg-slate-100 text-slate-600'
                          }`}
                        >
                          {p.name || 'Participant'}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Modification Proposal Banner (participant view) */}
          {activeProposal && activeProposal.status === 'pending' && (
            <div className="p-6 bg-blue-50 border-b-2 border-blue-300" data-testid="participant-proposal-banner">
              <div className="flex items-center gap-2 mb-3">
                <FileEdit className="w-5 h-5 text-blue-600" />
                <h3 className="font-semibold text-blue-900">Modification proposée</h3>
                <span className="text-xs bg-blue-200 text-blue-800 px-2 py-0.5 rounded-full ml-auto">
                  Par {activeProposal.proposed_by?.name || (activeProposal.proposed_by?.role === 'organizer' ? "l'organisateur" : 'un participant')}
                </span>
              </div>

              <div className="grid sm:grid-cols-2 gap-3 mb-4">
                {Object.entries(activeProposal.changes || {}).map(([field, newVal]) => {
                  const oldVal = activeProposal.original_values?.[field];
                  const labels = { start_datetime: 'Date/Heure', duration_minutes: 'Durée', location: 'Lieu', meeting_provider: 'Visio', appointment_type: 'Type' };
                  const fmtVal = (f, v) => {
                    if (f === 'start_datetime') return formatDateTimeFr(v);
                    if (f === 'duration_minutes') return `${v} min`;
                    if (f === 'appointment_type') return v === 'physical' ? 'En personne' : 'Visio';
                    return v || '—';
                  };
                  return (
                    <div key={field} className="bg-white rounded-lg p-3 border border-blue-200">
                      <p className="text-xs font-semibold text-slate-500 mb-1">{labels[field] || field}</p>
                      <p className="text-sm text-red-600 line-through">{fmtVal(field, oldVal)}</p>
                      <p className="text-sm text-emerald-700 font-semibold">{fmtVal(field, newVal)}</p>
                    </div>
                  );
                })}
              </div>

              {/* Show accept/reject only if this participant needs to respond */}
              {activeProposal.responses?.some(r => r.participant_id === participant.participant_id && r.status === 'pending') && (
                <div className="flex gap-3" data-testid="participant-respond-proposal">
                  <button
                    onClick={() => handleRespondToProposal('accept')}
                    disabled={respondingProposal}
                    className="flex-1 flex items-center justify-center gap-2 py-3 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 font-semibold transition-colors"
                    data-testid="accept-proposal-btn"
                  >
                    {respondingProposal ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                    Accepter
                  </button>
                  <button
                    onClick={() => handleRespondToProposal('reject')}
                    disabled={respondingProposal}
                    className="flex-1 flex items-center justify-center gap-2 py-3 bg-white text-red-600 border-2 border-red-300 rounded-lg hover:bg-red-50 disabled:opacity-50 font-semibold transition-colors"
                    data-testid="reject-proposal-btn"
                  >
                    <X className="w-4 h-4" /> Refuser
                  </button>
                </div>
              )}

              {/* Show if this participant already responded */}
              {activeProposal.responses?.some(r => r.participant_id === participant.participant_id && r.status === 'accepted') && (
                <p className="text-sm text-emerald-700 font-medium flex items-center gap-1">
                  <Check className="w-4 h-4" /> Vous avez accepté cette modification. En attente des autres participants.
                </p>
              )}

              <p className="text-xs text-slate-400 mt-3">Expire le {formatDateTimeFr(activeProposal.expires_at)}</p>
            </div>
          )}

          {/* Participant can propose a modification */}
          {['accepted', 'accepted_guaranteed', 'accepted_pending_guarantee', 'guaranteed'].includes(responseStatus || participant.status) && !activeProposal && !isAppointmentPast && (
            <div className="px-6 py-3 border-b border-slate-100">
              {!showProposeForm ? (
                <button
                  onClick={() => {
                    setProposalForm({
                      start_datetime: utcToLocalInput(appointment.start_datetime),
                      duration_minutes: String(appointment.duration_minutes || 60),
                      location: appointment.location || ''
                    });
                    setShowProposeForm(true);
                  }}
                  className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 transition-colors"
                  data-testid="participant-propose-btn"
                >
                  <Pencil className="w-4 h-4" /> Proposer une modification
                </button>
              ) : (
                <div className="space-y-3" data-testid="participant-proposal-form">
                  <h4 className="font-semibold text-slate-800 flex items-center gap-2">
                    <FileEdit className="w-4 h-4 text-blue-600" /> Proposer une modification
                  </h4>
                  <p className="text-xs text-slate-500">L'organisateur et les autres participants devront accepter.</p>
                  <div className="grid sm:grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-medium text-slate-600">Date et heure</label>
                      <input type="datetime-local" value={proposalForm.start_datetime}
                        min={(() => { const n=new Date(); return `${n.getFullYear()}-${String(n.getMonth()+1).padStart(2,'0')}-${String(n.getDate()).padStart(2,'0')}T${String(n.getHours()).padStart(2,'0')}:${String(n.getMinutes()).padStart(2,'0')}`; })()}
                        onChange={(e) => setProposalForm({...proposalForm, start_datetime: e.target.value})}
                        className="w-full mt-1 h-9 rounded-md border border-slate-300 px-2 text-sm"
                        data-testid="participant-proposal-datetime"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-slate-600">Durée (min)</label>
                      <input type="number" min="15" step="15" value={proposalForm.duration_minutes}
                        onChange={(e) => setProposalForm({...proposalForm, duration_minutes: e.target.value})}
                        className="w-full mt-1 h-9 rounded-md border border-slate-300 px-2 text-sm"
                        data-testid="participant-proposal-duration"
                      />
                    </div>
                    <div className="sm:col-span-2">
                      <label className="text-xs font-medium text-slate-600">Lieu</label>
                      <input type="text" value={proposalForm.location}
                        onChange={(e) => setProposalForm({...proposalForm, location: e.target.value})}
                        className="w-full mt-1 h-9 rounded-md border border-slate-300 px-2 text-sm"
                        data-testid="participant-proposal-location"
                      />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={handleSubmitParticipantProposal} disabled={submittingProposal}
                      className="flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 font-medium"
                      data-testid="participant-submit-proposal-btn"
                    >
                      {submittingProposal ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Envoyer
                    </button>
                    <button onClick={() => setShowProposeForm(false)}
                      className="px-4 py-2 bg-slate-100 text-slate-600 rounded-lg text-sm hover:bg-slate-200"
                    >Annuler</button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Engagement Rules */}
          <div className="p-6 bg-amber-50 border-b border-amber-100" data-testid="engagement-rules">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-6 h-6 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-semibold text-amber-800 mb-2">Règles d'engagement</h3>
                <ul className="space-y-2 text-sm text-amber-700">
                  <li>
                    <strong>Délai d'annulation :</strong> {engagement_rules.cancellation_deadline_hours}h avant le rendez-vous
                    {engagement_rules.cancellation_deadline_formatted && (
                      <span className="block text-xs mt-0.5">
                        (Limite : {engagement_rules.cancellation_deadline_formatted})
                      </span>
                    )}
                  </li>
                  {engagement_rules.tolerated_delay_minutes > 0 && (
                    <li>
                      <strong>Retard toléré :</strong> {engagement_rules.tolerated_delay_minutes} minutes
                    </li>
                  )}
                  <li>
                    <strong>Pénalité en cas d'absence :</strong> {engagement_rules.penalty_amount} {engagement_rules.penalty_currency}
                  </li>
                  <li>
                    <strong>Répartition :</strong> {engagement_rules.affected_compensation_percent}% aux participants affectés, {engagement_rules.platform_commission_percent}% commission plateforme
                    {engagement_rules.charity_percent > 0 && (
                      <>, {engagement_rules.charity_percent}% {engagement_rules.charity_association_name ? `pour ${engagement_rules.charity_association_name}` : 'pour une association'}</>
                    )}
                  </li>
                </ul>
              </div>
            </div>
          </div>

          {/* Response Section */}
          <div className="p-6" data-testid="response-section">
            {/* Guarantee message banner */}
            {guaranteeMessage && (
              <div className={`mb-4 p-4 rounded-lg ${
                guaranteeMessage.type === 'success' ? 'bg-green-50 border border-green-200 text-green-800' :
                guaranteeMessage.type === 'warning' ? 'bg-amber-50 border border-amber-200 text-amber-800' :
                'bg-blue-50 border border-blue-200 text-blue-800'
              }`}>
                <div className="flex items-center gap-2">
                  {guaranteeMessage.type === 'success' && <ShieldCheck className="w-5 h-5" />}
                  {guaranteeMessage.type === 'warning' && <AlertTriangle className="w-5 h-5" />}
                  {guaranteeMessage.type === 'info' && <Loader2 className="w-5 h-5 animate-spin" />}
                  <p className="font-medium">{guaranteeMessage.text}</p>
                </div>
              </div>
            )}
            
            {/* Accepted with guarantee */}
            {responseStatus === 'accepted_guaranteed' ? (
              <div className="text-center py-4">
                {guaranteeRevalidation?.requires_revalidation ? (
                  <>
                    <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
                      <AlertTriangle className="w-8 h-8 text-amber-600" />
                    </div>
                    <h3 className="text-xl font-semibold text-amber-800 mb-2" data-testid="guarantee-status-revalidation">Garantie à reconfirmer</h3>
                    <p className="text-slate-600">Votre garantie doit être reconfirmée suite à un changement majeur du rendez-vous.</p>
                    <p className="text-xs text-amber-600 mt-2">
                      Tant que vous n'avez pas reconfirmé, votre garantie est considérée comme partiellement invalide.
                    </p>
                  </>
                ) : (
                  <>
                    <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                      <ShieldCheck className="w-8 h-8 text-green-600" />
                    </div>
                    <h3 className="text-xl font-semibold text-green-800 mb-2" data-testid="guarantee-status-valid">Participation confirmée avec garantie !</h3>
                    <p className="text-slate-600">Votre moyen de paiement a été enregistré comme garantie.</p>
                    <p className="text-xs text-slate-500 mt-2">
                      Aucun montant ne sera prélevé sauf en cas d'absence ou de retard excessif.
                    </p>
                  </>
                )}
                {participant.guaranteed_at && !guaranteeRevalidation?.requires_revalidation && (
                  <p className="text-xs text-slate-400 mt-2">
                    Garanti le {formatActionDateFr(participant.guaranteed_at)}
                  </p>
                )}
                
                {/* Add to calendar button */}
                <div className="mt-6 pt-4 border-t border-slate-200">
                  <a
                    href={`${API_URL}/api/calendar/export/ics/${appointment.appointment_id}`}
                    download
                    className="inline-flex items-center gap-2 px-6 py-2 bg-slate-800 text-white rounded-lg hover:bg-slate-700 transition-colors font-medium"
                    data-testid="download-ics-btn"
                  >
                    <Download className="w-4 h-4" />
                    Ajouter au calendrier
                  </a>
                </div>
                
                {/* Cancel button if deadline not passed */}
                {engagement_rules.can_cancel && !engagement_rules.cancellation_deadline_passed && (
                  <div className="mt-6 pt-4 border-t border-slate-200">
                    <p className="text-sm text-slate-500 mb-3">
                      Vous pouvez annuler votre participation jusqu'au {engagement_rules.cancellation_deadline_formatted}
                    </p>
                    <button
                      onClick={handleCancelParticipation}
                      disabled={cancelling}
                      className="px-6 py-2 border-2 border-orange-300 text-orange-700 rounded-lg hover:bg-orange-50 transition-colors font-medium disabled:opacity-50 flex items-center gap-2 mx-auto"
                      data-testid="cancel-participation-btn"
                    >
                      {cancelling ? <Loader2 className="w-4 h-4 animate-spin" /> : <Ban className="w-4 h-4" />}
                      Annuler ma participation
                    </button>
                  </div>
                )}
              </div>
            ) : responseStatus === 'accepted_pending_guarantee' ? (
              <div className="text-center py-4">
                <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <CreditCard className="w-8 h-8 text-amber-600" />
                </div>
                <h3 className="text-xl font-semibold text-amber-800 mb-2">Garantie en attente</h3>
                <p className="text-slate-600 mb-4">
                  Vous avez accepté cette invitation mais la garantie financière n'est pas encore configurée.
                </p>
                <button
                  onClick={() => handleResponse('accept')}
                  disabled={responding}
                  className="px-8 py-3 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors font-medium disabled:opacity-50 flex items-center gap-2 mx-auto"
                  data-testid="complete-guarantee-btn"
                >
                  {responding ? <Loader2 className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
                  Compléter la garantie
                </button>
              </div>
            ) : responseStatus === 'accepted' ? (
              <div className="text-center py-4">
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Check className="w-8 h-8 text-green-600" />
                </div>
                <h3 className="text-xl font-semibold text-green-800 mb-2">Invitation acceptée !</h3>
                <p className="text-slate-600">Vous avez accepté cette invitation.</p>
                {participant.accepted_at && (
                  <p className="text-xs text-slate-400 mt-2">
                    Accepté le {formatActionDateFr(participant.accepted_at)}
                  </p>
                )}
                
                {/* Add to calendar button */}
                <div className="mt-6 pt-4 border-t border-slate-200">
                  <a
                    href={`${API_URL}/api/calendar/export/ics/${appointment.appointment_id}`}
                    download
                    className="inline-flex items-center gap-2 px-6 py-2 bg-slate-800 text-white rounded-lg hover:bg-slate-700 transition-colors font-medium"
                    data-testid="download-ics-btn"
                  >
                    <Download className="w-4 h-4" />
                    Ajouter au calendrier
                  </a>
                  <p className="text-xs text-slate-500 mt-2">
                    Téléchargez le fichier .ics pour l'ajouter à votre calendrier
                  </p>
                </div>
                
                {/* Cancel button if deadline not passed */}
                {engagement_rules.can_cancel && !engagement_rules.cancellation_deadline_passed && (
                  <div className="mt-6 pt-4 border-t border-slate-200">
                    <p className="text-sm text-slate-500 mb-3">
                      Vous pouvez annuler votre participation jusqu'au {engagement_rules.cancellation_deadline_formatted}
                    </p>
                    <button
                      onClick={handleCancelParticipation}
                      disabled={cancelling}
                      className="px-6 py-2 border-2 border-orange-300 text-orange-700 rounded-lg hover:bg-orange-50 transition-colors font-medium disabled:opacity-50 flex items-center gap-2 mx-auto"
                      data-testid="cancel-participation-btn"
                    >
                      {cancelling ? <Loader2 className="w-4 h-4 animate-spin" /> : <Ban className="w-4 h-4" />}
                      Annuler ma participation
                    </button>
                  </div>
                )}
                
                {/* Deadline passed message */}
                {responseStatus === 'accepted' && engagement_rules.cancellation_deadline_passed && (
                  <div className="mt-6 pt-4 border-t border-slate-200">
                    <p className="text-sm text-orange-600 bg-orange-50 px-4 py-2 rounded-lg">
                      Le délai d'annulation est dépassé. Vous ne pouvez plus annuler en ligne.
                    </p>
                  </div>
                )}
              </div>
            ) : responseStatus === 'declined' ? (
              <div className="text-center py-4">
                <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <X className="w-8 h-8 text-red-600" />
                </div>
                <h3 className="text-xl font-semibold text-red-800 mb-2">Invitation déclinée</h3>
                <p className="text-slate-600">Vous avez décliné cette invitation. L'organisateur en sera informé.</p>
                {participant.declined_at && (
                  <p className="text-xs text-slate-400 mt-2">
                    Décliné le {formatActionDateFr(participant.declined_at)}
                  </p>
                )}
              </div>
            ) : responseStatus === 'cancelled_by_participant' ? (
              <div className="text-center py-4">
                <div className="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Ban className="w-8 h-8 text-orange-600" />
                </div>
                <h3 className="text-xl font-semibold text-orange-800 mb-2">Participation annulée</h3>
                <p className="text-slate-600">Votre participation a bien été annulée. L'organisateur en sera informé.</p>
                {participant.cancelled_at && (
                  <p className="text-xs text-slate-400 mt-2">
                    Annulé le {formatActionDateFr(participant.cancelled_at)}
                  </p>
                )}
              </div>
            ) : (
              <div>
                <h3 className="font-semibold text-slate-800 mb-4 text-center">Votre réponse</h3>
                
                {/* Guarantee notice if penalty > 0 */}
                {engagement_rules.penalty_amount > 0 && (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                    <div className="flex items-start gap-3">
                      <CreditCard className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="font-medium text-blue-800">Garantie financière requise</p>
                        <p className="text-sm text-blue-700 mt-1">
                          Pour confirmer votre participation, vous devrez enregistrer un moyen de paiement.
                          <strong> Aucun montant ne sera prélevé immédiatement.</strong>
                        </p>
                        <p className="text-xs text-blue-600 mt-2">
                          La pénalité de {engagement_rules.penalty_amount} {engagement_rules.penalty_currency} ne sera prélevée 
                          qu'en cas d'absence ou de retard excessif.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
                
                <p className="text-sm text-slate-600 text-center mb-6">
                  En acceptant, vous vous engagez à respecter les règles ci-dessus. 
                  En cas de non-respect, la pénalité définie sera appliquée.
                </p>
                <div className="flex gap-4 justify-center">
                  <button
                    onClick={() => handleResponse('decline')}
                    disabled={responding}
                    className="px-8 py-3 border-2 border-slate-300 text-slate-700 rounded-xl hover:bg-slate-50 transition-colors font-medium disabled:opacity-50 flex items-center gap-2"
                    data-testid="decline-btn"
                  >
                    {responding ? <Loader2 className="w-5 h-5 animate-spin" /> : <X className="w-5 h-5" />}
                    Refuser
                  </button>
                  <button
                    onClick={() => handleResponse('accept')}
                    disabled={responding}
                    className="px-8 py-3 bg-green-600 text-white rounded-xl hover:bg-green-700 transition-colors font-medium disabled:opacity-50 flex items-center gap-2"
                    data-testid="accept-btn"
                  >
                    {responding ? <Loader2 className="w-5 h-5 animate-spin" /> : <Check className="w-5 h-5" />}
                    {engagement_rules.penalty_amount > 0 ? 'Accepter et configurer la garantie' : 'Accepter'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
        )}

        {/* CHECK-IN SECTION — Standalone prominent card */}
        {['accepted', 'accepted_guaranteed', 'accepted_pending_guarantee'].includes(responseStatus) && (
          renderCheckinSection()
        )}

        {/* Footer */}
        <div className="text-center mt-8 text-sm text-slate-500">
          <p>Besoin d'aide ? Contactez l'organisateur directement.</p>
          <p className="mt-2">© 2026 NLYT. Tous droits réservés.</p>
        </div>
      </div>

      {/* QR Scanner Modal */}
      {showQRScanner && (
        <QRCheckin
          appointmentId={appointment.appointment_id}
          invitationToken={token}
          onSuccess={handleQRScanSuccess}
          onClose={() => setShowQRScanner(false)}
        />
      )}

      {/* QR Display Modal */}
      {showQRDisplay && qrData && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" data-testid="qr-display-modal">
          <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
              <h3 className="text-lg font-semibold text-slate-800">Votre QR code</h3>
              <button onClick={handleCloseQR} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400" data-testid="qr-display-close">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 text-center">
              <div className="bg-white p-3 rounded-xl border border-slate-200 inline-block mb-4">
                <img src={`data:image/png;base64,${qrData.qr_image_base64}`} alt="QR Code" className="w-52 h-52" data-testid="qr-display-image" />
              </div>
              <p className="text-xs text-slate-500 mb-2">
                Montrez ce QR à un autre participant pour qu'il le scanne
              </p>
              <p className="text-xs font-mono bg-slate-50 px-3 py-2 rounded-lg text-slate-600 break-all select-all" data-testid="qr-display-token">
                {qrData.qr_token}
              </p>
              <p className="text-xs text-slate-400 mt-3">
                Renouvellement automatique toutes les {qrData.rotation_seconds}s
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
