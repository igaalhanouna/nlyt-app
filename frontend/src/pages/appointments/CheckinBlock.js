import React, { useState, useEffect } from 'react';
import { Button } from '../../components/ui/button';
import { Check, MapPin, Shield, Loader2, ArrowRight, Clock, Ban } from 'lucide-react';
import { checkinAPI } from '../../services/api';
import { toast } from 'sonner';

/**
 * Unified check-in block for both organizer and participant.
 * Same UX: time-gating (before/during/after), GPS display, proof link.
 * Role differences are strictly limited to the API call shape.
 */
export default function CheckinBlock({
  appointment,
  participantRecord,
  isOrganizer,
  onCheckinComplete,
  isCancelled,
  isPendingGuarantee,
  // Pre-loaded check-in state (organizer path passes these from parent)
  initialCheckinDone = false,
  initialCheckinData = null,
}) {
  const [checkinDone, setCheckinDone] = useState(initialCheckinDone);
  const [checkinData, setCheckinData] = useState(initialCheckinData);
  const [checkingIn, setCheckingIn] = useState(false);

  // Sync with parent-provided state (organizer path)
  useEffect(() => { setCheckinDone(initialCheckinDone); }, [initialCheckinDone]);
  useEffect(() => { setCheckinData(initialCheckinData); }, [initialCheckinData]);

  // Participant: fetch check-in status on mount
  const invitationToken = participantRecord?.invitation_token;
  const appointmentId = appointment?.appointment_id;

  useEffect(() => {
    if (isOrganizer || !invitationToken || !appointmentId) return;
    checkinAPI.getStatus(appointmentId, invitationToken).then(res => {
      if (res.data?.evidence_count > 0 || res.data?.checked_in) {
        setCheckinDone(true);
        const gpsEv = res.data.evidence?.find(e => e.source === 'gps' || e.derived_facts?.latitude);
        if (gpsEv) setCheckinData(gpsEv);
      }
    }).catch(() => {});
  }, [appointmentId, invitationToken, isOrganizer]);

  // Guard: only show if participant is accepted/guaranteed
  const status = participantRecord?.status;
  const canShow = status === 'accepted_guaranteed' && !isCancelled && !isPendingGuarantee;
  if (!canShow) return null;

  // Time gate: -30min / +duration+60min
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

  const isVideo = appointment?.appointment_type === 'video';
  const proofLink = invitationToken
    ? `/proof/${appointmentId}?token=${invitationToken}`
    : null;

  // Handle check-in action
  const handleCheckin = async () => {
    if (!invitationToken) return;
    setCheckingIn(true);
    try {
      const payload = {
        appointment_id: appointmentId,
        invitation_token: invitationToken,
        device_info: navigator.userAgent,
      };
      if (appointment.appointment_type === 'physical' && navigator.geolocation) {
        try {
          const pos = await new Promise((resolve, reject) =>
            navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 8000, enableHighAccuracy: true })
          );
          payload.latitude = pos.coords.latitude;
          payload.longitude = pos.coords.longitude;
          payload.gps_consent = true;
        } catch (geoErr) {
          if (geoErr.code === 1) toast.warning('Localisation refusee. Check-in enregistre sans GPS.');
          else toast.warning('GPS indisponible. Check-in enregistre sans coordonnees.');
        }
      }
      await checkinAPI.manual(payload);
      setCheckinDone(true);
      toast.success('Check-in enregistre');
      if (onCheckinComplete) onCheckinComplete();
    } catch (error) {
      const status = error.response?.status;
      const detail = error.response?.data?.detail;
      if (status === 409) { setCheckinDone(true); toast.info('Check-in deja effectue.'); }
      else if (status === 400) toast.error(detail || "Impossible d'effectuer le check-in.");
      else toast.error(detail || 'Erreur lors du check-in.');
    } finally { setCheckingIn(false); }
  };

  const roleLabel = isOrganizer ? 'organisateur' : 'participant';

  // ── State: Check-in done ──
  if (checkinDone) {
    return (
      <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-xl" data-testid="checkin-block-confirmed">
        <div className="flex items-center gap-2 mb-1">
          <Check className="w-4 h-4 text-emerald-600" />
          <span className="text-sm font-medium text-emerald-700">Check-in effectue</span>
        </div>
        {checkinData?.derived_facts && (
          <div className="pl-6 space-y-0.5">
            {checkinData.derived_facts.latitude && (
              <p className="text-xs text-slate-500 flex items-center gap-1">
                <MapPin className="w-3 h-3" />
                {Number(checkinData.derived_facts.latitude).toFixed(5)}, {Number(checkinData.derived_facts.longitude).toFixed(5)}
              </p>
            )}
            {checkinData.derived_facts.distance_km != null && (
              <p className="text-xs text-slate-500">
                Distance : {checkinData.derived_facts.distance_km < 1
                  ? `${Math.round(checkinData.derived_facts.distance_km * 1000)} m`
                  : `${checkinData.derived_facts.distance_km.toFixed(2)} km`
                } du lieu
              </p>
            )}
            {checkinData.derived_facts.address_label && (
              <p className="text-xs text-slate-400">{checkinData.derived_facts.address_label}</p>
            )}
          </div>
        )}
      </div>
    );
  }

  // ── State: Before window ──
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

  // ── State: After window ──
  if (checkinTimeState === 'after') {
    return (
      <div className="mb-4 p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center gap-2" data-testid="checkin-block-after-window">
        <Ban className="w-4 h-4 text-slate-400 flex-shrink-0" />
        <p className="text-xs text-slate-500">Fenetre de check-in expiree</p>
      </div>
    );
  }

  // ── State: During window — not checked in ──
  return (
    <div className="mb-4 p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between gap-3" data-testid="checkin-block-pending">
      <div className="flex items-center gap-2 min-w-0">
        <Shield className="w-4 h-4 text-slate-400 flex-shrink-0" />
        <p className="text-sm text-slate-600">Check-in non effectue</p>
      </div>
      {isVideo && proofLink ? (
        <a href={proofLink} data-testid="checkin-block-confirm-btn">
          <Button variant="outline" size="sm" className="h-9 text-xs font-medium gap-1.5 whitespace-nowrap">
            Confirmer <ArrowRight className="w-3 h-3" />
          </Button>
        </a>
      ) : (
        <Button variant="outline" size="sm" onClick={handleCheckin} disabled={checkingIn} className="h-9 text-xs font-medium gap-1.5 whitespace-nowrap" data-testid="checkin-block-confirm-btn">
          {checkingIn ? <Loader2 className="w-3 h-3 animate-spin" /> : <MapPin className="w-3 h-3" />}
          Check-in
        </Button>
      )}
    </div>
  );
}
