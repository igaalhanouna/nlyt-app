import React from 'react';
import { AlertTriangle, CreditCard, Loader2 } from 'lucide-react';

export default function GuaranteeRevalidationBanner({ guaranteeRevalidation, onReconfirm, reconfirming }) {
  return (
    <div className="p-5 bg-amber-50 border-b-2 border-amber-300" data-testid="guarantee-revalidation-banner">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 bg-amber-100 rounded-full flex items-center justify-center flex-shrink-0">
          <AlertTriangle className="w-5 h-5 text-amber-600" />
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-amber-900 mb-1">Garantie à reconfirmer</h3>
          <p className="text-sm text-amber-800 mb-3">
            Les conditions de l'engagement ont changé de manière significative. Veuillez reconfirmer votre garantie.
          </p>
          <div className="flex flex-wrap gap-2 mb-3">
            {(guaranteeRevalidation.reason || '').split(', ').map((r, i) => {
              let label = r;
              if (r.includes('city_change')) label = 'Changement de ville';
              else if (r.includes('date_shift')) label = 'Décalage de date > 24h';
              else if (r.includes('type_change')) label = 'Changement de type';
              return (
                <span key={i} className="text-xs bg-amber-200 text-amber-900 px-2 py-1 rounded-full font-medium" data-testid={`revalidation-reason-${i}`}>
                  {label}
                </span>
              );
            })}
          </div>
          <button
            onClick={onReconfirm}
            disabled={reconfirming}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors font-semibold text-sm disabled:opacity-50"
            data-testid="reconfirm-guarantee-btn"
          >
            {reconfirming ? <Loader2 className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
            Reconfirmer ma garantie
          </button>
        </div>
      </div>
    </div>
  );
}
