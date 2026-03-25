import React, { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import api from '../../services/api';
import { Button } from '../../components/ui/button';
import { CreditCard, Loader2, Trash2, CheckCircle, AlertTriangle, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import SettingsPageLayout from '../../components/SettingsPageLayout';

export default function PaymentSettings() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [paymentMethod, setPaymentMethod] = useState(null);
  const [hasPaymentMethod, setHasPaymentMethod] = useState(false);
  const [loading, setLoading] = useState(true);
  const [settingUp, setSettingUp] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [polling, setPolling] = useState(false);

  const fetchPaymentMethod = useCallback(async () => {
    try {
      const res = await api.get('/api/user-settings/me/payment-method');
      setHasPaymentMethod(res.data.has_payment_method);
      setPaymentMethod(res.data.payment_method || null);
    } catch {
      toast.error("Erreur lors du chargement du moyen de paiement");
    } finally {
      setLoading(false);
    }
  }, []);

  // Handle return from Stripe
  useEffect(() => {
    const setupStatus = searchParams.get('setup_status');
    const sessionId = searchParams.get('session_id');

    if (setupStatus === 'success' && sessionId) {
      setPolling(true);
      const pollSetup = async () => {
        try {
          const res = await api.get(`/api/user-settings/me/payment-method/check-setup?session_id=${sessionId}`);
          if (res.data.status === 'completed') {
            toast.success("Carte enregistrée avec succès");
            await fetchPaymentMethod();
            setPolling(false);
            setSearchParams({}, { replace: true });
          } else {
            // Retry after 2s
            setTimeout(pollSetup, 2000);
          }
        } catch {
          toast.error("Erreur lors de la vérification");
          setPolling(false);
        }
      };
      pollSetup();
    } else if (setupStatus === 'cancelled') {
      toast.info("Configuration annulée");
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams, fetchPaymentMethod]);

  useEffect(() => {
    fetchPaymentMethod();
  }, [fetchPaymentMethod]);

  const handleSetup = async () => {
    setSettingUp(true);
    try {
      const res = await api.post('/api/user-settings/me/setup-payment-method');
      if (res.data.checkout_url) {
        // Dev mode auto-save
        if (res.data.dev_mode) {
          toast.success("Carte de test enregistrée (mode dev)");
          await fetchPaymentMethod();
          setSettingUp(false);
          return;
        }
        window.location.href = res.data.checkout_url;
      }
    } catch {
      toast.error("Erreur lors de la configuration Stripe");
      setSettingUp(false);
    }
  };

  const handleRemove = async () => {
    if (!window.confirm("Supprimer votre carte par défaut ? Vos futurs engagements nécessiteront une saisie manuelle.")) return;
    setRemoving(true);
    try {
      await api.delete('/api/user-settings/me/payment-method');
      setHasPaymentMethod(false);
      setPaymentMethod(null);
      toast.success("Carte supprimée");
    } catch {
      toast.error("Erreur lors de la suppression");
    } finally {
      setRemoving(false);
    }
  };

  const brandIcons = {
    visa: "Visa",
    mastercard: "Mastercard",
    amex: "Amex",
    discover: "Discover",
  };

  if (loading || polling) {
    return (
      <SettingsPageLayout title="Paiement" description="Moyen de paiement pour vos garanties en tant qu'organisateur">
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
          <span className="ml-3 text-slate-500">{polling ? 'Vérification en cours...' : 'Chargement...'}</span>
        </div>
      </SettingsPageLayout>
    );
  }

  return (
    <SettingsPageLayout
      title="Paiement"
      description="Moyen de paiement pour vos garanties en tant qu'organisateur"
    >

        {hasPaymentMethod && paymentMethod ? (
          <div className="space-y-6">
            {/* Card display */}
            <div className="bg-white border border-slate-200 rounded-lg p-4 md:p-6" data-testid="saved-card-display">
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                <div className="flex items-center gap-3 md:gap-4">
                  <div className="w-14 h-10 bg-gradient-to-br from-slate-700 to-slate-900 rounded-md flex items-center justify-center flex-shrink-0">
                    <CreditCard className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <p className="font-semibold text-slate-900">
                      {brandIcons[paymentMethod.brand] || paymentMethod.brand?.toUpperCase()} •••• {paymentMethod.last4}
                    </p>
                    <p className="text-sm text-slate-500">Expire {paymentMethod.exp}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-emerald-500" />
                  <span className="text-xs text-emerald-600 font-medium">Active</span>
                </div>
              </div>
            </div>

            {/* Consent info */}
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 flex items-start gap-3" data-testid="consent-info">
              <ShieldCheck className="w-5 h-5 text-emerald-600 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-emerald-800">Utilisation automatique activée</p>
                <p className="text-xs text-emerald-700 mt-1">
                  Cette carte sera utilisée automatiquement pour couvrir votre garantie lorsque vous créez un engagement en tant qu'organisateur. Aucune ressaisie nécessaire.
                </p>
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-col sm:flex-row gap-2 sm:gap-3">
              <Button
                onClick={handleSetup}
                disabled={settingUp}
                variant="outline"
                data-testid="replace-card-btn"
                className="w-full sm:w-auto min-h-[44px] sm:min-h-0"
              >
                {settingUp ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <CreditCard className="w-4 h-4 mr-2" />}
                Remplacer la carte
              </Button>
              <Button
                onClick={handleRemove}
                disabled={removing}
                variant="outline"
                className="text-red-600 border-red-200 hover:bg-red-50 w-full sm:w-auto min-h-[44px] sm:min-h-0"
                data-testid="remove-card-btn"
              >
                {removing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Trash2 className="w-4 h-4 mr-2" />}
                Supprimer
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Empty state */}
            <div className="bg-white border border-slate-200 rounded-lg p-6 md:p-8 text-center" data-testid="no-card-display">
              <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <CreditCard className="w-8 h-8 text-slate-400" />
              </div>
              <h3 className="font-semibold text-slate-900 mb-2">Aucune carte enregistrée</h3>
              <p className="text-sm text-slate-500 mb-6 max-w-sm mx-auto">
                Enregistrez un moyen de paiement pour créer vos engagements instantanément, sans passer par Stripe à chaque fois.
              </p>
              <Button onClick={handleSetup} disabled={settingUp} data-testid="add-card-btn">
                {settingUp ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <CreditCard className="w-4 h-4 mr-2" />}
                Enregistrer une carte
              </Button>
            </div>

            {/* Info box */}
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-start gap-3" data-testid="no-card-warning">
              <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-amber-800">Sans carte par défaut</p>
                <p className="text-xs text-amber-700 mt-1">
                  Vous devrez passer par Stripe à chaque création d'engagement avec compensation. Les invitations ne seront envoyées qu'après validation de votre garantie.
                </p>
              </div>
            </div>
          </div>
        )}
    </SettingsPageLayout>
  );
}
