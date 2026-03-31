import React from 'react';
import { Check, X, Ban, Loader2, ShieldCheck, CreditCard, AlertTriangle, Download } from 'lucide-react';
import { formatActionDateFr } from '../../utils/dateFormat';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function InvitationResponseSection({
  responseStatus,
  participant,
  engagementRules,
  guaranteeRevalidation,
  guaranteeMessage,
  appointment,
  token,
  onResponse,
  responding,
  onCancelParticipation,
  cancelling,
  onReconfirmGuarantee,
  reconfirming,
}) {
  const renderCalendarDownload = () => (
    <div className="mt-6 pt-4 border-t border-slate-200">
      <a
        href={`${API_URL}/api/calendar/export/ics/${appointment.appointment_id}?token=${token}`}
        download
        className="inline-flex items-center gap-2 px-6 py-2 bg-slate-800 text-white rounded-lg hover:bg-slate-700 transition-colors font-medium"
        data-testid="download-ics-btn"
      >
        <Download className="w-4 h-4" />
        Autres calendriers (.ics)
      </a>
      <p className="text-xs text-slate-400 mt-2">
        Compatible avec Apple Calendar, Thunderbird et tout calendrier standard.
      </p>
    </div>
  );

  const renderCancelButton = () => {
    if (!engagementRules.can_cancel || engagementRules.cancellation_deadline_passed) return null;
    return (
      <div className="mt-6 pt-4 border-t border-slate-200">
        <p className="text-sm text-slate-500 mb-3">
          Vous pouvez annuler votre participation jusqu'au {engagementRules.cancellation_deadline_formatted}
        </p>
        <button
          onClick={onCancelParticipation}
          disabled={cancelling}
          className="px-6 py-2 border-2 border-orange-300 text-orange-700 rounded-lg hover:bg-orange-50 transition-colors font-medium disabled:opacity-50 flex items-center gap-2 mx-auto"
          data-testid="cancel-participation-btn"
        >
          {cancelling ? <Loader2 className="w-4 h-4 animate-spin" /> : <Ban className="w-4 h-4" />}
          Annuler ma participation
        </button>
      </div>
    );
  };

  return (
    <div className="p-6" data-testid="response-section">
      {/* Guarantee message banner */}
      {guaranteeMessage && (
        <div className={`mb-4 p-4 rounded-lg ${
          guaranteeMessage.type === 'success' ? 'bg-green-50 border border-green-200 text-green-800' :
          guaranteeMessage.type === 'warning' ? 'bg-amber-50 border border-amber-200 text-amber-800' :
          'bg-blue-50 border border-blue-200 text-blue-800'
        }`}>
          <div className="flex items-center gap-2">
            {guaranteeMessage.type === 'success' && <ShieldCheck className="w-5 h-5" />}
            {guaranteeMessage.type === 'warning' && <AlertTriangle className="w-5 h-5" />}
            {guaranteeMessage.type === 'info' && <Loader2 className="w-5 h-5 animate-spin" />}
            <p className="font-medium">{guaranteeMessage.text}</p>
          </div>
        </div>
      )}

      {/* Accepted with guarantee */}
      {responseStatus === 'accepted_guaranteed' ? (
        <div className="text-center py-4">
          {guaranteeRevalidation?.requires_revalidation ? (
            <>
              <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <AlertTriangle className="w-8 h-8 text-amber-600" />
              </div>
              <h3 className="text-xl font-semibold text-amber-800 mb-2" data-testid="guarantee-status-revalidation">Garantie à reconfirmer</h3>
              <p className="text-slate-600">Votre garantie doit être reconfirmée suite à un changement majeur de l'engagement.</p>
              <p className="text-xs text-amber-600 mt-2">
                Tant que vous n'avez pas reconfirmé, votre garantie est considérée comme partiellement invalide.
              </p>
            </>
          ) : (
            <>
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <ShieldCheck className="w-8 h-8 text-green-600" />
              </div>
              <h3 className="text-xl font-semibold text-green-800 mb-2" data-testid="guarantee-status-valid">Participation confirmée avec garantie !</h3>
              <p className="text-slate-600">Votre moyen de paiement a été enregistré comme garantie.</p>
              <p className="text-xs text-slate-500 mt-2">
                Aucun montant ne sera prélevé sauf en cas d'absence ou de retard excessif.
              </p>
            </>
          )}
          {participant.guaranteed_at && !guaranteeRevalidation?.requires_revalidation && (
            <p className="text-xs text-slate-400 mt-2">
              Garanti le {formatActionDateFr(participant.guaranteed_at)}
            </p>
          )}
          {renderCalendarDownload()}
          {renderCancelButton()}
        </div>
      ) : responseStatus === 'accepted_pending_guarantee' ? (
        <div className="text-center py-4">
          <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CreditCard className="w-8 h-8 text-amber-600" />
          </div>
          <h3 className="text-xl font-semibold text-amber-800 mb-2">Garantie en attente</h3>
          <p className="text-slate-600 mb-4">
            Vous avez accepté cette invitation mais la garantie financière n'est pas encore configurée.
          </p>
          <button
            onClick={() => onResponse('accept')}
            disabled={responding}
            className="px-8 py-3 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors font-medium disabled:opacity-50 flex items-center gap-2 mx-auto"
            data-testid="complete-guarantee-btn"
          >
            {responding ? <Loader2 className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
            Compléter la garantie
          </button>
        </div>
      ) : responseStatus === 'accepted' ? (
        <div className="text-center py-4">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Check className="w-8 h-8 text-green-600" />
          </div>
          <h3 className="text-xl font-semibold text-green-800 mb-2">Invitation acceptée !</h3>
          <p className="text-slate-600">Vous avez accepté cette invitation.</p>
          {participant.accepted_at && (
            <p className="text-xs text-slate-400 mt-2">
              Accepté le {formatActionDateFr(participant.accepted_at)}
            </p>
          )}
          {renderCalendarDownload()}
          {renderCancelButton()}
          {engagementRules.cancellation_deadline_passed && (
            <div className="mt-6 pt-4 border-t border-slate-200">
              <p className="text-sm text-orange-600 bg-orange-50 px-4 py-2 rounded-lg">
                Le délai d'annulation est dépassé. Vous ne pouvez plus annuler en ligne.
              </p>
            </div>
          )}
        </div>
      ) : responseStatus === 'declined' ? (
        <div className="text-center py-4">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <X className="w-8 h-8 text-red-600" />
          </div>
          <h3 className="text-xl font-semibold text-red-800 mb-2">Invitation déclinée</h3>
          <p className="text-slate-600">Vous avez décliné cette invitation. L'organisateur en sera informé.</p>
          {participant.declined_at && (
            <p className="text-xs text-slate-400 mt-2">
              Décliné le {formatActionDateFr(participant.declined_at)}
            </p>
          )}
        </div>
      ) : responseStatus === 'cancelled_by_participant' || responseStatus === 'guarantee_released' ? (
        <div className="text-center py-4">
          <div className="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Ban className="w-8 h-8 text-orange-600" />
          </div>
          <h3 className="text-xl font-semibold text-orange-800 mb-2">Vous avez annulé votre participation</h3>
          <p className="text-slate-600">L'organisateur en a été informé.</p>
          {participant.cancelled_at && (
            <p className="text-xs text-slate-400 mt-2">
              Annulé le {formatActionDateFr(participant.cancelled_at)}
            </p>
          )}
          <p className="text-xs text-slate-400 mt-1">Garantie libérée — aucune pénalité</p>
        </div>
      ) : (
        <div>
          <h3 className="font-semibold text-slate-800 mb-4 text-center">Votre réponse</h3>
          
          {engagementRules.penalty_amount > 0 && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
              <div className="flex items-start gap-3">
                <CreditCard className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-blue-800">Garantie financière requise</p>
                  <p className="text-sm text-blue-700 mt-1">
                    Pour confirmer votre participation, vous devrez enregistrer un moyen de paiement.
                    <strong> Aucun montant ne sera prélevé immédiatement.</strong>
                  </p>
                  <p className="text-xs text-blue-600 mt-2">
                    La compensation de {engagementRules.penalty_amount} {engagementRules.penalty_currency} ne sera prélevée 
                    qu'en cas d'absence ou de retard excessif.
                  </p>
                </div>
              </div>
            </div>
          )}
          
          <p className="text-sm text-slate-600 text-center mb-6">
            En acceptant, vous vous engagez à respecter les règles ci-dessus. 
            En cas de non-respect, la compensation définie sera appliquée.
          </p>
          <div className="flex gap-4 justify-center">
            <button
              onClick={() => onResponse('decline')}
              disabled={responding}
              className="px-8 py-3 border-2 border-slate-300 text-slate-700 rounded-xl hover:bg-slate-50 transition-colors font-medium disabled:opacity-50 flex items-center gap-2"
              data-testid="decline-btn"
            >
              {responding ? <Loader2 className="w-5 h-5 animate-spin" /> : <X className="w-5 h-5" />}
              Refuser
            </button>
            <button
              onClick={() => onResponse('accept')}
              disabled={responding}
              className="px-8 py-3 bg-green-600 text-white rounded-xl hover:bg-green-700 transition-colors font-medium disabled:opacity-50 flex items-center gap-2"
              data-testid="accept-btn"
            >
              {responding ? <Loader2 className="w-5 h-5 animate-spin" /> : <Check className="w-5 h-5" />}
              {engagementRules.penalty_amount > 0 ? 'Accepter et configurer la garantie' : 'Accepter'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
