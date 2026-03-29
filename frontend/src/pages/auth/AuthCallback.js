import React, { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Unified OAuth callback handler.
 * - Google (Emergent Auth): session_id in URL hash fragment
 * - Microsoft: code in query params
 */
export default function AuthCallback() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const { loginWithToken } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processCallback = async () => {
      try {
        // Check for Google (Emergent Auth) session_id in hash
        const hash = location.hash || window.location.hash;
        const sessionIdMatch = hash.match(/session_id=([^&]+)/);

        if (sessionIdMatch) {
          const sessionId = sessionIdMatch[1];
          const resp = await fetch(`${API_URL}/api/auth/google/callback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId }),
          });
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.detail || 'Erreur Google OAuth');

          loginWithToken(data.access_token, data.user);
          toast.success(data.is_new_account ? 'Compte créé avec Google' : 'Connexion avec Google réussie');
          navigate('/dashboard', { replace: true });
          return;
        }

        // Check for Microsoft code in query params
        const code = searchParams.get('code');
        if (code) {
          const resp = await fetch(`${API_URL}/api/auth/microsoft/callback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code }),
          });
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.detail || 'Erreur Microsoft OAuth');

          loginWithToken(data.access_token, data.user);
          toast.success(data.is_new_account ? 'Compte créé avec Microsoft' : 'Connexion avec Microsoft réussie');
          navigate('/dashboard', { replace: true });
          return;
        }

        // Check for error/cancellation from provider
        const error = searchParams.get('error');
        if (error) {
          throw new Error('Connexion annulée');
        }

        // No recognizable callback data (user arrived here directly)
        throw new Error('Connexion annulée');
      } catch (err) {
        console.error('[AuthCallback] Error:', err);
        toast.error(err.message || 'Erreur d\'authentification');
        navigate('/signin', { replace: true });
      }
    };

    processCallback();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900 mx-auto mb-4" />
        <p className="text-slate-600">Authentification en cours...</p>
      </div>
    </div>
  );
}
