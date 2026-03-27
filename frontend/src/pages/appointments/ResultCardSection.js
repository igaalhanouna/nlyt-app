import React, { useState, useEffect } from 'react';
import { Share2, Sparkles } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { ResultCard, ResultCardActions } from '../../components/ResultCard';
import { resultCardsAPI } from '../../services/api';
import { toast } from 'sonner';

/**
 * Determines which card types are available based on attendance + distributions.
 */
function detectAvailableCards(attendance, appointment, userId) {
  const cards = [];
  const records = attendance?.records || [];

  // 1. Check if current user was present (engagement respected)
  const userRecord = records.find(
    (r) => r.participant_email && (r.outcome === 'on_time' || r.outcome === 'late')
  );
  // Also check if user is organizer (organizers who show up)
  const isOrganizer = appointment?.organizer_id === userId;
  const anyPresent = records.some((r) => r.outcome === 'on_time' || r.outcome === 'late');

  if (userRecord || (isOrganizer && anyPresent)) {
    cards.push('engagement_respected');
  }

  // 2. Check for compensation (user received compensation from a no-show)
  // This is visible if the current user is the organizer and someone was absent
  const anyNoShow = records.some((r) => r.outcome === 'no_show' || r.outcome === 'late_penalized');
  if (isOrganizer && anyNoShow) {
    cards.push('compensation_received');
  }

  // 3. Check for charity donation (if any distribution went to charity)
  if (anyNoShow && appointment?.charity_association_id) {
    cards.push('charity_donation');
  }

  return cards;
}

const CARD_LABELS = {
  engagement_respected: 'Engagement tenu',
  compensation_received: 'Temps valorisé',
  charity_donation: 'Geste solidaire',
};

export default function ResultCardSection({ attendance, appointment, userId }) {
  const [availableTypes, setAvailableTypes] = useState([]);
  const [selectedType, setSelectedType] = useState(null);
  const [generatedCard, setGeneratedCard] = useState(null);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    if (attendance && appointment) {
      const types = detectAvailableCards(attendance, appointment, userId);
      setAvailableTypes(types);
      if (types.length > 0 && !selectedType) {
        setSelectedType(types[0]);
      }
    }
  }, [attendance, appointment, userId, selectedType]);

  if (availableTypes.length === 0) return null;

  const handleGenerate = async () => {
    if (!selectedType) return;
    setGenerating(true);
    try {
      const res = await resultCardsAPI.create({
        appointment_id: appointment.appointment_id,
        card_type: selectedType,
      });
      setGeneratedCard(res.data);
      toast.success('Carte générée');
    } catch (e) {
      const msg = e.response?.data?.detail || 'Erreur lors de la génération';
      toast.error(msg);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div
      data-testid="result-card-section"
      className="mb-4 bg-white border border-slate-200 rounded-xl overflow-hidden"
    >
      <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-amber-500" />
        <span className="text-sm font-semibold text-slate-900">
          Partagez votre résultat
        </span>
      </div>

      <div className="p-4">
        {!generatedCard ? (
          <>
            <p className="text-sm text-slate-500 mb-3">
              Créez une carte et partagez-la pour valoriser votre engagement.
            </p>

            {/* Type selector */}
            {availableTypes.length > 1 && (
              <div className="flex flex-wrap gap-2 mb-4">
                {availableTypes.map((type) => (
                  <button
                    key={type}
                    data-testid={`card-type-${type}`}
                    onClick={() => { setSelectedType(type); setGeneratedCard(null); }}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                      selectedType === type
                        ? 'bg-slate-900 text-white'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {CARD_LABELS[type]}
                  </button>
                ))}
              </div>
            )}

            <Button
              data-testid="generate-result-card-btn"
              onClick={handleGenerate}
              disabled={generating || !selectedType}
              className="w-full sm:w-auto flex items-center gap-2"
              style={{ background: '#0A0A0B', color: '#fff' }}
            >
              {generating ? (
                <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
              ) : (
                <Share2 size={16} />
              )}
              {generating ? 'Génération...' : `Créer ma carte`}
            </Button>
          </>
        ) : (
          <div className="flex flex-col items-center">
            <ResultCard card={generatedCard} compact />
            <ResultCardActions card={generatedCard} />

            {availableTypes.length > 1 && (
              <button
                data-testid="generate-another-card-btn"
                onClick={() => setGeneratedCard(null)}
                className="mt-3 text-xs text-slate-400 hover:text-slate-600 underline"
              >
                Créer une autre carte
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
