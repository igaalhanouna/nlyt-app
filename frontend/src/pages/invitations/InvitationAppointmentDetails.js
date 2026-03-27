import React from 'react';
import { Calendar, Clock, MapPin, Users, Video } from 'lucide-react';
import { formatDateTimeFr } from '../../utils/dateFormat';

const PROVIDER_LABELS = {
  zoom: 'Zoom', teams: 'Microsoft Teams', meet: 'Google Meet',
};

export default function InvitationAppointmentDetails({ appointment, otherParticipants }) {
  const isVideo = appointment.appointment_type === 'video';
  const providerLabel = PROVIDER_LABELS[(appointment.meeting_provider || '').toLowerCase()] || appointment.meeting_provider || 'Visioconférence';

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

        {!isVideo && appointment.location && (
          <div className="flex items-center gap-3 text-slate-600">
            <MapPin className="w-5 h-5 text-slate-400" />
            <span data-testid="appointment-location">{appointment.location}</span>
          </div>
        )}

        {isVideo && (
          <div className="flex items-center gap-3 text-slate-600">
            <Video className="w-5 h-5 text-slate-400" />
            <span>{providerLabel}</span>
          </div>
        )}

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
      </div>
    </div>
  );
}
