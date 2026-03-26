import React from 'react';
import { Clock, Check, MapPinCheck, QrCode, ScanLine, AlertTriangle, Video, MapPin, Loader2 } from 'lucide-react';
import { formatTimeFr, formatDateShortFr, formatEvidenceDateFr, parseUTC } from '../../utils/dateFormat';

export default function InvitationCheckinSection({
  appointment,
  participant,
  responseStatus,
  engagementRules,
  checkinStatus,
  checkingIn,
  onManualCheckin,
  onShowQR,
  onOpenQRScanner,
  token,
}) {
  const isCheckedIn = checkinStatus?.checked_in;

  const startStr = appointment.start_datetime;
  const startDate = parseUTC(startStr);
  if (!startDate) return null;

  const durationMin = appointment.duration_minutes || 60;
  const toleratedDelay = appointment.tolerated_delay_minutes || engagementRules?.tolerated_delay_minutes || 0;
  const WINDOW_BEFORE_MIN = 30;

  const windowOpen = new Date(startDate.getTime() - WINDOW_BEFORE_MIN * 60000);
  const windowClose = new Date(startDate.getTime() + (durationMin + toleratedDelay) * 60000);
  const now = new Date();

  const isBefore = now < windowOpen;
  const isDuring = now >= windowOpen && now <= windowClose;
  const isAfter = now > windowClose;

  const formatCountdown = () => {
    const diff = windowOpen - now;
    const days = Math.floor(diff / 86400000);
    const hours = Math.floor((diff % 86400000) / 3600000);
    const mins = Math.floor((diff % 3600000) / 60000);
    if (days > 0) return `${days}j ${hours}h`;
    if (hours > 0) return `${hours}h ${mins}min`;
    return `${mins} min`;
  };

  const formatTime = (d) => formatTimeFr(d.toISOString());
  const formatDate = (d) => formatDateShortFr(d.toISOString());

  const effectiveStatus = responseStatus || participant?.status;
  const isEngaged = ['accepted', 'accepted_guaranteed', 'accepted_pending_guarantee'].includes(effectiveStatus);

  return (
    <div className="bg-white rounded-2xl border-2 border-slate-200 overflow-hidden mt-6" data-testid="checkin-section">
      {!isEngaged ? (
        <div className="p-5 text-center">
          <div className="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-3">
            <Clock className="w-6 h-6 text-slate-400" />
          </div>
          <p className="text-sm font-semibold text-slate-700">Accès à l'engagement verrouillé</p>
          <p className="text-xs text-slate-500 mt-1">
            {effectiveStatus === 'accepted_pending_guarantee'
              ? 'Finalisez votre garantie pour débloquer l\'accès à l\'engagement, au calendrier et à la visio.'
              : 'Acceptez l\'invitation pour accéder à l\'engagement.'}
          </p>
        </div>
      ) : (
        <>
          {/* Header band */}
          <div className={`px-5 py-3 text-center font-semibold text-sm ${
            isCheckedIn ? 'bg-emerald-600 text-white' :
            isDuring ? 'bg-blue-600 text-white' :
            isBefore ? 'bg-slate-100 text-slate-600' :
            'bg-slate-100 text-slate-500'
          }`}>
            {isCheckedIn ? 'Présence confirmée' :
             isDuring ? (appointment.appointment_type === 'video' ? 'Rejoindre la réunion' : 'Confirmer votre présence') :
             isBefore ? (appointment.appointment_type === 'video' ? 'Réunion bientôt' : 'Check-in bientôt disponible') :
             'Fenêtre de check-in terminée'}
          </div>

          <div className="p-5">
            {/* Already checked in */}
            {isCheckedIn && (
              <div className="text-center" data-testid="checkin-done">
                <div className="w-14 h-14 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-3">
                  <Check className="w-7 h-7 text-emerald-600" />
                </div>
                <p className="font-semibold text-emerald-800 text-base">Présence enregistrée</p>
                {checkinStatus.earliest_checkin && (
                  <p className="text-sm text-emerald-600 mt-1">
                    le {formatEvidenceDateFr(checkinStatus.earliest_checkin)}
                  </p>
                )}
                <div className="flex items-center justify-center gap-4 mt-3 flex-wrap">
                  {checkinStatus.has_manual_checkin && (
                    <span className={`inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full font-medium ${
                      appointment.appointment_type === 'video'
                        ? 'bg-amber-50 text-amber-700'
                        : 'bg-emerald-50 text-emerald-700'
                    }`}>
                      <MapPinCheck className="w-3.5 h-3.5" />
                      {appointment.appointment_type === 'video' ? 'Check-in de secours' : 'Arrivée confirmée'}
                    </span>
                  )}
                  {checkinStatus.has_qr_checkin && (
                    <span className="inline-flex items-center gap-1.5 text-xs bg-blue-50 text-blue-700 px-3 py-1.5 rounded-full font-medium">
                      <QrCode className="w-3.5 h-3.5" /> QR validé
                    </span>
                  )}
                  {checkinStatus.has_gps && (
                    <span className="inline-flex items-center gap-1.5 text-xs bg-purple-50 text-purple-700 px-3 py-1.5 rounded-full font-medium">
                      <MapPin className="w-3.5 h-3.5" /> Position GPS
                    </span>
                  )}
                </div>
                {appointment.appointment_type === 'video' && checkinStatus.has_manual_checkin && !checkinStatus.has_video_evidence && (
                  <p className="text-xs text-amber-600 mt-3">
                    Note : cette preuve manuelle pourra faire l'objet d'une vérification complémentaire.
                  </p>
                )}
              </div>
            )}

            {/* Before window */}
            {!isCheckedIn && isBefore && (
              <div className="text-center" data-testid="checkin-before">
                <div className="w-14 h-14 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-3">
                  <Clock className="w-7 h-7 text-slate-400" />
                </div>
                {appointment.appointment_type === 'video' ? (
                  <>
                    <p className="font-medium text-slate-700 text-sm">
                      La réunion commencera dans <span className="font-bold text-slate-900">{formatCountdown()}</span>
                    </p>
                    <p className="text-xs text-slate-500 mt-2">
                      Votre présence sera vérifiée après la réunion via le rapport du provider.
                    </p>
                    {appointment.meeting_join_url && (
                      <p className="text-xs text-blue-600 mt-2">
                        Le lien de réunion sera actif 30 min avant le début.
                      </p>
                    )}
                  </>
                ) : (
                  <>
                    <p className="font-medium text-slate-700 text-sm">
                      Le check-in ouvrira dans <span className="font-bold text-slate-900">{formatCountdown()}</span>
                    </p>
                    <p className="text-xs text-slate-500 mt-2">
                      Disponible à partir du {formatDate(windowOpen)} à {formatTime(windowOpen)}, soit 30 min avant l'engagement
                    </p>
                    <div className="flex items-center justify-center gap-3 mt-4 opacity-50">
                      <button disabled className="flex items-center gap-2 px-4 py-2.5 bg-slate-200 text-slate-400 rounded-xl text-sm font-medium cursor-not-allowed">
                        <MapPinCheck className="w-4 h-4" /> Je suis arrivé
                      </button>
                      <button disabled className="flex items-center gap-2 px-4 py-2.5 bg-slate-200 text-slate-400 rounded-xl text-sm font-medium cursor-not-allowed">
                        <ScanLine className="w-4 h-4" /> Scanner un QR
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* During window — ACTIVE */}
            {!isCheckedIn && isDuring && (
              <div data-testid="checkin-active">
                <div className="text-center mb-5">
                  <p className="text-sm text-slate-600">
                    Fenêtre ouverte jusqu'à <span className="font-semibold">{formatTime(windowClose)}</span>
                  </p>
                </div>

                {appointment.appointment_type === 'video' ? (
                  <div>
                    <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-4 text-center" data-testid="video-primary-proof">
                      <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-3">
                        <Video className="w-6 h-6 text-blue-600" />
                      </div>
                      <p className="text-sm font-semibold text-blue-900 mb-1">
                        Confirmez votre présence et rejoignez la réunion
                      </p>
                      <p className="text-xs text-blue-700 mb-3">
                        Ce lien enregistre votre présence puis ouvre la visio automatiquement.
                      </p>
                      <a
                        href={`/proof/${appointment.appointment_id}?token=${token}`}
                        className="inline-flex items-center gap-2 px-5 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 active:scale-[0.98] transition-all font-semibold text-sm"
                        data-testid="join-meeting-btn"
                      >
                        <Video className="w-4 h-4" />
                        Confirmer ma présence
                      </a>
                      {!appointment.meeting_join_url && appointment.meeting_provider && (
                        <p className="text-xs text-blue-600 italic mt-2">
                          Le lien de réunion sera disponible prochainement via {appointment.meeting_provider}.
                        </p>
                      )}
                    </div>

                    <details className="group" data-testid="video-fallback-checkin">
                      <summary className="flex items-center justify-center gap-2 text-xs text-slate-400 cursor-pointer hover:text-slate-600 transition-colors py-2">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        <span>Problème de connexion ? Utiliser le check-in de secours</span>
                      </summary>
                      <div className="mt-3 border border-amber-200 bg-amber-50 rounded-xl p-4">
                        <p className="text-xs text-amber-800 mb-3 text-center">
                          Le check-in manuel est une solution de secours. Il pourra faire l'objet d'une vérification complémentaire.
                        </p>
                        <button
                          onClick={onManualCheckin}
                          disabled={checkingIn}
                          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-amber-600 text-white rounded-xl hover:bg-amber-700 active:scale-[0.98] transition-all font-medium text-sm disabled:opacity-50"
                          data-testid="manual-checkin-fallback-btn"
                        >
                          {checkingIn ? <Loader2 className="w-4 h-4 animate-spin" /> : <MapPinCheck className="w-4 h-4" />}
                          Check-in de secours
                        </button>
                      </div>
                    </details>
                  </div>
                ) : (
                  <div>
                    <button
                      onClick={onManualCheckin}
                      disabled={checkingIn}
                      className="w-full flex items-center justify-center gap-3 px-5 py-4 bg-emerald-600 text-white rounded-xl hover:bg-emerald-700 active:scale-[0.98] transition-all font-semibold text-base disabled:opacity-50 mb-3"
                      data-testid="manual-checkin-btn"
                    >
                      {checkingIn ? <Loader2 className="w-5 h-5 animate-spin" /> : <MapPinCheck className="w-5 h-5" />}
                      Je suis arrivé
                    </button>

                    <div className="grid grid-cols-2 gap-3">
                      <button
                        onClick={onOpenQRScanner}
                        className="flex items-center justify-center gap-2 px-4 py-3 border-2 border-slate-200 text-slate-700 rounded-xl hover:bg-slate-50 hover:border-slate-300 active:scale-[0.98] transition-all font-medium text-sm"
                        data-testid="scan-qr-btn"
                      >
                        <ScanLine className="w-4 h-4" />
                        Scanner un QR
                      </button>
                      <button
                        onClick={onShowQR}
                        className="flex items-center justify-center gap-2 px-4 py-3 border-2 border-slate-200 text-slate-700 rounded-xl hover:bg-slate-50 hover:border-slate-300 active:scale-[0.98] transition-all font-medium text-sm"
                        data-testid="show-qr-btn"
                      >
                        <QrCode className="w-4 h-4" />
                        Afficher mon QR
                      </button>
                    </div>

                    <p className="text-xs text-slate-400 text-center mt-4">
                      La position GPS sera capturée automatiquement si autorisée par votre navigateur.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* After window (not checked in) */}
            {!isCheckedIn && isAfter && (
              <div className="text-center" data-testid="checkin-closed">
                <div className="w-14 h-14 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-3">
                  <AlertTriangle className="w-7 h-7 text-red-400" />
                </div>
                <p className="font-medium text-slate-700 text-sm">La fenêtre de check-in est fermée</p>
                <p className="text-xs text-slate-500 mt-1">
                  Elle était ouverte de {formatTime(windowOpen)} à {formatTime(windowClose)}
                </p>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
