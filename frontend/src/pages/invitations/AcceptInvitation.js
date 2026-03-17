import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { contractAPI, paymentAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { Checkbox } from '../../components/ui/checkbox';
import { CheckCircle, XCircle, Calendar, MapPin, Video, Clock, AlertCircle, CreditCard, Shield } from 'lucide-react';
import { toast } from 'sonner';

export default function AcceptInvitation() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [invitation, setInvitation] = useState(null);
  const [consentGiven, setConsentGiven] = useState(false);
  const [step, setStep] = useState('review'); // review, payment, success, error

  useEffect(() => {
    loadInvitation();
  }, [token]);

  const loadInvitation = async () => {
    try {
      const response = await contractAPI.getInvitation(token);
      setInvitation(response.data);
    } catch (error) {
      toast.error('Invitation introuvable ou expirée');
      setStep('error');
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = async () => {
    if (!consentGiven) {
      toast.error('Vous devez accepter les conditions d\'engagement');
      return;
    }

    setSubmitting(true);

    try {
      // Record acceptance
      const acceptanceData = {
        appointment_id: invitation.appointment.appointment_id,
        participant_id: invitation.participant.participant_id,
        ip_address: 'client_ip', // Would be captured server-side in production
        user_agent: navigator.userAgent,
        locale: navigator.language,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
      };

      await contractAPI.accept(acceptanceData);

      // Create payment guarantee
      const guaranteeResponse = await paymentAPI.createGuarantee(
        invitation.participant.participant_id,
        invitation.appointment.appointment_id
      );

      // Setup payment method
      const setupResponse = await paymentAPI.setupPaymentMethod(guaranteeResponse.data.guarantee_id);

      // Redirect to Stripe
      if (setupResponse.data.checkout_url) {
        window.location.href = setupResponse.data.checkout_url;
      } else {
        setStep('success');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Erreur lors de l\'acceptation');
      setSubmitting(false);
    }
  };

  const handleDecline = () => {
    toast.info('Invitation déclinée');
    navigate('/');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900"></div>
      </div>
    );
  }

  if (step === 'error') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4">
        <div className="bg-white p-8 rounded-lg border border-slate-200 max-w-md w-full text-center">
          <XCircle className="w-16 h-16 text-rose-600 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-slate-900 mb-2">Invitation invalide</h2>
          <p className="text-slate-600 mb-6">
            Cette invitation est introuvable ou a expiré.
          </p>
          <Button onClick={() => navigate('/')} className="w-full">
            Retour à l'accueil
          </Button>
        </div>
      </div>
    );
  }

  if (step === 'success') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4">
        <div className="bg-white p-8 rounded-lg border border-slate-200 max-w-md w-full text-center">
          <CheckCircle className="w-16 h-16 text-emerald-600 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-slate-900 mb-2">Invitation acceptée !</h2>
          <p className="text-slate-600 mb-6">
            Vous avez confirmé votre participation. Un email de confirmation vous a été envoyé.
          </p>
          <Button onClick={() => navigate('/')} className="w-full">
            Retour à l'accueil
          </Button>
        </div>
      </div>
    );
  }

  const { appointment, participant, policy_snapshot, organizer } = invitation;

  return (
    <div className="min-h-screen bg-background py-12 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">NLYT</h1>
          <p className="text-slate-600">Invitation à un rendez-vous avec engagement</p>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-8 mb-6" data-testid="invitation-card">
          <div className="flex items-start gap-4 mb-6 pb-6 border-b border-slate-200">
            <div className="p-3 bg-slate-100 rounded-lg">
              {appointment.appointment_type === 'physical' ? (
                <MapPin className="w-6 h-6 text-slate-700" />
              ) : (
                <Video className="w-6 h-6 text-slate-700" />
              )}
            </div>
            <div className="flex-1">
              <h2 className="text-2xl font-bold text-slate-900 mb-1">{appointment.title}</h2>
              <p className="text-slate-600">
                Organisé par {organizer.first_name} {organizer.last_name}
              </p>
            </div>
          </div>

          <div className="space-y-4 mb-6">
            <div className="flex items-start gap-3">
              <Calendar className="w-5 h-5 text-slate-500 mt-0.5" />
              <div>
                <p className="font-medium text-slate-900">Date et heure</p>
                <p className="text-slate-600">
                  {new Date(appointment.start_datetime).toLocaleString('fr-FR', {
                    dateStyle: 'full',
                    timeStyle: 'short'
                  })}
                </p>
                <p className="text-sm text-slate-500">Durée : {appointment.duration_minutes} minutes</p>
              </div>
            </div>

            {appointment.appointment_type === 'physical' && appointment.location && (
              <div className="flex items-start gap-3">
                <MapPin className="w-5 h-5 text-slate-500 mt-0.5" />
                <div>
                  <p className="font-medium text-slate-900">Lieu</p>
                  <p className="text-slate-600">{appointment.location}</p>
                </div>
              </div>
            )}

            {appointment.appointment_type === 'video' && appointment.meeting_provider && (
              <div className="flex items-start gap-3">
                <Video className="w-5 h-5 text-slate-500 mt-0.5" />
                <div>
                  <p className="font-medium text-slate-900">Plateforme</p>
                  <p className="text-slate-600">{appointment.meeting_provider}</p>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="bg-white rounded-lg border-t-4 border-slate-900 p-8 mb-6 shadow-sm">
          <h3 className="text-xl font-semibold text-slate-900 mb-4">
            Conditions d'engagement
          </h3>

          <div className="space-y-4 mb-6">
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
              <div className="flex items-start gap-3">
                <Clock className="w-5 h-5 text-amber-700 mt-0.5" />
                <div>
                  <p className="font-medium text-amber-900">Retard toléré</p>
                  <p className="text-sm text-amber-800">
                    Maximum {policy_snapshot.terms.tolerated_delay_minutes} minutes de retard autorisé
                  </p>
                </div>
              </div>
            </div>

            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-blue-700 mt-0.5" />
                <div>
                  <p className="font-medium text-blue-900">Délai d'annulation</p>
                  <p className="text-sm text-blue-800">
                    Annulation sans pénalité jusqu'à {policy_snapshot.terms.cancellation_deadline_hours} heures avant le rendez-vous
                  </p>
                </div>
              </div>
            </div>

            <div className="p-4 bg-rose-50 border border-rose-200 rounded-lg">
              <div className="flex items-start gap-3">
                <CreditCard className="w-5 h-5 text-rose-700 mt-0.5" />
                <div>
                  <p className="font-medium text-rose-900">Pénalité en cas d'absence ou retard excessif</p>
                  <p className="text-lg font-bold text-rose-900 mt-1">
                    {policy_snapshot.terms.penalty_amount} {policy_snapshot.terms.penalty_currency.toUpperCase()}
                  </p>
                  <p className="text-xs text-rose-800 mt-2">
                    Répartition : {policy_snapshot.terms.payout_split.affected_compensation_percent}% aux participants présents, 
                    {' '}{policy_snapshot.terms.payout_split.platform_commission_percent}% commission plateforme
                    {policy_snapshot.terms.payout_split.charity_percent > 0 && 
                      `, ${policy_snapshot.terms.payout_split.charity_percent}% don caritatif`}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
            <div className="flex items-start gap-3">
              <Shield className="w-5 h-5 text-slate-700 mt-0.5" />
              <div>
                <p className="font-medium text-slate-900 mb-2">Garantie de paiement</p>
                <p className="text-sm text-slate-600">
                  En acceptant cette invitation, vous devrez fournir un moyen de paiement. 
                  Aucun montant ne sera prélevé immédiatement. La garantie ne sera activée qu'en cas d'absence ou de retard excessif non justifié.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
          <div className="flex items-start gap-3">
            <Checkbox
              id="consent"
              checked={consentGiven}
              onCheckedChange={setConsentGiven}
              data-testid="consent-checkbox"
            />
            <label htmlFor="consent" className="text-sm text-slate-700 cursor-pointer">
              {policy_snapshot.consent_language.fr}
            </label>
          </div>
        </div>

        <div className="flex gap-4">
          <Button
            variant="outline"
            onClick={handleDecline}
            disabled={submitting}
            className="flex-1"
            data-testid="decline-btn"
          >
            Refuser
          </Button>
          <Button
            onClick={handleAccept}
            disabled={!consentGiven || submitting}
            className="flex-1"
            data-testid="accept-btn"
          >
            {submitting ? 'Traitement...' : 'Accepter et configurer le paiement'}
          </Button>
        </div>

        <p className="text-center text-xs text-slate-500 mt-6">
          En acceptant, vous créez un engagement juridiquement contraignant avec tous les participants.
        </p>
      </div>
    </div>
  );
}
