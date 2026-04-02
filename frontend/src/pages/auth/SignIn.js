import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { AlertCircle, Mail } from 'lucide-react';
import { toast } from 'sonner';
import OAuthButtons from './OAuthButtons';

export default function SignIn() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const redirectTo = searchParams.get('redirect');
  const { login } = useAuth();
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  });
  const [loading, setLoading] = useState(false);
  const [notVerifiedEmail, setNotVerifiedEmail] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMessage(null);

    try {
      await login(formData.email, formData.password);
      setNotVerifiedEmail(null);
      toast.success('Connexion réussie');
      navigate(redirectTo || '/dashboard');
    } catch (error) {
      const errorData = error.response?.data;
      const errorType = typeof errorData?.detail === 'object' ? errorData.detail.error : errorData?.detail;
      
      if (errorType === 'not_verified' || errorData?.error === 'not_verified') {
        setNotVerifiedEmail(formData.email);
      } else {
        setNotVerifiedEmail(null);
        const msg = (typeof errorData?.detail === 'string' ? errorData.detail : null) || errorData?.message || 'Erreur de connexion';
        setErrorMessage(msg);
        toast.error(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleResendVerification = () => {
    navigate('/resend-verification', { state: { email: notVerifiedEmail } });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="mb-2">
            <Link to="/" className="inline-block" data-testid="auth-logo-link">
              <span className="block text-lg font-bold tracking-[0.35em] text-slate-900">N<span className="text-slate-400">·</span>L<span className="text-slate-400">·</span>Y<span className="text-slate-400">·</span>T</span>
              <span className="block text-[10px] font-medium tracking-[0.25em] text-slate-400 uppercase">Never Lose Your Time</span>
            </Link>
          </div>
          <h2 className="text-2xl font-semibold text-slate-800 mb-2">Connexion</h2>
          <p className="text-slate-600">Accédez à votre espace d'engagements solidaires</p>
        </div>

        <div className="bg-white p-8 rounded-lg shadow-sm border border-slate-200">
          {notVerifiedEmail && (
            <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-lg" data-testid="not-verified-alert">
              <div className="flex items-start gap-3 mb-3">
                <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5" />
                <div>
                  <p className="font-medium text-amber-900">Email non vérifié</p>
                  <p className="text-sm text-amber-800 mt-1">
                    Votre compte existe mais votre email n'a pas encore été vérifié. 
                    Veuillez vérifier votre boîte mail ou demander un nouvel email.
                  </p>
                </div>
              </div>
              <Button
                onClick={handleResendVerification}
                variant="outline"
                size="sm"
                className="w-full border-amber-300 hover:bg-amber-100"
                data-testid="resend-from-signin-btn"
              >
                <Mail className="w-4 h-4 mr-2" />
                Renvoyer l'email de vérification
              </Button>
            </div>
          )}

          <OAuthButtons loading={loading} />

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-slate-200" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-white px-3 text-slate-400 font-medium">ou continuer avec email</span>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {errorMessage && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2" data-testid="login-error-message">
                <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
                <p className="text-sm text-red-800">{errorMessage}</p>
              </div>
            )}
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                data-testid="signin-email-input"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                required
                className="mt-1 h-11 sm:h-9"
              />
            </div>

            <div>
              <Label htmlFor="password">Mot de passe</Label>
              <Input
                id="password"
                type="password"
                data-testid="signin-password-input"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                required
                className="mt-1 h-11 sm:h-9"
              />
            </div>

            <div className="text-right">
              <Link to="/forgot-password" className="inline-flex items-center min-h-[44px] sm:min-h-0 text-sm text-blue-600 hover:text-blue-800 hover:underline font-medium" data-testid="forgot-password-link">
                Mot de passe oublié ?
              </Link>
            </div>

            <Button type="submit" className="w-full min-h-[44px] sm:min-h-0" disabled={loading} data-testid="signin-submit-btn">
              {loading ? 'Connexion...' : 'Se connecter'}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm text-slate-600">
            Pas encore de compte ?{' '}
            <Link to={redirectTo ? `/signup?redirect=${encodeURIComponent(redirectTo)}` : '/signup'} className="inline-flex items-center min-h-[44px] sm:min-h-0 text-blue-600 hover:text-blue-800 hover:underline font-semibold">
              Créer un compte
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
