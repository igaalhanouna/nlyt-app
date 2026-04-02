import React, { useState } from 'react';
import { Button } from '../../components/ui/button';
import { Ban, Download, Calendar, Check, Zap, Loader2, AlertTriangle, LogOut } from 'lucide-react';
import { invitationAPI } from '../../services/api';
import { toast } from 'sonner';
import { parseUTC } from '../../utils/dateFormat';

export default function QuickActions({
  appointment, isCancelled, syncStatus, syncingProvider,
  onSyncCalendar, onDownloadICS, onShowCancelModal,
  isOrganizer = true,
  viewerInvitationToken,
  viewerParticipantStatus,
  onParticipantCancelComplete,
}) {
  const [cancellingParticipation, setCancellingParticipation] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);

  // Temporal checks
  const startDt = appointment?.start_datetime ? parseUTC(appointment.start_datetime) : null;
  const now = new Date();
  const isStarted = startDt && now >= startDt;
  const deadlineHours = appointment?.cancellation_deadline_hours || 0;
  const cancellationDeadline = deadlineHours > 0 && startDt
    ? new Date(startDt.getTime() - deadlineHours * 3600000)
    : null;
  const isPastCancelDeadline = cancellationDeadline ? now >= cancellationDeadline : false;

  const canCancelParticipation = !isOrganizer
    && ['accepted', 'accepted_guaranteed'].includes(viewerParticipantStatus)
    && !isCancelled
    && !isStarted
    && !isPastCancelDeadline;

  const cancelParticipationDisabled = !isOrganizer
    && ['accepted', 'accepted_guaranteed'].includes(viewerParticipantStatus)
    && !isCancelled
    && !isStarted
    && isPastCancelDeadline;

  const handleCancelParticipation = async () => {
    if (!viewerInvitationToken) return;
    if (!confirmCancel) { setConfirmCancel(true); return; }
    setConfirmCancel(false);
    setCancellingParticipation(true);
    try {
      await invitationAPI.cancelParticipation(viewerInvitationToken);
      toast.success('Participation annulée');
      if (onParticipantCancelComplete) onParticipantCancelComplete();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Impossible d\'annuler la participation');
    } finally {
      setCancellingParticipation(false);
    }
  };

  return (
    <div className={`mb-4 ${isCancelled ? 'opacity-60' : ''}`} data-testid="quick-actions">
      {/* Calendar + ICS — compact inline */}
      <div className="flex flex-wrap gap-2 mb-2">
        <Button variant="outline" size="sm" onClick={onDownloadICS} className="gap-1.5 h-9 text-xs" data-testid="download-ics-btn">
          <Download className="w-3.5 h-3.5" /> .ics
        </Button>

        {/* Google Calendar — based on viewer's own connections */}
        {syncStatus?.google?.synced ? (
          <Button variant="outline" size="sm" className="text-emerald-700 border-emerald-300 h-9 text-xs gap-1.5" disabled data-testid="google-synced-btn">
            {syncStatus.google.sync_source === 'auto' ? <Zap className="w-3.5 h-3.5" /> : <Check className="w-3.5 h-3.5" />}
            Google
          </Button>
        ) : syncStatus?.google?.out_of_sync ? (
          <Button variant="outline" size="sm" className="text-amber-700 border-amber-300 h-9 text-xs gap-1.5" onClick={() => onSyncCalendar('google')} disabled={syncingProvider !== null} data-testid="google-out-of-sync-btn">
            {syncingProvider === 'google' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <AlertTriangle className="w-3.5 h-3.5" />}
            Google
          </Button>
        ) : syncStatus?.google?.has_connection && !isCancelled ? (
          <Button variant="outline" size="sm" onClick={() => onSyncCalendar('google')} disabled={syncingProvider !== null} className="h-9 text-xs gap-1.5" data-testid="sync-google-btn">
            {syncingProvider === 'google' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Calendar className="w-3.5 h-3.5" />}
            Google
          </Button>
        ) : null}

        {/* Outlook Calendar — based on viewer's own connections */}
        {syncStatus?.outlook?.synced ? (
          <Button variant="outline" size="sm" className="text-emerald-700 border-emerald-300 h-9 text-xs gap-1.5" disabled data-testid="outlook-synced-btn">
            {syncStatus.outlook.sync_source === 'auto' ? <Zap className="w-3.5 h-3.5" /> : <Check className="w-3.5 h-3.5" />}
            Outlook
          </Button>
        ) : syncStatus?.outlook?.out_of_sync ? (
          <Button variant="outline" size="sm" className="text-amber-700 border-amber-300 h-9 text-xs gap-1.5" onClick={() => onSyncCalendar('outlook')} disabled={syncingProvider !== null} data-testid="outlook-out-of-sync-btn">
            {syncingProvider === 'outlook' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <AlertTriangle className="w-3.5 h-3.5" />}
            Outlook
          </Button>
        ) : syncStatus?.outlook?.has_connection && !isCancelled ? (
          <Button variant="outline" size="sm" onClick={() => onSyncCalendar('outlook')} disabled={syncingProvider !== null} className="h-9 text-xs gap-1.5" data-testid="sync-outlook-btn">
            {syncingProvider === 'outlook' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Calendar className="w-3.5 h-3.5" />}
            Outlook
          </Button>
        ) : null}
      </div>

      {/* Cancel — organizer cancels the whole appointment (hidden after start) */}
      {isOrganizer && !isCancelled && !isStarted && (
        <button
          onClick={onShowCancelModal}
          className="flex items-center gap-1.5 text-xs text-red-500 hover:text-red-700 font-medium py-1.5 transition-colors min-h-[44px]"
          data-testid="cancel-appointment-btn"
        >
          <Ban className="w-3.5 h-3.5" />
          Annuler l'engagement
        </button>
      )}

      {/* Cancel participation — participant leaves */}
      {canCancelParticipation && (
        confirmCancel ? (
          <div className="flex items-center gap-2 py-1.5">
            <span className="text-xs text-red-600 font-medium">Annuler votre participation ?</span>
            <button onClick={handleCancelParticipation} disabled={cancellingParticipation} className="px-2 py-1 text-xs font-bold text-white bg-red-600 rounded hover:bg-red-700 transition-colors disabled:opacity-50" data-testid="confirm-cancel-participation">Oui</button>
            <button onClick={() => setConfirmCancel(false)} className="px-2 py-1 text-xs font-medium text-slate-600 bg-slate-100 rounded hover:bg-slate-200 transition-colors" data-testid="cancel-cancel-participation">Non</button>
          </div>
        ) : (
          <button
            onClick={handleCancelParticipation}
            disabled={cancellingParticipation}
            className="flex items-center gap-1.5 text-xs text-red-500 hover:text-red-700 font-medium py-1.5 transition-colors min-h-[44px] disabled:opacity-50"
            data-testid="cancel-participation-btn"
          >
            {cancellingParticipation
              ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
              : <LogOut className="w-3.5 h-3.5" />
            }
            Annuler ma participation
          </button>
        )
      )}
      {cancelParticipationDisabled && (
        <span title="Le délai d'annulation est dépassé">
          <button
            disabled
            className="flex items-center gap-1.5 text-xs text-slate-400 font-medium py-1.5 min-h-[44px] cursor-not-allowed"
            data-testid="cancel-participation-btn-disabled"
          >
            <LogOut className="w-3.5 h-3.5" />
            Annuler ma participation
          </button>
        </span>
      )}
    </div>
  );
}
