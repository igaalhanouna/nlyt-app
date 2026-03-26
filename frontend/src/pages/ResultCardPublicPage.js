import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ResultCard, ResultCardActions } from '../components/ResultCard';
import { ArrowRight } from 'lucide-react';
import { Button } from '../components/ui/button';

const API = process.env.REACT_APP_BACKEND_URL;
const SITE_URL = 'https://app.nlyt.io';

export default function ResultCardPublicPage() {
  const { cardId } = useParams();
  const [card, setCard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchCard() {
      try {
        const res = await fetch(`${API}/api/result-cards/${cardId}`);
        if (!res.ok) throw new Error('Carte introuvable');
        const data = await res.json();
        setCard(data);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    fetchCard();
  }, [cardId]);

  if (loading) {
    return (
      <div
        data-testid="result-card-loading"
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#F1F5F9',
          fontFamily: "'Inter', Helvetica, Arial, sans-serif",
        }}
      >
        <div style={{ color: '#94A3B8', fontSize: 14 }}>Chargement...</div>
      </div>
    );
  }

  if (error || !card) {
    return (
      <div
        data-testid="result-card-error"
        style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#F1F5F9',
          fontFamily: "'Inter', Helvetica, Arial, sans-serif",
          padding: 24,
        }}
      >
        <p style={{ color: '#64748B', fontSize: 16, marginBottom: 16 }}>
          Cette carte n'existe pas ou a été supprimée.
        </p>
        <Link to="/">
          <Button variant="outline">Retour à l'accueil</Button>
        </Link>
      </div>
    );
  }

  return (
    <div
      data-testid="result-card-public-page"
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#F1F5F9',
        fontFamily: "'Inter', Helvetica, Arial, sans-serif",
        padding: '32px 16px',
      }}
    >
      {/* The card */}
      <ResultCard card={card} />

      {/* Share/Copy actions */}
      <ResultCardActions card={card} />

      {/* CTA: Discover NLYT */}
      <div
        style={{
          marginTop: 32,
          textAlign: 'center',
          maxWidth: 400,
          width: '100%',
        }}
      >
        <a
          href={SITE_URL}
          data-testid="result-card-discover-cta"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '14px 28px',
            background: '#0A0A0B',
            color: '#FFFFFF',
            borderRadius: 10,
            fontSize: 15,
            fontWeight: 600,
            textDecoration: 'none',
            letterSpacing: '0.01em',
            transition: 'opacity 0.15s',
          }}
        >
          Découvrir NLYT
          <ArrowRight size={18} />
        </a>
        <p
          style={{
            marginTop: 12,
            fontSize: 12,
            color: '#94A3B8',
          }}
        >
          Protégez votre temps. Toujours.
        </p>
      </div>
    </div>
  );
}
