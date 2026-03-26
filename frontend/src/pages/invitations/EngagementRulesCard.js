import React from 'react';
import { AlertTriangle } from 'lucide-react';

export default function EngagementRulesCard({ engagementRules }) {
  return (
    <div className="p-6 bg-amber-50 border-b border-amber-100" data-testid="engagement-rules">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-6 h-6 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <h3 className="font-semibold text-amber-800 mb-2">Règles d'engagement</h3>
          <ul className="space-y-2 text-sm text-amber-700">
            <li>
              <strong>Délai de désengagement :</strong> {engagementRules.cancellation_deadline_hours}h avant l'engagement
              {engagementRules.cancellation_deadline_formatted && (
                <span className="block text-xs mt-0.5">
                  (Limite : {engagementRules.cancellation_deadline_formatted})
                </span>
              )}
            </li>
            {engagementRules.tolerated_delay_minutes > 0 && (
              <li>
                <strong>Dépassement toléré :</strong> {engagementRules.tolerated_delay_minutes} minutes
              </li>
            )}
            <li>
              <strong>Compensation en cas d'absence :</strong> {engagementRules.penalty_amount} {engagementRules.penalty_currency}
            </li>
            <li>
              <strong>Répartition :</strong> {engagementRules.affected_compensation_percent}% aux participants affectés, {engagementRules.platform_commission_percent}% commission plateforme
              {engagementRules.charity_percent > 0 && (
                <>, {engagementRules.charity_percent}% {engagementRules.charity_association_name ? `pour ${engagementRules.charity_association_name}` : 'pour une association'}</>
              )}
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
