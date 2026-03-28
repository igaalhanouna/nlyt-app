import React from 'react';
import { Button } from '../../components/ui/button';
import { Check, MapPin, Shield, Loader2, ArrowRight, Clock, Ban } from 'lucide-react';

export default function OrganizerCheckinBlock({
  appointment, organizerParticipant, organizerCheckinDone, organizerCheckinData,
  checkingIn, handleOrganizerCheckin, isCancelled, isPendingGuarantee,
}) {
  const canCheckin = organizerParticipant?.status === 'accepted_guaranteed' && !isCancelled && !isPendingGuarantee;
  if (!canCheckin) return null;

  // Time gate: same rule as rest of system (-30min / +60min)
  const WINDOW_BEFORE_MIN = 30;
  const WINDOW_AFTER_MIN = 60;
  let checkinTimeState = 'during';
  let minutesUntilOpen = 0;
  if (appointment?.start_datetime) {
    const startMs = new Date(appointment.start_datetime).getTime();
    const durationMin = appointment.duration_minutes || 60;
    const openMs = startMs - WINDOW_BEFORE_MIN * 60000;
    const closeMs = startMs + (durationMin + WINDOW_AFTER_MIN) * 60000;
    const nowMs = Date.now();
    if (nowMs < openMs) {
      checkinTimeState = 'before';
      minutesUntilOpen = Math.ceil((openMs - nowMs) / 60000);
    } else if (nowMs > closeMs) {
      checkinTimeState = 'after';
    }
  }

  const formatCountdown = (mins) => {
    const d = Math.floor(mins / 1440);
    const h = Math.floor((mins % 1440) / 60);
    const m = mins % 60;
    if (d > 0) return `${d}j ${h}h`;
    if (h > 0) return `${h}h ${m}min`;
    return `${m} min`;
  };

  const isVideo = appointment.appointment_type === 'video';
  const proofLink = organizerParticipant?.invitation_token
    ? `/proof/${appointment.appointment_id}?token=${organizerParticipant.invitation_token}`
    : null;

  if (organizerCheckinDone) {
    return (
      <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-xl" data-testid="checkin-block-confirmed">
        <div className="flex items-center gap-2 mb-1">
          <Check className="w-4 h-4 text-emerald-600" />
          <span className="text-sm font-medium text-emerald-700">Présence confirmée</span>
        </div>
        {organizerCheckinData?.derived_facts && (
          <div className="pl-6 space-y-0.5">
            {organizerCheckinData.derived_facts.latitude && (
              <p className="text-xs text-slate-500 flex items-center gap-1">
                <MapPin className="w-3 h-3" />
                {Number(organizerCheckinData.derived_facts.latitude).toFixed(5)}, {Number(organizerCheckinData.derived_facts.longitude).toFixed(5)}
              </p>
            )}
            {organizerCheckinData.derived_facts.distance_km != null && (
              <p className="text-xs text-slate-500">
                Distance : {organizerCheckinData.derived_facts.distance_km < 1
                  ? `${Math.round(organizerCheckinData.derived_facts.distance_km * 1000)} m`
                  : `${organizerCheckinData.derived_facts.distance_km.toFixed(2)} km`
                } du lieu
              </p>
            )}
            {organizerCheckinData.derived_facts.address_label && (
              <p className="text-xs text-slate-400">{organizerCheckinData.derived_facts.address_label}</p>
            )}
          </div>
        )}
      </div>
    );
  }

  // Not yet checked in — time-gated states
  if (checkinTimeState === 'before') {
    return (
      <div className="mb-4 p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center gap-2.5" data-testid="checkin-block-before-window">
        <Clock className="w-4 h-4 text-slate-400 flex-shrink-0" />
        <p className="text-xs font-medium text-slate-500">
          Check-in disponible dans {formatCountdown(minutesUntilOpen)}
        </p>
      </div>
    );
  }

  if (checkinTimeState === 'after') {
    return (
      <div className="mb-4 p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center gap-2" data-testid="checkin-block-after-window">
        <Ban className="w-4 h-4 text-slate-400 flex-shrink-0" />
        <p className="text-xs text-slate-500">Fenêtre de check-in expirée</p>
      </div>
    );
  }

  // During window — contextual reminder (lighter than header CTA)
  return (
    <div className="mb-4 p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between gap-3" data-testid="checkin-block-pending">
      <div className="flex items-center gap-2 min-w-0">
        <Shield className="w-4 h-4 text-slate-400 flex-shrink-0" />
        <p className="text-sm text-slate-600">Présence non confirmée</p>
      </div>
      {isVideo && proofLink ? (
        <a href={proofLink} data-testid="checkin-block-confirm-btn">
          <Button variant="outline" size="sm" className="h-9 text-xs font-medium gap-1.5 whitespace-nowrap">
            Confirmer <ArrowRight className="w-3 h-3" />
          </Button>
        </a>
      ) : (
        <Button variant="outline" size="sm" onClick={handleOrganizerCheckin} disabled={checkingIn} className="h-9 text-xs font-medium gap-1.5 whitespace-nowrap" data-testid="checkin-block-confirm-btn">
          {checkingIn ? <Loader2 className="w-3 h-3 animate-spin" /> : <MapPin className="w-3 h-3" />}
          Check-in
        </Button>
      )}
    </div>
  );
}
