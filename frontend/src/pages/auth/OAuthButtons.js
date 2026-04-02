import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { safeFetchJson } from '../../utils/safeFetchJson';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
function handleGoogleLogin(redirectAfterAuth) {
  // Store redirect target for after OAuth callback
  if (redirectAfterAuth) {
    localStorage.setItem('nlyt_auth_redirect', redirectAfterAuth);
  }
  const redirectUrl = window.location.origin + '/auth/callback';
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
}

export default function OAuthButtons({ loading: parentLoading }) {
  const [msLoading, setMsLoading] = useState(false);
  const [searchParams] = useSearchParams();
  const redirectTo = searchParams.get('redirect');

  const handleMicrosoftLogin = async () => {
    // Store redirect target for after OAuth callback
    if (redirectTo) {
      localStorage.setItem('nlyt_auth_redirect', redirectTo);
    }
    setMsLoading(true);
    try {
      const { ok, data } = await safeFetchJson(`${API_URL}/api/auth/microsoft/login`);
      if (data.authorization_url) {
        window.location.href = data.authorization_url;
      } else {
        console.error('No authorization_url in response');
        setMsLoading(false);
      }
    } catch (err) {
      console.error('Microsoft login error:', err);
      setMsLoading(false);
    }
  };

  const disabled = parentLoading || msLoading;

  return (
    <div className="space-y-3">
      <Button
        type="button"
        variant="outline"
        className="w-full min-h-[44px] sm:min-h-0 flex items-center justify-center gap-3 border-slate-300 hover:bg-slate-50 text-slate-700 font-medium"
        onClick={() => handleGoogleLogin(redirectTo)}
        disabled={disabled}
        data-testid="oauth-google-btn"
      >
        <svg className="w-5 h-5" viewBox="0 0 24 24">
          <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
          <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
          <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
          <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
        </svg>
        Continuer avec Google
      </Button>

      <Button
        type="button"
        variant="outline"
        className="w-full min-h-[44px] sm:min-h-0 flex items-center justify-center gap-3 border-slate-300 hover:bg-slate-50 text-slate-700 font-medium"
        onClick={handleMicrosoftLogin}
        disabled={disabled}
        data-testid="oauth-microsoft-btn"
      >
        <svg className="w-5 h-5" viewBox="0 0 23 23">
          <rect x="1" y="1" width="10" height="10" fill="#F25022"/>
          <rect x="12" y="1" width="10" height="10" fill="#7FBA00"/>
          <rect x="1" y="12" width="10" height="10" fill="#00A4EF"/>
          <rect x="12" y="12" width="10" height="10" fill="#FFB900"/>
        </svg>
        {msLoading ? 'Redirection...' : 'Continuer avec Microsoft'}
      </Button>
    </div>
  );
}
