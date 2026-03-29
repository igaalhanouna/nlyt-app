import React, { useState } from 'react';
import { Button } from '../../components/ui/button';
import { Ban, Download, Calendar, Check, Zap, Loader2, AlertTriangle, LogOut } from 'lucide-react';
import { invitationAPI } from '../../services/api';
import { toast } from 'sonner';

export default function QuickActions({
  appointment, isCancelled, syncStatus, syncingProvider,
  onSyncCalendar, onDownloadICS, onShowCancelModal,
  isOrganizer = true,
  viewerInvitationToken,
  viewerParticipantStatus,
  onParticipantCancelComplete,
}) {
  const [cancellingParticipation, setCancellingParticipation] = useState(false);

  const canCancelParticipation = !isOrganizer
    && ['accepted', 'accepted_guaranteed'].includes(viewerParticipantStatus)
    && !isCancelled;

  const handleCancelParticipation = async () => {
    if (!viewerInvitationToken) return;
    if (!window.confirm('Annuler votre participation ? Cette action est irréversible si le délai d\'annulation est respecté.')) return;
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

        {/* Google Calendar — organizer only */}
        {isOrganizer && syncStatus?.google?.synced ? (
          <Button variant="outline" size="sm" className="text-emerald-700 border-emerald-300 h-9 text-xs gap-1.5" disabled data-testid="google-synced-btn">
            {syncStatus.google.sync_source === 'auto' ? <Zap className="w-3.5 h-3.5" /> : <Check className="w-3.5 h-3.5" />}
            Google
          </Button>
        ) : isOrganizer && syncStatus?.google?.out_of_sync ? (
          <Button variant="outline" size="sm" className="text-amber-700 border-amber-300 h-9 text-xs gap-1.5" onClick={() => onSyncCalendar('google')} disabled={syncingProvider !== null} data-testid="google-out-of-sync-btn">
            {syncingProvider === 'google' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <AlertTriangle className="w-3.5 h-3.5" />}
            Google
          </Button>
        ) : isOrganizer && syncStatus?.google?.has_connection && !isCancelled ? (
          <Button variant="outline" size="sm" onClick={() => onSyncCalendar('google')} disabled={syncingProvider !== null} className="h-9 text-xs gap-1.5" data-testid="sync-google-btn">
            {syncingProvider === 'google' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Calendar className="w-3.5 h-3.5" />}
            Google
          </Button>
        ) : null}

        {/* Outlook Calendar — organizer only */}
        {isOrganizer && syncStatus?.outlook?.synced ? (
          <Button variant="outline" size="sm" className="text-emerald-700 border-emerald-300 h-9 text-xs gap-1.5" disabled data-testid="outlook-synced-btn">
            {syncStatus.outlook.sync_source === 'auto' ? <Zap className="w-3.5 h-3.5" /> : <Check className="w-3.5 h-3.5" />}
            Outlook
          </Button>
        ) : isOrganizer && syncStatus?.outlook?.out_of_sync ? (
          <Button variant="outline" size="sm" className="text-amber-700 border-amber-300 h-9 text-xs gap-1.5" onClick={() => onSyncCalendar('outlook')} disabled={syncingProvider !== null} data-testid="outlook-out-of-sync-btn">
            {syncingProvider === 'outlook' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <AlertTriangle className="w-3.5 h-3.5" />}
            Outlook
          </Button>
        ) : isOrganizer && syncStatus?.outlook?.has_connection && !isCancelled ? (
          <Button variant="outline" size="sm" onClick={() => onSyncCalendar('outlook')} disabled={syncingProvider !== null} className="h-9 text-xs gap-1.5" data-testid="sync-outlook-btn">
            {syncingProvider === 'outlook' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Calendar className="w-3.5 h-3.5" />}
            Outlook
          </Button>
        ) : null}
      </div>

      {/* Cancel — organizer cancels the whole appointment */}
      {isOrganizer && !isCancelled && (
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
      )}
    </div>
  );
}
