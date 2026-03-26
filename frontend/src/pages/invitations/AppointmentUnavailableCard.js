import React from 'react';
import { Ban } from 'lucide-react';
import { formatDateTimeFr } from '../../utils/dateFormat';

export default function AppointmentUnavailableCard({ appointment, organizer, isAppointmentCancelled }) {
  return (
    <div className="bg-white rounded-2xl shadow-xl overflow-hidden mb-6" data-testid="appointment-unavailable">
      <div className={`px-6 py-4 ${isAppointmentCancelled ? 'bg-red-600' : 'bg-slate-600'} text-white text-center`}>
        <h2 className="text-xl font-semibold">
          {isAppointmentCancelled ? 'Cet engagement a été annulé' : 'Cet engagement n\'est plus disponible'}
        </h2>
      </div>
      <div className="p-6">
        <div className="text-center">
          <div className={`w-16 h-16 ${isAppointmentCancelled ? 'bg-red-100' : 'bg-slate-100'} rounded-full flex items-center justify-center mx-auto mb-4`}>
            <Ban className={`w-8 h-8 ${isAppointmentCancelled ? 'text-red-600' : 'text-slate-600'}`} />
          </div>
          <h3 className="text-lg font-semibold text-slate-800 mb-2">{appointment.title}</h3>
          <p className="text-slate-600 mb-4">
            {isAppointmentCancelled 
              ? `L'organisateur (${organizer.name}) a annulé cet engagement.`
              : 'Cet engagement a été supprimé par l\'organisateur.'}
          </p>
          <p className="text-sm text-slate-500">
            <strong>Prévu le :</strong> {formatDateTimeFr(appointment.start_datetime)}
          </p>
          {appointment.location && (
            <p className="text-sm text-slate-500">
              <strong>Lieu :</strong> {appointment.location}
            </p>
          )}
          <p className="text-slate-600 mt-4 font-medium">
            Vous n'avez plus besoin de vous présenter à cet engagement.
          </p>
        </div>
      </div>
    </div>
  );
}
