import React, { useState } from 'react';
import { Calendar, Clock, MapPin, Video, Users, Loader2, Zap } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { formatDateTimeCompactFr } from '../../utils/dateFormat';
import { externalEventsAPI } from '../../services/api';
import { toast } from 'sonner';

const SOURCE_BADGE = {
  google: {
    label: 'Google',
    className: 'bg-[#4285F4]/10 text-[#4285F4] border-[#4285F4]/20',
  },
  outlook: {
    label: 'Outlook',
    className: 'bg-[#0078D4]/10 text-[#0078D4] border-[#0078D4]/20',
  },
};

const PROVIDER_LABELS = {
  meet: 'Google Meet',
  teams: 'Microsoft Teams',
  zoom: 'Zoom',
};

export default function ExternalEventCard({ event }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const badge = SOURCE_BADGE[event.source] || SOURCE_BADGE.google;
  const attendeeCount = (event.attendees || []).length;

  const handleNlytMe = async () => {
    setLoading(true);
    try {
      const res = await externalEventsAPI.prefill(event.external_event_id);
      navigate('/appointments/create', {
        state: { fromExternal: res.data },
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 409) {
        toast.error('Cet événement a déjà été converti en engagement NLYT');
      } else {
        toast.error(detail || 'Impossible de charger les données de l\'événement');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="relative border border-dashed border-slate-300 rounded-lg bg-white/60 hover:border-slate-400 transition-all"
      data-testid={`external-event-${event.external_event_id}`}
    >
      <div className="p-4">
        {/* Row 1: Title + source badge + NLYT me */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <h4 className="font-semibold text-sm text-slate-800 leading-tight truncate">
            {event.title}
          </h4>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium rounded-full border ${badge.className}`}>
              {badge.label}
            </span>
            <button
              onClick={handleNlytMe}
              disabled={loading}
              className="inline-flex items-center gap-1 px-2.5 py-1 bg-[#fff88a] text-slate-900 rounded-md text-[11px] font-bold hover:bg-[#fff44f] active:scale-[0.96] transition-all disabled:opacity-60 shadow-sm"
              data-testid={`nlyt-me-btn-${event.external_event_id}`}
              title="Garantir ce rendez-vous avec NLYT"
            >
              {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
              NLYT me
            </button>
          </div>
        </div>

        {/* Row 2: Meta */}
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500 mb-2">
          <span className="flex items-center gap-1">
            <Calendar className="w-3 h-3" />
            {formatDateTimeCompactFr(event.start_datetime)}
          </span>
          <span className="text-slate-300">·</span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {event.duration_minutes} min
          </span>

          {event.location && (
            <>
              <span className="text-slate-300">·</span>
              <span className="flex items-center gap-1 truncate max-w-[180px]">
                <MapPin className="w-3 h-3 flex-shrink-0" />
                {event.location}
              </span>
            </>
          )}

          {event.conference_provider && (
            <>
              <span className="text-slate-300">·</span>
              <span className="flex items-center gap-1">
                <Video className="w-3 h-3" />
                {PROVIDER_LABELS[event.conference_provider] || 'Visio'}
              </span>
            </>
          )}
        </div>

        {/* Row 3: Attendees */}
        {attendeeCount > 0 && (
          <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-3">
            <Users className="w-3 h-3" />
            <span>{attendeeCount} participant{attendeeCount > 1 ? 's' : ''}</span>
            <div className="flex gap-1 ml-1 overflow-hidden max-w-[250px]">
              {event.attendees.slice(0, 3).map((att, i) => (
                <span key={i} className="px-1.5 py-0.5 bg-slate-100 rounded text-[10px] text-slate-500 truncate max-w-[80px]">
                  {att.name || att.email?.split('@')[0] || '?'}
                </span>
              ))}
              {attendeeCount > 3 && (
                <span className="px-1.5 py-0.5 bg-slate-100 rounded text-[10px] text-slate-500">
                  +{attendeeCount - 3}
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
