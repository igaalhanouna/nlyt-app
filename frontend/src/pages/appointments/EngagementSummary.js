import React from 'react';

export default function EngagementSummary({ appointment, isCancelled }) {
  return (
    <div className={`grid grid-cols-4 gap-2 mb-4 ${isCancelled ? 'opacity-60' : ''}`} data-testid="engagement-summary">
      {/* Compensation — dominant (2 cols) */}
      <div className="col-span-2 bg-rose-50 border border-rose-100 rounded-xl p-3 text-center">
        <p className="text-2xl font-bold text-rose-700 tabular-nums" data-testid="compensation-amount">
          {appointment.penalty_amount} {appointment.penalty_currency?.toUpperCase()}
        </p>
        <p className="text-[10px] sm:text-xs text-rose-500 font-medium mt-0.5">Compensation</p>
      </div>
      {/* Tolerance */}
      <div className="bg-slate-50 border border-slate-100 rounded-xl p-3 text-center">
        <p className="text-lg font-bold text-slate-900 tabular-nums">{appointment.tolerated_delay_minutes}</p>
        <p className="text-[10px] sm:text-xs text-slate-500 font-medium mt-0.5">min tolérance</p>
      </div>
      {/* Cancellation deadline */}
      <div className="bg-slate-50 border border-slate-100 rounded-xl p-3 text-center">
        <p className="text-lg font-bold text-slate-900 tabular-nums">{appointment.cancellation_deadline_hours}h</p>
        <p className="text-[10px] sm:text-xs text-slate-500 font-medium mt-0.5">annulation</p>
        {appointment.cancellation_deadline_hours_original && appointment.cancellation_deadline_hours_original !== appointment.cancellation_deadline_hours && (
          <p className="text-[9px] text-amber-600 mt-0.5" data-testid="deadline-adjusted-note">
            ajusté de {appointment.cancellation_deadline_hours_original}h
          </p>
        )}
      </div>
    </div>
  );
}
