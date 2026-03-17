import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Mail, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL;

export default function ResendVerification() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('idle'); // idle, success, error, already_verified
  const [message, setMessage] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!email) {
      setMessage('Veuillez entrer votre adresse email');
      setStatus('error');
      return;
    }

    setLoading(true);
    setStatus('idle');

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/auth/resend-verification`,
        { email },
        { headers: { 'Content-Type': 'application/json' } }
      );

      setMessage(response.data.message);
      
      if (response.data.already_verified) {
        setStatus('already_verified');
      } else {
        setStatus('success');
      }
    } catch (error) {
      console.error('Resend verification error:', error);
      
      let errorMessage = 'Une erreur est survenue. Veuillez réessayer.';
      
      if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error.response?.data?.error) {
        errorMessage = error.response.data.error;
      }
      
      setMessage(errorMessage);
      setStatus('error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">NLYT</h1>
          <h2 className="text-2xl font-semibold text-slate-800 mb-2">
            Renvoyer l'email de vérification
          </h2>
          <p className="text-slate-600">
            Entrez votre adresse email pour recevoir un nouveau lien de vérification
          </p>
        </div>

        <div className="bg-white p-8 rounded-lg shadow-sm border border-slate-200">
          {status === 'success' && (
            <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-lg" data-testid="resend-success">
              <div className="flex items-start gap-3">
                <CheckCircle className="w-5 h-5 text-emerald-600 mt-0.5" />
                <div>
                  <p className="font-medium text-emerald-900">Email envoyé !</p>
                  <p className="text-sm text-emerald-800 mt-1">{message}</p>
                </div>
              </div>
            </div>
          )}

          {status === 'already_verified' && (
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg" data-testid="resend-already-verified">
              <div className="flex items-start gap-3">
                <CheckCircle className="w-5 h-5 text-blue-600 mt-0.5" />
                <div>
                  <p className="font-medium text-blue-900">Compte déjà vérifié</p>
                  <p className="text-sm text-blue-800 mt-1">{message}</p>
                </div>
              </div>
            </div>
          )}

          {status === 'error' && (
            <div className="mb-6 p-4 bg-rose-50 border border-rose-200 rounded-lg" data-testid="resend-error">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-rose-600 mt-0.5" />
                <div>
                  <p className="font-medium text-rose-900">Erreur</p>
                  <p className="text-sm text-rose-800 mt-1">{message}</p>
                </div>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <Label htmlFor="email">Adresse email</Label>
              <Input
                id="email"
                type="email"
                data-testid="resend-email-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="votre.email@exemple.com"
                required
                disabled={loading || status === 'success'}
                className="mt-1"
              />
            </div>

            {status !== 'success' && status !== 'already_verified' && (
              <Button 
                type="submit" 
                className="w-full" 
                disabled={loading}
                data-testid="resend-submit-btn"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Envoi en cours...
                  </>
                ) : (
                  <>
                    <Mail className="w-4 h-4 mr-2" />
                    Renvoyer l'email
                  </>
                )}
              </Button>
            )}

            {(status === 'success' || status === 'already_verified') && (
              <Link to="/signin">
                <Button className="w-full" data-testid="resend-goto-signin">
                  Aller à la connexion
                </Button>
              </Link>
            )}
          </form>

          <div className="mt-6 text-center text-sm text-slate-600">
            Vous vous souvenez de vos identifiants ?{' '}
            <Link to="/signin" className="text-accent hover:underline font-medium">
              Se connecter
            </Link>
          </div>
        </div>

        <div className="mt-6 p-4 bg-slate-50 rounded-lg text-sm text-slate-600">
          <p className="font-medium mb-2">Conseils :</p>
          <ul className="list-disc list-inside space-y-1 text-xs">
            <li>Vérifiez votre dossier spam/courrier indésirable</li>
            <li>Attendez quelques minutes entre chaque demande</li>
            <li>Assurez-vous d'utiliser la bonne adresse email</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
