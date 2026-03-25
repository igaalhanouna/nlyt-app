import React from 'react';
import { Button } from '../../components/ui/button';
import { Ban, Download, Calendar, Check, Zap, Loader2, AlertTriangle } from 'lucide-react';

export default function QuickActions({
  appointment, isCancelled, syncStatus, syncingProvider,
  onSyncCalendar, onDownloadICS, onShowCancelModal,
}) {
  return (
    <div className={`mb-4 ${isCancelled ? 'opacity-60' : ''}`} data-testid="quick-actions">
      {/* Calendar + ICS — compact inline */}
      <div className="flex flex-wrap gap-2 mb-2">
        <Button variant="outline" size="sm" onClick={onDownloadICS} className="gap-1.5 h-9 text-xs" data-testid="download-ics-btn">
          <Download className="w-3.5 h-3.5" /> .ics
        </Button>

        {/* Google Calendar */}
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

        {/* Outlook Calendar */}
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

      {/* Cancel — ghost red, visible but secondary */}
      {!isCancelled && (
        <button
          onClick={onShowCancelModal}
          className="flex items-center gap-1.5 text-xs text-red-500 hover:text-red-700 font-medium py-1.5 transition-colors min-h-[44px]"
          data-testid="cancel-appointment-btn"
        >
          <Ban className="w-3.5 h-3.5" />
          Annuler l'engagement
        </button>
      )}
    </div>
  );
}
