import React from 'react';
import { Check, MapPin } from 'lucide-react';

/**
 * Post-check-in details block.
 * Displays GPS coordinates, distance, and address after check-in.
 * No CTA — the primary check-in action lives in AppointmentHeader.
 */
export default function CheckinBlock({
  appointment,
  checkinDone,
  checkinData,
  isCancelled,
  isPendingGuarantee,
  participantStatus,
}) {
  // Only show when check-in is done and there are GPS details to display
  const canShow = participantStatus === 'accepted_guaranteed' && !isCancelled && !isPendingGuarantee;
  if (!canShow || !checkinDone) return null;

  const facts = checkinData?.derived_facts;
  if (!facts || (!facts.latitude && facts.distance_km == null && !facts.address_label)) return null;

  return (
    <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-xl" data-testid="checkin-details-block">
      <div className="flex items-center gap-2 mb-1">
        <Check className="w-4 h-4 text-emerald-600" />
        <span className="text-sm font-medium text-emerald-700">Détails du check-in</span>
      </div>
      <div className="pl-6 space-y-0.5">
        {facts.latitude && (
          <p className="text-xs text-slate-500 flex items-center gap-1">
            <MapPin className="w-3 h-3" />
            {Number(facts.latitude).toFixed(5)}, {Number(facts.longitude).toFixed(5)}
          </p>
        )}
        {facts.distance_km != null && (
          <p className="text-xs text-slate-500">
            Distance : {facts.distance_km < 1
              ? `${Math.round(facts.distance_km * 1000)} m`
              : `${facts.distance_km.toFixed(2)} km`
            } du lieu
          </p>
        )}
        {facts.address_label && (
          <p className="text-xs text-slate-400">{facts.address_label}</p>
        )}
      </div>
    </div>
  );
}
