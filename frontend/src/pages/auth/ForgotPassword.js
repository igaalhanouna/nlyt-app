import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { authAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      await authAPI.forgotPassword(email);
      toast.success('Email envoyé');
      setSent(true);
    } catch (error) {
      toast.error('Erreur lors de l\'envoi');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">NLYT</h1>
          <h2 className="text-2xl font-semibold text-slate-800 mb-2">Mot de passe oublié</h2>
          <p className="text-slate-600">Nous vous enverrons un lien de réinitialisation</p>
        </div>

        <div className="bg-white p-8 rounded-lg shadow-sm border border-slate-200">
          {sent ? (
            <div className="text-center">
              <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-md">
                <p className="text-emerald-800 font-medium">Email envoyé !</p>
                <p className="text-sm text-emerald-700 mt-2">
                  Vérifiez votre boîte mail pour réinitialiser votre mot de passe.
                </p>
              </div>
              <Link to="/signin">
                <Button variant="outline" className="w-full">Retour à la connexion</Button>
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  data-testid="forgot-email-input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="mt-1"
                />
              </div>

              <Button type="submit" className="w-full" disabled={loading} data-testid="forgot-submit-btn">
                {loading ? 'Envoi...' : 'Envoyer le lien'}
              </Button>

              <div className="text-center">
                <Link to="/signin" className="text-sm text-accent hover:underline">
                  Retour à la connexion
                </Link>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}