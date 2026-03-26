import React from 'react';
import { Calendar, Clock, MapPin, Video, Users } from 'lucide-react';
import { formatDateTimeCompactFr } from '../../utils/dateFormat';

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
  const badge = SOURCE_BADGE[event.source] || SOURCE_BADGE.google;
  const attendeeCount = (event.attendees || []).length;

  return (
    <div
      className="relative border border-dashed border-slate-300 rounded-lg bg-white/60 hover:border-slate-400 transition-all"
      data-testid={`external-event-${event.external_event_id}`}
    >
      <div className="p-4">
        {/* Row 1: Title + source badge */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <h4 className="font-semibold text-sm text-slate-800 leading-tight truncate">
            {event.title}
          </h4>
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium rounded-full border flex-shrink-0 ${badge.className}`}>
            {badge.label}
          </span>
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
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
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
