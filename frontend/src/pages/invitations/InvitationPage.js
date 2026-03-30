import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { Loader2, X } from 'lucide-react';
import QRCheckin from '../../components/QRCheckin';
import { toast } from 'sonner';
import { parseUTC, localInputToUTC } from '../../utils/dateFormat';
import { useAuth } from '../../contexts/AuthContext';
import { invitationAPI } from '../../services/api';
import { safeFetchJson } from '../../utils/safeFetchJson';

// Sub-components
import InvitationStatusBadge from './InvitationStatusBadge';
import AppointmentUnavailableCard from './AppointmentUnavailableCard';
import InvitationCardHeader from './InvitationCardHeader';
import GuaranteeRevalidationBanner from './GuaranteeRevalidationBanner';
import InvitationAppointmentDetails from './InvitationAppointmentDetails';
import ModificationProposalSection from './ModificationProposalSection';
import EngagementRulesCard from './EngagementRulesCard';
import InvitationResponseSection from './InvitationResponseSection';
import InvitationCheckinSection from './InvitationCheckinSection';
import QRDisplayModal from './QRDisplayModal';
import InvitationAccountChoice from './InvitationAccountChoice';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function InvitationPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user, loginWithToken } = useAuth();

  // Core state
  const [invitation, setInvitation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [responseStatus, setResponseStatus] = useState(null);

  // Action state
  const [responding, setResponding] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [reconfirming, setReconfirming] = useState(false);

  // Guarantee
  const [guaranteeMessage, setGuaranteeMessage] = useState(null);
  const [guaranteeRevalidation, setGuaranteeRevalidation] = useState(null);

  // Check-in
  const [checkinStatus, setCheckinStatus] = useState(null);
  const [checkingIn, setCheckingIn] = useState(false);
  const [showQRScanner, setShowQRScanner] = useState(false);
  const [showQRDisplay, setShowQRDisplay] = useState(false);
  const [qrData, setQrData] = useState(null);
  const [qrRefreshInterval, setQrRefreshInterval] = useState(null);

  // Modification proposals
  const [activeProposal, setActiveProposal] = useState(null);
  const [respondingProposal, setRespondingProposal] = useState(false);
  // Account choice step (intercalé avant Stripe)
  const [showAccountChoice, setShowAccountChoice] = useState(false);
  const [showProposeForm, setShowProposeForm] = useState(false);
  const [proposalForm, setProposalForm] = useState({ start_datetime: '', duration_minutes: '', location: '' });
  const [submittingProposal, setSubmittingProposal] = useState(false);

  // ─── Effects ───────────────────────────────────────────────

  useEffect(() => {
    const guaranteeStatus = searchParams.get('guarantee_status');
    const sessionId = searchParams.get('session_id');
    
    if (guaranteeStatus === 'success' && sessionId) {
      pollGuaranteeStatus(sessionId);
    } else if (guaranteeStatus === 'cancelled') {
      setGuaranteeMessage({
        type: 'warning',
        text: 'Vous avez annulé la configuration de la garantie. Votre participation n\'est pas encore confirmée.'
      });
    }
    
    fetchInvitation();
  }, [token]);

  // Scenario C: already logged-in user clicking an invitation link
  // Auto-link user_id and redirect to dashboard
  useEffect(() => {
    if (!user || !invitation) return;
    // Don't redirect if we're in the middle of guarantee polling
    const guaranteeStatus = searchParams.get('guarantee_status');
    if (guaranteeStatus) return;

    const participantEmail = (invitation.participant?.email || '').toLowerCase();
    const userEmail = (user.email || '').toLowerCase();
    if (participantEmail && userEmail && participantEmail === userEmail) {
      // Link user silently, then redirect
      invitationAPI.linkUser(token).catch(() => {});
      toast.success('Invitation retrouvée — direction votre dashboard');
      navigate('/dashboard');
    }
  }, [user, invitation]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── API Functions ─────────────────────────────────────────

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
      const text = await response.text();
      let data;
      try { data = JSON.parse(text); } catch { data = {}; }

      if (data.is_guaranteed) {
        setResponseStatus('accepted_guaranteed');
        setGuaranteeMessage({
          type: 'success',
          text: 'Garantie confirmée ! Votre participation est maintenant validée.'
        });
        // If user is logged in, redirect to dashboard after guarantee confirmation
        if (user) {
          toast.success('Garantie confirmée — direction votre dashboard');
          setTimeout(() => navigate('/dashboard'), 1500);
          return;
        }
        fetchInvitation();
        return;
      }

      setTimeout(() => pollGuaranteeStatus(sessionId, attempts + 1), pollInterval);
    } catch (error) {
      console.error('Error polling guarantee status:', error);
    }
  };

  const fetchInvitation = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/api/invitations/${token}`);
      const text = await response.text();
      let data;
      try { data = JSON.parse(text); } catch { throw new Error('Réponse invalide du serveur'); }

      if (!response.ok) {
        throw new Error(data.detail || 'Invitation non trouvée');
      }
      
      setInvitation(data);
      
      if (data.guarantee_revalidation?.requires_revalidation) {
        setGuaranteeRevalidation(data.guarantee_revalidation);
      } else {
        setGuaranteeRevalidation(null);
      }

      if (['accepted', 'accepted_guaranteed', 'accepted_pending_guarantee', 'declined', 'cancelled_by_participant'].includes(data.participant.status)) {
        setResponseStatus(data.participant.status);
      }

      if (data.appointment?.appointment_id) {
        try {
          const propRes = await fetch(`${API_URL}/api/modifications/active/${data.appointment.appointment_id}`);
          if (propRes.ok) {
            const text = await propRes.text();
            let propData;
            try { propData = JSON.parse(text); } catch { propData = {}; }
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
    // Intercept "accept" → show account choice BEFORE Stripe
    if (action === 'accept' && !showAccountChoice) {
      setShowAccountChoice(true);
      return;
    }
    try {
      setResponding(true);
      setError(null);
      
      const response = await fetch(`${API_URL}/api/invitations/${token}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
      
      const text = await response.text();
      let data;
      try { data = JSON.parse(text); } catch { data = {}; }

      if (!response.ok) {
        throw new Error(data.detail || 'Erreur lors de la réponse');
      }
      
      if (data.requires_guarantee && data.checkout_url) {
        setGuaranteeMessage({ type: 'info', text: 'Redirection vers la page de garantie...' });
        window.location.href = data.checkout_url;
        return;
      }

      if (data.reused_card) {
        setGuaranteeMessage({ type: 'success', text: data.message || 'Garantie confirmée avec votre carte enregistrée' });
      }
      
      setResponseStatus(data.status);
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

  // Called when user creates account/logs in from the choice panel
  const handleAccountSuccess = (data) => {
    // Save auth state via context
    if (data.access_token && data.user) {
      loginWithToken(data.access_token, data.user);
    }
    const label = data.is_new_account ? 'Compte créé' : 'Connexion réussie';
    toast.success(`${label} — retrouvez votre invitation sur le dashboard`);
    navigate('/dashboard');
  };

  // Called when user skips account creation
  const handleSkipAccount = async () => {
    setShowAccountChoice(false);
    // Proceed with original accept flow (guest mode) — bypass the intercept
    try {
      setResponding(true);
      setError(null);
      const response = await fetch(`${API_URL}/api/invitations/${token}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'accept' }),
      });
      const text = await response.text();
      let data;
      try { data = JSON.parse(text); } catch { data = {}; }
      if (!response.ok) throw new Error(data.detail || 'Erreur');
      if (data.requires_guarantee && data.checkout_url) {
        setGuaranteeMessage({ type: 'info', text: 'Redirection vers la page de garantie...' });
        window.location.href = data.checkout_url;
        return;
      }
      setResponseStatus(data.status);
      setInvitation(prev => ({
        ...prev,
        participant: { ...prev.participant, status: data.status },
      }));
    } catch (err) {
      setError(err.message);
    } finally {
      setResponding(false);
    }
  };

  const handleRespondToProposal = async (action) => {
    if (!activeProposal) return;
    setRespondingProposal(true);
    try {
      const res = await fetch(`${API_URL}/api/modifications/${activeProposal.proposal_id}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, invitation_token: token })
      });
      const text = await res.text();
      let data;
      try { data = JSON.parse(text); } catch { data = {}; }
      if (!res.ok) throw new Error(data.detail || 'Erreur');
      setActiveProposal(data.status === 'pending' ? data : null);
      if (data.status === 'accepted') fetchInvitation();
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
      const text = await res.text();
      let data;
      try { data = JSON.parse(text); } catch { data = {}; }
      if (!res.ok) throw new Error(data.detail || 'Erreur');
      setActiveProposal(data);
      setShowProposeForm(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmittingProposal(false);
    }
  };

  const handleReconfirmGuarantee = async () => {
    setReconfirming(true);
    try {
      const res = await fetch(`${API_URL}/api/invitations/${token}/reconfirm-guarantee`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const text = await res.text();
      let data;
      try { data = JSON.parse(text); } catch { data = {}; }
      if (!res.ok) throw new Error(data.detail || 'Erreur lors de la reconfirmation');
      if (data.checkout_url) window.location.href = data.checkout_url;
    } catch (err) {
      setError(err.message);
    } finally {
      setReconfirming(false);
    }
  };

  const handleCancelParticipation = async () => {
    try {
      setCancelling(true);
      const response = await fetch(`${API_URL}/api/invitations/${token}/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const text = await response.text();
      let data;
      try { data = JSON.parse(text); } catch { data = {}; }

      if (!response.ok) throw new Error(data.detail || 'Erreur lors de l\'annulation');
      
      setResponseStatus(data.status);
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

  // ─── Check-in Functions ────────────────────────────────────

  const loadCheckinStatus = useCallback(async () => {
    if (!invitation?.appointment?.appointment_id) return;
    try {
      const { ok, data } = await safeFetchJson(`${API_URL}/api/checkin/status/${invitation.appointment.appointment_id}?invitation_token=${token}`);
      if (ok) setCheckinStatus(data);
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

      if (navigator.geolocation) {
        try {
          const pos = await new Promise((resolve, reject) =>
            navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 8000, enableHighAccuracy: true })
          );
          payload.latitude = pos.coords.latitude;
          payload.longitude = pos.coords.longitude;
          payload.gps_consent = true;
        } catch (geoErr) {
          if (geoErr.code === 1) {
            toast.warning('Localisation refusée. Le check-in sera enregistré sans coordonnées GPS.');
          } else if (geoErr.code === 2) {
            toast.warning('Position GPS indisponible. Le check-in continuera sans coordonnées.');
          } else if (geoErr.code === 3) {
            toast.warning('Délai GPS dépassé. Le check-in continuera sans coordonnées.');
          }
        }
      }

      const { ok, data } = await safeFetchJson(`${API_URL}/api/checkin/manual`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!ok) {
        if (data.status === 409 || (data.detail && data.detail.includes('déjà'))) toast.info('Check-in déjà effectué. Votre présence est enregistrée.');
        else toast.error(data.detail || 'Erreur lors du check-in.');
      } else {
        toast.success('Présence enregistrée avec succès !');
      }
      loadCheckinStatus();
    } catch (e) {
      toast.error('Impossible de contacter le serveur. Vérifiez votre connexion internet et réessayez.');
    } finally {
      setCheckingIn(false);
    }
  };

  const handleShowQR = async () => {
    try {
      const { ok, data } = await safeFetchJson(`${API_URL}/api/checkin/qr/${invitation.appointment.appointment_id}?invitation_token=${token}`);
      if (ok) {
        setQrData(data);
        setShowQRDisplay(true);
        const interval = setInterval(async () => {
          try {
            const { ok: rOk, data: rData } = await safeFetchJson(`${API_URL}/api/checkin/qr/${invitation.appointment.appointment_id}?invitation_token=${token}`);
            if (rOk) setQrData(rData);
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

  // ─── Loading & Error States ────────────────────────────────

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

  // ─── Computed Values ───────────────────────────────────────

  const { participant, appointment, organizer, engagement_rules, other_participants } = invitation;

  const isAppointmentCancelled = appointment.status === 'cancelled';
  const isAppointmentDeleted = appointment.status === 'deleted';
  const isAppointmentUnavailable = isAppointmentCancelled || isAppointmentDeleted;
  const isAppointmentPast = (() => {
    const start = parseUTC(appointment.start_datetime);
    if (!start) return true;
    const end = new Date(start.getTime() + (appointment.duration_minutes || 60) * 60000);
    return new Date() > end;
  })();

  const effectiveStatus = responseStatus || participant.status;

  // ─── Render ────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 py-8 px-4" data-testid="invitation-page">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="mb-2">
            <a href="https://app.nlyt.io" target="_blank" rel="noopener noreferrer" className="inline-block">
              <span className="block text-lg font-bold tracking-[0.35em] text-slate-800">N<span className="text-slate-400">·</span>L<span className="text-slate-400">·</span>Y<span className="text-slate-400">·</span>T</span>
              <span className="block text-[10px] font-medium tracking-[0.25em] text-slate-400 uppercase">Never Lose Your Time</span>
            </a>
          </div>
          <p className="text-slate-600">Rendez-vous avec engagement solidaire</p>
        </div>

        {/* Cancelled/Deleted Appointment */}
        {isAppointmentUnavailable && (
          <AppointmentUnavailableCard
            appointment={appointment}
            organizer={organizer}
            isAppointmentCancelled={isAppointmentCancelled}
          />
        )}

        {/* Existing account banner (Phase 5 — Viral Loop) */}
        {!isAppointmentUnavailable && invitation?.has_existing_account && effectiveStatus === 'invited' && (
          <div
            data-testid="existing-account-banner"
            className="mb-4 bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 flex items-center justify-between gap-3 flex-wrap"
          >
            <p className="text-sm text-blue-800 font-medium">
              Vous avez déjà un compte NLYT — connectez-vous pour accepter plus vite.
            </p>
            <a
              href={`/signin?redirect=/invitation/${token}`}
              data-testid="existing-account-login-link"
              className="shrink-0 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 px-4 py-1.5 rounded-lg transition-colors"
            >
              Se connecter
            </a>
          </div>
        )}

        {/* Main Card */}
        {!isAppointmentUnavailable && (
          <div className="bg-white rounded-2xl shadow-xl overflow-hidden" data-testid="invitation-card">
            <InvitationCardHeader
              organizer={organizer}
              responseStatus={effectiveStatus}
              statusBadge={<InvitationStatusBadge status={effectiveStatus} guaranteeRevalidation={guaranteeRevalidation} />}
            />

            {guaranteeRevalidation?.requires_revalidation && (effectiveStatus === 'accepted_guaranteed') && (
              <GuaranteeRevalidationBanner
                guaranteeRevalidation={guaranteeRevalidation}
                onReconfirm={handleReconfirmGuarantee}
                reconfirming={reconfirming}
              />
            )}

            <InvitationAppointmentDetails
              appointment={appointment}
              otherParticipants={other_participants}
            />

            <ModificationProposalSection
              activeProposal={activeProposal}
              participant={participant}
              respondingProposal={respondingProposal}
              onRespondToProposal={handleRespondToProposal}
              appointment={appointment}
              responseStatus={responseStatus}
              isAppointmentPast={isAppointmentPast}
              showProposeForm={showProposeForm}
              setShowProposeForm={setShowProposeForm}
              proposalForm={proposalForm}
              setProposalForm={setProposalForm}
              submittingProposal={submittingProposal}
              onSubmitProposal={handleSubmitParticipantProposal}
            />

            <EngagementRulesCard engagementRules={engagement_rules} />

            {showAccountChoice ? (
              <InvitationAccountChoice
                participant={participant}
                token={token}
                hasExistingAccount={invitation?.has_existing_account}
                onSuccess={handleAccountSuccess}
                onSkip={handleSkipAccount}
              />
            ) : (
              <InvitationResponseSection
                responseStatus={responseStatus}
                participant={participant}
                engagementRules={engagement_rules}
                guaranteeRevalidation={guaranteeRevalidation}
                guaranteeMessage={guaranteeMessage}
                appointment={appointment}
                token={token}
                onResponse={handleResponse}
                responding={responding}
                onCancelParticipation={handleCancelParticipation}
                cancelling={cancelling}
                onReconfirmGuarantee={handleReconfirmGuarantee}
                reconfirming={reconfirming}
              />
            )}
          </div>
        )}

        {/* Check-in Section */}
        {['accepted', 'accepted_guaranteed', 'accepted_pending_guarantee'].includes(responseStatus) && (
          <InvitationCheckinSection
            appointment={appointment}
            participant={participant}
            responseStatus={responseStatus}
            engagementRules={engagement_rules}
            checkinStatus={checkinStatus}
            checkingIn={checkingIn}
            onManualCheckin={handleManualCheckin}
            onShowQR={handleShowQR}
            onOpenQRScanner={() => setShowQRScanner(true)}
            token={token}
          />
        )}

        {/* Footer */}
        <div className="text-center mt-8 text-sm text-slate-500">
          <p>Besoin d'aide ? Contactez l'organisateur directement.</p>
          <p className="mt-2">© 2026 N·L·Y·T — Never Lose Your Time. Tous droits réservés.</p>
          <a href="https://app.nlyt.io" target="_blank" rel="noopener noreferrer" className="inline-block mt-2 text-blue-600 hover:text-blue-800 font-medium">nlyt.io</a>
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
        <QRDisplayModal qrData={qrData} onClose={handleCloseQR} />
      )}
    </div>
  );
}
