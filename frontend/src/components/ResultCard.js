import React, { useState, useRef } from 'react';
import { Share2, Copy, Download, Check, Eye } from 'lucide-react';
import { Button } from '../components/ui/button';

const SITE_URL = 'https://app.nlyt.io';

const CARD_CONFIG = {
  engagement_respected: {
    accentColor: '#10B981',
    accentBg: '#F0FDF4',
    accentBorder: '#BBF7D0',
    icon: '&#10004;',
    iconColor: '#166534',
    headline: 'Engagement tenu.',
    subtitle: 'Rien n\u2019a \u00e9t\u00e9 d\u00e9bit\u00e9.',
    brandLine: 'Le temps ne se perd plus.',
  },
  compensation_received: {
    accentColor: '#3B82F6',
    accentBg: '#EFF6FF',
    accentBorder: '#BFDBFE',
    icon: '&#9670;',
    iconColor: '#1D4ED8',
    headline: 'Temps valoris\u00e9.',
    subtitle: null, // dynamic: amount
    brandLine: 'Votre temps a de la valeur.',
  },
  charity_donation: {
    accentColor: '#F59E0B',
    accentBg: '#FFFBEB',
    accentBorder: '#FDE68A',
    icon: '&#9829;',
    iconColor: '#B45309',
    headline: 'Geste solidaire.',
    subtitle: null, // dynamic: amount + association
    brandLine: 'Chaque absence peut faire du bien.',
  },
};

function formatAmount(cents, currency = 'EUR') {
  if (!cents || cents <= 0) return null;
  const val = (cents / 100).toFixed(cents % 100 === 0 ? 0 : 2);
  return `${val} ${currency}`;
}

function formatDateShort(isoDate, tz = 'Europe/Paris') {
  if (!isoDate) return '';
  try {
    const d = new Date(isoDate);
    return d.toLocaleDateString('fr-FR', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      timeZone: tz,
    });
  } catch {
    return isoDate;
  }
}

export function ResultCard({ card, compact = false }) {
  const config = CARD_CONFIG[card.card_type];
  if (!config) return null;

  const amountStr = formatAmount(card.amount_cents, card.currency);
  const dateStr = formatDateShort(card.appointment_date, card.appointment_timezone);

  let subtitle = config.subtitle;
  if (card.card_type === 'compensation_received' && amountStr) {
    subtitle = `${amountStr} re\u00e7us en compensation.`;
  } else if (card.card_type === 'compensation_received') {
    subtitle = 'Compensation re\u00e7ue.';
  }
  if (card.card_type === 'charity_donation') {
    const parts = [];
    if (amountStr) parts.push(`${amountStr} revers\u00e9s`);
    if (card.association_name) parts.push(`\u00e0 ${card.association_name}`);
    subtitle = parts.length > 0 ? `${parts.join(' ')}.` : 'Don revers\u00e9 \u00e0 une association.';
  }

  return (
    <div
      data-testid={`result-card-${card.card_type}`}
      className="result-card-container"
      style={{
        width: '100%',
        maxWidth: compact ? 340 : 400,
        borderRadius: 16,
        overflow: 'hidden',
        boxShadow: '0 4px 24px rgba(0,0,0,0.10), 0 1px 4px rgba(0,0,0,0.06)',
        fontFamily: "'Inter', Helvetica, Arial, sans-serif",
        background: '#FFFFFF',
      }}
    >
      {/* Header band */}
      <div
        style={{
          background: '#0A0A0B',
          padding: compact ? '14px 20px' : '18px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span
          style={{
            fontSize: compact ? 14 : 16,
            fontWeight: 700,
            letterSpacing: '0.3em',
            color: '#FFFFFF',
          }}
        >
          N<span style={{ color: 'rgba(255,255,255,0.5)' }}>&middot;</span>L
          <span style={{ color: 'rgba(255,255,255,0.5)' }}>&middot;</span>Y
          <span style={{ color: 'rgba(255,255,255,0.5)' }}>&middot;</span>T
        </span>
        <span
          style={{
            fontSize: 9,
            fontWeight: 500,
            letterSpacing: '0.2em',
            color: '#64748B',
            textTransform: 'uppercase',
          }}
        >
          Never Lose Your Time
        </span>
      </div>

      {/* Accent strip */}
      <div style={{ height: 4, background: config.accentColor }} />

      {/* Body */}
      <div style={{ padding: compact ? '24px 20px' : '32px 28px' }}>
        {/* Icon */}
        <div
          style={{
            width: compact ? 44 : 52,
            height: compact ? 44 : 52,
            borderRadius: '50%',
            background: config.accentBg,
            border: `2px solid ${config.accentBorder}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: compact ? 16 : 20,
          }}
        >
          <span
            style={{
              fontSize: compact ? 20 : 24,
              color: config.iconColor,
              fontWeight: 700,
              lineHeight: 1,
            }}
            dangerouslySetInnerHTML={{ __html: config.icon }}
          />
        </div>

        {/* Headline */}
        <h2
          style={{
            margin: '0 0 6px 0',
            fontSize: compact ? 22 : 26,
            fontWeight: 800,
            color: '#0F172A',
            lineHeight: 1.2,
            letterSpacing: '-0.01em',
          }}
        >
          {config.headline}
        </h2>

        {/* Subtitle */}
        {subtitle && (
          <p
            style={{
              margin: '0 0 20px 0',
              fontSize: compact ? 14 : 15,
              color: '#64748B',
              lineHeight: 1.5,
            }}
          >
            {subtitle}
          </p>
        )}

        {/* Engagement details */}
        <div
          style={{
            background: '#F8FAFC',
            borderRadius: 10,
            padding: compact ? '12px 14px' : '14px 16px',
            marginBottom: compact ? 16 : 20,
            borderLeft: `3px solid ${config.accentColor}`,
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: compact ? 13 : 14,
              fontWeight: 600,
              color: '#0F172A',
              lineHeight: 1.4,
            }}
          >
            {card.appointment_title}
          </p>
          {dateStr && (
            <p
              style={{
                margin: '4px 0 0 0',
                fontSize: compact ? 11 : 12,
                color: '#94A3B8',
              }}
            >
              {dateStr}
            </p>
          )}
        </div>

        {/* User name */}
        {card.user_name && (
          <p
            style={{
              margin: '0 0 16px 0',
              fontSize: compact ? 12 : 13,
              color: '#94A3B8',
              fontWeight: 500,
            }}
          >
            {card.user_name}
          </p>
        )}

        {/* Separator + brand line */}
        <div
          style={{
            borderTop: '1px solid #E2E8F0',
            paddingTop: compact ? 14 : 16,
            textAlign: 'center',
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: compact ? 12 : 13,
              fontWeight: 600,
              color: '#475569',
              fontStyle: 'italic',
              letterSpacing: '0.01em',
            }}
          >
            {config.brandLine}
          </p>
        </div>
      </div>

      {/* View count (if public) */}
      {card.view_count > 0 && (
        <div
          style={{
            padding: '0 28px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}
        >
          <Eye size={12} color="#CBD5E1" />
          <span style={{ fontSize: 11, color: '#CBD5E1' }}>
            {card.view_count} vue{card.view_count > 1 ? 's' : ''}
          </span>
        </div>
      )}
    </div>
  );
}

export function ResultCardActions({ card }) {
  const [copied, setCopied] = useState(false);
  const shareUrl = `${window.location.origin}/card/${card.card_id}`;

  const handleShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: `NLYT \u2014 ${CARD_CONFIG[card.card_type]?.headline || ''}`,
          text: CARD_CONFIG[card.card_type]?.brandLine || '',
          url: shareUrl,
        });
      } catch {
        // User cancelled
      }
    } else {
      handleCopy();
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const textarea = document.createElement('textarea');
      textarea.value = shareUrl;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div
      data-testid="result-card-actions"
      style={{
        display: 'flex',
        gap: 8,
        flexWrap: 'wrap',
        marginTop: 16,
      }}
    >
      <Button
        data-testid="result-card-share-btn"
        onClick={handleShare}
        className="flex items-center gap-2"
        style={{
          background: '#0A0A0B',
          color: '#fff',
          borderRadius: 8,
          padding: '10px 20px',
          fontSize: 14,
          fontWeight: 600,
        }}
      >
        <Share2 size={16} />
        Partager
      </Button>

      <Button
        data-testid="result-card-copy-btn"
        variant="outline"
        onClick={handleCopy}
        className="flex items-center gap-2"
        style={{
          borderRadius: 8,
          padding: '10px 20px',
          fontSize: 14,
          fontWeight: 500,
        }}
      >
        {copied ? <Check size={16} /> : <Copy size={16} />}
        {copied ? 'Copi\u00e9' : 'Copier le lien'}
      </Button>
    </div>
  );
}

export default ResultCard;
