import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';

export default function ResetPassword() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (password !== confirmPassword) {
      toast.error('Les mots de passe ne correspondent pas');
      return;
    }

    setLoading(true);

    try {
      await authAPI.resetPassword(token, password);
      toast.success('Mot de passe réinitialisé');
      navigate('/signin');
    } catch (error) {
      toast.error('Erreur lors de la réinitialisation');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="mb-2">
            <span className="block text-lg font-bold tracking-[0.35em] text-slate-900">N<span className="text-slate-400">·</span>L<span className="text-slate-400">·</span>Y<span className="text-slate-400">·</span>T</span>
            <span className="block text-[10px] font-medium tracking-[0.25em] text-slate-400 uppercase">Never Lose Your Time</span>
          </div>
          <h2 className="text-2xl font-semibold text-slate-800 mb-2">Nouveau mot de passe</h2>
          <p className="text-slate-600">Choisissez un nouveau mot de passe</p>
        </div>

        <div className="bg-white p-8 rounded-lg shadow-sm border border-slate-200">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <Label htmlFor="password">Nouveau mot de passe</Label>
              <Input
                id="password"
                type="password"
                data-testid="reset-password-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="mt-1"
              />
            </div>

            <div>
              <Label htmlFor="confirmPassword">Confirmer le mot de passe</Label>
              <Input
                id="confirmPassword"
                type="password"
                data-testid="reset-confirm-password-input"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className="mt-1"
              />
            </div>

            <Button type="submit" className="w-full" disabled={loading} data-testid="reset-submit-btn">
              {loading ? 'Réinitialisation...' : 'Réinitialiser le mot de passe'}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}