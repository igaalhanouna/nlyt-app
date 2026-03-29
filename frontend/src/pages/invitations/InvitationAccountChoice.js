import React, { useState } from 'react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Loader2, Check, User, KeyRound } from 'lucide-react';
import { invitationAPI } from '../../services/api';
import { toast } from 'sonner';

export default function InvitationAccountChoice({
  participant,
  token,
  hasExistingAccount,
  onSuccess,
  onSkip,
}) {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [showForgotPassword, setShowForgotPassword] = useState(false);

  const { first_name, last_name, email } = participant;
  const isExisting = hasExistingAccount;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!password || password.length < 6) {
      toast.error('Le mot de passe doit contenir au moins 6 caractères');
      return;
    }
    setLoading(true);
    try {
      const res = await invitationAPI.linkAccount(token, password);
      const data = res.data;
      onSuccess(data);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Erreur lors de la création du compte';
      toast.error(msg);
      if (msg.includes('Mot de passe incorrect')) {
        setShowForgotPassword(true);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = () => {
    window.open(`/forgot-password?email=${encodeURIComponent(email)}`, '_blank');
  };

  return (
    <div className="space-y-4" data-testid="invitation-account-choice">
      <div className="bg-white border-2 border-emerald-200 rounded-xl p-6 shadow-sm" data-testid="account-option-create">
        {!isExisting && (
          <span className="inline-block text-[11px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded mb-3">
            Recommandé
          </span>
        )}

        <h3 className="text-lg font-semibold text-slate-900 mb-1">
          {isExisting ? 'Connectez-vous pour accepter' : 'Votre espace est prêt'}
        </h3>
        <p className="text-sm text-slate-500 mb-4">
          {isExisting
            ? 'Cet engagement sera ajouté à votre espace NLYT.'
            : 'Il ne vous reste qu\'à choisir un mot de passe.'}
        </p>

        <div className="flex items-center gap-3 bg-slate-50 rounded-lg px-4 py-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
            <User className="w-5 h-5 text-emerald-600" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-slate-900 truncate" data-testid="account-display-name">
              {first_name} {last_name}
            </p>
            <p className="text-xs text-slate-500 truncate" data-testid="account-display-email">
              {email}
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <Label htmlFor="account-password" className="text-sm font-medium text-slate-700">
              {isExisting ? 'Mot de passe' : 'Choisissez un mot de passe'}
            </Label>
            <div className="relative mt-1">
              <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                id="account-password" type="password" autoFocus
                placeholder={isExisting ? 'Votre mot de passe' : 'Minimum 6 caractères'}
                value={password} onChange={(e) => setPassword(e.target.value)}
                className="pl-10"
                data-testid="account-password-input"
              />
            </div>
          </div>

          {isExisting && showForgotPassword && (
            <button type="button" onClick={handleForgotPassword}
              className="text-xs text-blue-600 hover:text-blue-800 underline"
              data-testid="forgot-password-link">
              Mot de passe oublié ?
            </button>
          )}

          {isExisting && !showForgotPassword && (
            <button type="button" onClick={() => setShowForgotPassword(true)}
              className="text-xs text-slate-400 hover:text-slate-600"
              data-testid="show-forgot-password">
              Mot de passe oublié ?
            </button>
          )}

          {!isExisting && (
            <div className="space-y-1.5 pt-1">
              <div className="flex items-start gap-2 text-xs text-slate-600">
                <Check className="w-3.5 h-3.5 text-emerald-500 mt-0.5 flex-shrink-0" />
                <span>Votre carte sera sauvegardée — plus de double saisie</span>
              </div>
              <div className="flex items-start gap-2 text-xs text-slate-600">
                <Check className="w-3.5 h-3.5 text-emerald-500 mt-0.5 flex-shrink-0" />
                <span>Suivez vos engagements dans votre espace</span>
              </div>
              <div className="flex items-start gap-2 text-xs text-slate-600">
                <Check className="w-3.5 h-3.5 text-emerald-500 mt-0.5 flex-shrink-0" />
                <span>Accédez à votre wallet et vos compensations</span>
              </div>
            </div>
          )}

          <Button type="submit" className="w-full" disabled={loading} data-testid="account-submit-btn">
            {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
            {isExisting ? 'Se connecter et accepter' : 'Créer mon espace et continuer'}
          </Button>
        </form>
      </div>

      <div className="text-center">
        <button onClick={onSkip}
          className="text-sm text-slate-400 hover:text-slate-600 transition-colors"
          data-testid="skip-account-link">
          Continuer sans compte &rarr;
        </button>
      </div>
    </div>
  );
}
