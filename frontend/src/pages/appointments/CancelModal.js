import React from 'react';
import { Button } from '../../components/ui/button';
import { AlertTriangle } from 'lucide-react';

export default function CancelModal({ show, onClose, onConfirm, cancelling, participantCount }) {
  if (!show) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => !cancelling && onClose()}>
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="bg-red-50 p-4 flex items-center gap-3 border-b border-red-100">
          <div className="p-2 bg-red-100 rounded-full">
            <AlertTriangle className="w-6 h-6 text-red-600" />
          </div>
          <h3 className="text-lg font-semibold text-red-800">Annuler l'engagement</h3>
        </div>
        <div className="p-5">
          <p className="text-slate-700 mb-3 text-sm">Voulez-vous vraiment annuler cet engagement ?</p>
          <ul className="text-sm text-slate-600 space-y-2 mb-5">
            <li className="flex items-start gap-2"><span className="text-red-500">•</span>Les {participantCount} participant(s) seront immédiatement notifié(s) par email.</li>
            <li className="flex items-start gap-2"><span className="text-red-500">•</span>L'engagement sera conservé dans l'historique avec le statut "Annulé".</li>
            <li className="flex items-start gap-2"><span className="text-red-500">•</span>Les invitations ne pourront plus être acceptées.</li>
          </ul>
        </div>
        <div className="flex flex-col-reverse sm:flex-row gap-2 sm:gap-3 p-4 bg-slate-50 border-t border-slate-100">
          <Button variant="outline" onClick={onClose} disabled={cancelling} className="flex-1 min-h-[44px] sm:min-h-0">Retour</Button>
          <Button onClick={onConfirm} disabled={cancelling} className="flex-1 bg-red-600 hover:bg-red-700 text-white min-h-[44px] sm:min-h-0" data-testid="confirm-cancel-btn">
            {cancelling ? 'Annulation...' : "Confirmer l'annulation"}
          </Button>
        </div>
      </div>
    </div>
  );
}
