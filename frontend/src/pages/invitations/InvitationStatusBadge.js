import React from 'react';
import { Clock, Check, X, Ban, ShieldCheck, CreditCard, AlertTriangle } from 'lucide-react';

export default function InvitationStatusBadge({ status, guaranteeRevalidation }) {
  if (guaranteeRevalidation?.requires_revalidation && status === 'accepted_guaranteed') {
    return (
      <span className="inline-flex items-center gap-1 px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-sm font-medium" data-testid="status-badge-revalidation">
        <AlertTriangle className="w-4 h-4" /> À reconfirmer
      </span>
    );
  }

  switch (status) {
    case 'accepted_guaranteed':
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium" data-testid="status-badge-guaranteed">
          <ShieldCheck className="w-4 h-4" /> Garanti
        </span>
      );
    case 'accepted_pending_guarantee':
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-sm font-medium" data-testid="status-badge-pending-guarantee">
          <CreditCard className="w-4 h-4" /> Garantie en cours
        </span>
      );
    case 'accepted':
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium" data-testid="status-badge-accepted">
          <Check className="w-4 h-4" /> Accepté
        </span>
      );
    case 'declined':
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 bg-red-100 text-red-800 rounded-full text-sm font-medium" data-testid="status-badge-declined">
          <X className="w-4 h-4" /> Refusé
        </span>
      );
    case 'cancelled_by_participant':
    case 'guarantee_released':
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 bg-orange-100 text-orange-800 rounded-full text-sm font-medium" data-testid="status-badge-cancelled">
          <Ban className="w-4 h-4" /> Participation annulée
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-sm font-medium" data-testid="status-badge-invited">
          <Clock className="w-4 h-4" /> En attente
        </span>
      );
  }
}
