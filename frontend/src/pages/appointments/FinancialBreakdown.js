import React from 'react';
import { Heart } from 'lucide-react';

export default function FinancialBreakdown({ appointment, isCancelled }) {
  return (
    <div className={`bg-white border border-slate-200 rounded-xl p-4 mb-4 ${isCancelled ? 'opacity-60' : ''}`} data-testid="financial-breakdown">
      <p className="text-sm font-semibold text-slate-900 mb-3">Répartition</p>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-slate-600">Compensation participants</span>
          <span className="font-medium text-slate-900 tabular-nums">{appointment.affected_compensation_percent}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-600">Commission plateforme</span>
          <span className="font-medium text-slate-900 tabular-nums">{appointment.platform_commission_percent}%</span>
        </div>
        {appointment.charity_percent > 0 && (
          <div className="flex justify-between">
            <span className="text-slate-600">Don caritatif</span>
            <span className="font-medium text-slate-900 tabular-nums">{appointment.charity_percent}%</span>
          </div>
        )}
      </div>
      {appointment.charity_percent > 0 && appointment.charity_association_id && (
        <div className="flex items-center gap-2.5 mt-3 pt-3 border-t border-slate-100" data-testid="charity-association-block">
          <Heart className="w-4 h-4 text-teal-600 flex-shrink-0" />
          <div className="text-sm">
            <span className="font-medium text-teal-800">{appointment.charity_association_name || 'Association sélectionnée'}</span>
            <span className="text-teal-600"> · {appointment.charity_percent}% reversé</span>
          </div>
        </div>
      )}
    </div>
  );
}
