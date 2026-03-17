import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../../components/ui/button';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL;

export default function VerifyEmail() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  
  const [status, setStatus] = useState('loading');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    if (!token) {
      console.error('No verification token provided');
      setStatus('error');
      setErrorMessage('Token de vérification manquant');
      return;
    }
    verifyEmail();
  }, [token]);

  const verifyEmail = async () => {
    try {
      console.log('Starting email verification with token:', token);
      
      // Make a direct axios call without authentication headers
      const response = await axios.get(
        `${API_BASE_URL}/api/auth/verify-email?token=${token}`,
        {
          headers: {
            'Content-Type': 'application/json'
          }
        }
      );
      
      console.log('Verification successful:', response.data);
      setStatus('success');
      
      // Redirect to signin after 2 seconds
      setTimeout(() => {
        navigate('/signin');
      }, 2000);
      
    } catch (error) {
      console.error('Email verification failed:', error);
      
      let message = 'Une erreur est survenue lors de la vérification';
      
      if (error.response) {
        console.error('Error response:', error.response.data);
        message = error.response.data.detail || message;
        
        if (error.response.status === 400) {
          message = 'Token invalide ou expiré';
        } else if (error.response.status === 404) {
          message = 'Utilisateur introuvable';
        }
      } else if (error.request) {
        console.error('No response received:', error.request);
        message = 'Impossible de contacter le serveur';
      } else {
        console.error('Error setting up request:', error.message);
      }
      
      setErrorMessage(message);
      setStatus('error');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">NLYT</h1>
          <h2 className="text-xl font-semibold text-slate-800">Vérification d'email</h2>
        </div>

        <div className="bg-white p-8 rounded-lg shadow-sm border border-slate-200 text-center">
          {status === 'loading' && (
            <div data-testid="verify-loading">
              <Loader2 className="w-16 h-16 text-slate-900 mx-auto mb-4 animate-spin" />
              <h2 className="text-2xl font-semibold text-slate-900 mb-2">Vérification en cours...</h2>
              <p className="text-slate-600">Veuillez patienter</p>
            </div>
          )}

          {status === 'success' && (
            <div data-testid="verify-success">
              <CheckCircle className="w-16 h-16 text-emerald-600 mx-auto mb-4" />
              <h2 className="text-2xl font-semibold text-slate-900 mb-2">Email vérifié !</h2>
              <p className="text-slate-600 mb-6">Votre compte est maintenant activé. Redirection vers la connexion...</p>
              <Link to="/signin">
                <Button className="w-full" data-testid="verify-signin-btn">Se connecter</Button>
              </Link>
            </div>
          )}

          {status === 'error' && (
            <div data-testid="verify-error">
              <XCircle className="w-16 h-16 text-rose-600 mx-auto mb-4" />
              <h2 className="text-2xl font-semibold text-slate-900 mb-2">Échec de vérification</h2>
              <p className="text-slate-600 mb-2">{errorMessage}</p>
              <p className="text-sm text-slate-500 mb-6">
                Le lien a peut-être expiré. Veuillez vous inscrire à nouveau ou contacter le support.
              </p>
              <div className="space-y-3">
                <Link to="/signin">
                  <Button variant="outline" className="w-full">Aller à la connexion</Button>
                </Link>
                <Link to="/signup">
                  <Button variant="ghost" className="w-full">Créer un nouveau compte</Button>
                </Link>
              </div>
            </div>
          )}
        </div>
        
        {status === 'error' && token && (
          <div className="mt-4 p-3 bg-slate-50 rounded text-xs text-slate-500 font-mono break-all">
            Debug: Token = {token.substring(0, 20)}...
          </div>
        )}
      </div>
    </div>
  );
}