import React from 'react';
import { Calendar, Video, MapPin, Shield, Pencil } from 'lucide-react';
import { formatDateTimeFr } from '../../utils/dateFormat';

const PROVIDER_LABELS = {
  zoom: 'Zoom', teams: 'Microsoft Teams', meet: 'Google Meet',
};

export default function AppointmentEssentials({
  appointment, isCancelled, organizerParticipant, guaranteedCount, canEdit, onEdit,
}) {
  const isVideo = appointment.appointment_type === 'video';
  const providerLabel = PROVIDER_LABELS[(appointment.meeting_provider || '').toLowerCase()] || appointment.meeting_provider || 'Visio';
  const proofLink = organizerParticipant?.invitation_token
    ? `/proof/${appointment.appointment_id}?token=${organizerParticipant.invitation_token}`
    : null;

  const trustLabel = isCancelled
    ? 'Engagement annulé'
    : appointment.status === 'pending_organizer_guarantee'
    ? 'En attente de garantie organisateur'
    : guaranteedCount > 0
    ? `Engagement actif · ${guaranteedCount} participant${guaranteedCount > 1 ? 's' : ''} garanti${guaranteedCount > 1 ? 's' : ''}`
    : 'Engagement actif';

  return (
    <div className={`mb-4 ${isCancelled ? 'opacity-60' : ''}`} data-testid="appointment-essentials">
      <div className="space-y-3">
        {/* Date & Time */}
        <div className="flex items-start gap-3">
          <Calendar className="w-5 h-5 text-slate-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-slate-900" data-testid="appointment-datetime-display">
              {formatDateTimeFr(appointment.start_datetime)}
            </p>
            <p className="text-xs text-slate-500">Durée : {appointment.duration_minutes} min</p>
          </div>
          {canEdit && (
            <button onClick={onEdit} className="p-3 -m-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors" title="Modifier" data-testid="edit-general-info-btn">
              <Pencil className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Location or Video platform */}
        {isVideo && appointment.meeting_provider && (
          <div className="flex items-start gap-3">
            <Video className="w-5 h-5 text-slate-400 mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-slate-900">{providerLabel}</p>
              {appointment.meeting_join_url && (
                <a
                  href={proofLink || appointment.meeting_join_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800 font-medium mt-0.5"
                  data-testid="meeting-link"
                >
                  <Video className="w-3.5 h-3.5" /> Check-in et rejoindre la réunion
                </a>
              )}
            </div>
          </div>
        )}

        {appointment.appointment_type === 'physical' && (appointment.location_display_name || appointment.location) && (
          <div className="flex items-start gap-3">
            <MapPin className="w-5 h-5 text-slate-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-slate-900">{appointment.location_display_name || appointment.location}</p>
            </div>
          </div>
        )}
      </div>

      {/* Trust signal */}
      <div className="mt-3 pt-3 border-t border-dashed border-slate-200">
        <div className={`flex items-center gap-2 text-xs font-medium ${isCancelled ? 'text-red-500' : 'text-slate-500'}`} data-testid="trust-signal">
          <Shield className="w-3.5 h-3.5" />
          {trustLabel}
        </div>
      </div>
    </div>
  );
}
