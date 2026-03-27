import React from 'react';
import { Calendar, Clock, MapPin, Users, Video, ExternalLink, Shield, UserCheck } from 'lucide-react';
import { formatDateTimeFr } from '../../utils/dateFormat';

const PROVIDER_LABELS = {
  zoom: 'Zoom', teams: 'Microsoft Teams', meet: 'Google Meet',
};

export default function InvitationAppointmentDetails({ appointment, otherParticipants, confirmedCount, totalParticipants, effectiveStatus }) {
  const isVideo = appointment.appointment_type === 'video';
  const providerLabel = PROVIDER_LABELS[(appointment.meeting_provider || '').toLowerCase()] || appointment.meeting_provider || 'Visioconférence';
  const isEngagementFinalized = ['accepted', 'accepted_guaranteed'].includes(effectiveStatus);
  const displayLocation = appointment.location_display_name || appointment.location || '';

  return (
    <div className="p-6 border-b border-slate-100">
      <h2 className="text-2xl font-bold text-slate-800 mb-4" data-testid="appointment-title">
        {appointment.title}
      </h2>

      <div className="space-y-3">
        <div className="flex items-center gap-3 text-slate-600">
          <Calendar className="w-5 h-5 text-slate-400" />
          <span data-testid="appointment-date">{formatDateTimeFr(appointment.start_datetime)}</span>
        </div>

        <div className="flex items-center gap-3 text-slate-600">
          <Clock className="w-5 h-5 text-slate-400" />
          <span>{appointment.duration_minutes} minutes</span>
        </div>

        {/* Location — full address */}
        {!isVideo && displayLocation && (
          <div className="flex items-start gap-3 text-slate-600">
            <MapPin className="w-5 h-5 text-slate-400 mt-0.5" />
            <span data-testid="appointment-location">{displayLocation}</span>
          </div>
        )}

        {/* Video meeting — provider + join link block */}
        {isVideo && (
          <div className="flex items-start gap-3 text-slate-600">
            <Video className="w-5 h-5 text-slate-400 mt-0.5" />
            <div>
              <span>{providerLabel}</span>
            </div>
          </div>
        )}

        {/* Meeting Link CTA — prominent block */}
        {isVideo && isEngagementFinalized && appointment.meeting_join_url && (
          <a
            href={appointment.meeting_join_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 mt-1 px-4 py-3 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors"
            data-testid="meeting-join-block"
          >
            <Video className="w-5 h-5 text-blue-600 flex-shrink-0" />
            <div className="flex-1">
              <span className="text-sm font-semibold text-blue-700">Rejoindre la réunion</span>
              <span className="block text-xs text-blue-500 truncate">{providerLabel}</span>
            </div>
            <ExternalLink className="w-4 h-4 text-blue-400 flex-shrink-0" />
          </a>
        )}

        {/* Participants */}
        {otherParticipants && otherParticipants.length > 0 && (
          <div className="flex items-start gap-3 text-slate-600">
            <Users className="w-5 h-5 text-slate-400 mt-0.5" />
            <div>
              <span className="font-medium">{(otherParticipants.length + 1)} participants</span>
              <div className="flex flex-wrap gap-2 mt-1">
                {otherParticipants.map((p, idx) => (
                  <span
                    key={idx}
                    className={`text-xs px-2 py-1 rounded-full ${
                      ['accepted', 'accepted_guaranteed'].includes(p.status) ? 'bg-green-100 text-green-700' :
                      p.status === 'accepted_pending_guarantee' ? 'bg-amber-100 text-amber-700' :
                      p.status === 'declined' ? 'bg-red-100 text-red-700' :
                      'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {p.name || 'Participant'}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Trust signal */}
        {confirmedCount > 0 && (
          <div className="mt-2 pt-3 border-t border-dashed border-slate-200">
            <div className="flex items-center gap-2 text-xs font-medium text-emerald-600" data-testid="trust-signal">
              <Shield className="w-3.5 h-3.5" />
              {confirmedCount} participant{confirmedCount > 1 ? 's' : ''} {confirmedCount > 1 ? 'ont' : 'a'} déjà confirmé {confirmedCount > 1 ? 'leur' : 'son'} engagement
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
