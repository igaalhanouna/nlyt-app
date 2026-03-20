import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { Calendar, MapPin, Clock, Users, AlertTriangle, Check, X, Loader2, Ban, Download, CreditCard, ShieldCheck } from 'lucide-react';

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
      
      // Check if already responded
      if (['accepted', 'accepted_guaranteed', 'accepted_pending_guarantee', 'declined', 'cancelled_by_participant'].includes(data.participant.status)) {
        setResponseStatus(data.participant.status);
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
    switch (status) {
      case 'accepted':
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
            <Check className="w-4 h-4" /> Accepté
          </span>
        );
      case 'declined':
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 bg-red-100 text-red-800 rounded-full text-sm font-medium">
            <X className="w-4 h-4" /> Refusé
          </span>
        );
      case 'cancelled_by_participant':
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 bg-orange-100 text-orange-800 rounded-full text-sm font-medium">
            <Ban className="w-4 h-4" /> Annulé
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-sm font-medium">
            <Clock className="w-4 h-4" /> En attente
          </span>
        );
    }
  };

  // Check if appointment is cancelled or deleted
  const isAppointmentCancelled = appointment.status === 'cancelled';
  const isAppointmentDeleted = appointment.status === 'deleted';
  const isAppointmentUnavailable = isAppointmentCancelled || isAppointmentDeleted;

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
                  <strong>Prévu le :</strong> {appointment.formatted_date || appointment.start_datetime}
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
            responseStatus === 'accepted' ? 'bg-green-500' :
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

          {/* Appointment Details */}
          <div className="p-6 border-b border-slate-100">
            <h2 className="text-2xl font-bold text-slate-800 mb-4" data-testid="appointment-title">
              {appointment.title}
            </h2>
            
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-slate-600">
                <Calendar className="w-5 h-5 text-slate-400" />
                <span data-testid="appointment-date">{appointment.formatted_date || appointment.start_datetime}</span>
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
                            p.status === 'accepted' ? 'bg-green-100 text-green-700' :
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
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <ShieldCheck className="w-8 h-8 text-green-600" />
                </div>
                <h3 className="text-xl font-semibold text-green-800 mb-2">Participation confirmée avec garantie !</h3>
                <p className="text-slate-600">Votre moyen de paiement a été enregistré comme garantie.</p>
                <p className="text-xs text-slate-500 mt-2">
                  Aucun montant ne sera prélevé sauf en cas d'absence ou de retard excessif.
                </p>
                {participant.guaranteed_at && (
                  <p className="text-xs text-slate-400 mt-2">
                    Garanti le {new Date(participant.guaranteed_at).toLocaleDateString('fr-FR', {
                      day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit'
                    })}
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
                    Accepté le {new Date(participant.accepted_at).toLocaleDateString('fr-FR', {
                      day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit'
                    })}
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
                    Décliné le {new Date(participant.declined_at).toLocaleDateString('fr-FR', {
                      day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit'
                    })}
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
                    Annulé le {new Date(participant.cancelled_at).toLocaleDateString('fr-FR', {
                      day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit'
                    })}
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

        {/* Footer */}
        <div className="text-center mt-8 text-sm text-slate-500">
          <p>Besoin d'aide ? Contactez l'organisateur directement.</p>
          <p className="mt-2">© 2026 NLYT. Tous droits réservés.</p>
        </div>
      </div>
    </div>
  );
}
