import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { AlertCircle, Mail } from 'lucide-react';
import { toast } from 'sonner';

export default function SignUp() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    phone: ''
  });
  const [loading, setLoading] = useState(false);
  const [unverifiedEmail, setUnverifiedEmail] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setUnverifiedEmail(null);

    try {
      const result = await register(formData);
      
      // Check if error is "not_verified" (existing unverified account)
      if (result?.error === 'not_verified') {
        setUnverifiedEmail(formData.email);
        return;
      }
      
      toast.success('Compte créé ! Vérifiez votre email.');
      navigate('/signin');
    } catch (error) {
      const errorData = error.response?.data;
      
      // Check if it's an existing unverified account
      if (errorData?.error === 'not_verified') {
        setUnverifiedEmail(formData.email);
        toast.error(errorData.message || 'Ce compte existe mais n\'est pas vérifié');
      } else {
        toast.error(errorData?.detail || errorData?.error || 'Erreur lors de l\'inscription');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleResendVerification = () => {
    navigate('/resend-verification', { state: { email: unverifiedEmail } });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="mb-2">
            <span className="block text-lg font-bold tracking-[0.35em] text-slate-900">N<span className="text-slate-400">·</span>L<span className="text-slate-400">·</span>Y<span className="text-slate-400">·</span>T</span>
            <span className="block text-[10px] font-medium tracking-[0.25em] text-slate-400 uppercase">Never Lose Your Time</span>
          </div>
          <h2 className="text-2xl font-semibold text-slate-800 mb-2">Créer un compte</h2>
          <p className="text-slate-600">Commencez à créer vos engagements solidaires</p>
        </div>

        <div className="bg-white p-8 rounded-lg shadow-sm border border-slate-200">
          {unverifiedEmail && (
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg" data-testid="unverified-account-alert">
              <div className="flex items-start gap-3 mb-3">
                <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5" />
                <div>
                  <p className="font-medium text-blue-900">Compte existant non vérifié</p>
                  <p className="text-sm text-blue-800 mt-1">
                    Un compte existe avec <strong>{unverifiedEmail}</strong> mais n'est pas encore vérifié. 
                    Vérifiez vos emails ou demandez un nouvel email de vérification.
                  </p>
                </div>
              </div>
              <Button
                onClick={handleResendVerification}
                variant="outline"
                size="sm"
                className="w-full border-blue-300 hover:bg-blue-100"
                data-testid="resend-from-signup-btn"
              >
                <Mail className="w-4 h-4 mr-2" />
                Renvoyer l'email de vérification
              </Button>
              <div className="mt-3 text-center">
                <Link to="/signin" className="text-sm text-blue-700 hover:underline">
                  Retour à la connexion
                </Link>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="first_name">Prénom</Label>
                <Input
                  id="first_name"
                  data-testid="signup-firstname-input"
                  value={formData.first_name}
                  onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                  required
                  disabled={!!unverifiedEmail}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="last_name">Nom</Label>
                <Input
                  id="last_name"
                  data-testid="signup-lastname-input"
                  value={formData.last_name}
                  onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                  required
                  disabled={!!unverifiedEmail}
                  className="mt-1"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                data-testid="signup-email-input"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                required
                disabled={!!unverifiedEmail}
                className="mt-1"
              />
            </div>

            <div>
              <Label htmlFor="phone">Téléphone (optionnel)</Label>
              <Input
                id="phone"
                type="tel"
                data-testid="signup-phone-input"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                disabled={!!unverifiedEmail}
                className="mt-1"
              />
            </div>

            <div>
              <Label htmlFor="password">Mot de passe</Label>
              <Input
                id="password"
                type="password"
                data-testid="signup-password-input"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                required
                disabled={!!unverifiedEmail}
                className="mt-1"
              />
            </div>

            {!unverifiedEmail && (
              <Button type="submit" className="w-full" disabled={loading} data-testid="signup-submit-btn">
                {loading ? 'Création...' : 'Créer mon compte'}
              </Button>
            )}
          </form>

          <div className="mt-6 text-center text-sm text-slate-600">
            Déjà un compte ?{' '}
            <Link to="/signin" className="text-blue-600 hover:text-blue-800 hover:underline font-semibold">
              Se connecter
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
