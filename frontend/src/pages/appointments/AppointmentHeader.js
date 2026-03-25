import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { Ban, Check, MapPin, ArrowRight, Loader2, CreditCard, AlertTriangle, Settings2, Shield } from 'lucide-react';

const STATUS_STYLES = {
  active: 'bg-emerald-100 text-emerald-800',
  cancelled: 'bg-red-100 text-red-800',
  pending_organizer_guarantee: 'bg-amber-100 text-amber-800',
  draft: 'bg-slate-100 text-slate-800',
};
const STATUS_LABELS = {
  active: 'Actif',
  cancelled: 'Annulé',
  pending_organizer_guarantee: 'En attente de garantie',
  draft: 'Brouillon',
};

export default function AppointmentHeader({
  appointment, isCancelled, isPendingGuarantee,
  organizerParticipant, organizerCheckinDone, checkingIn,
  handleOrganizerCheckin, handleResumeGuarantee, resumingGuarantee,
  handleCheckActivation, checkingActivation, navigate,
}) {
  const canCheckin = organizerParticipant?.status === 'accepted_guaranteed' && !isCancelled && !isPendingGuarantee;
  const isVideo = appointment.appointment_type === 'video';
  const proofLink = organizerParticipant?.invitation_token
    ? `/proof/${appointment.appointment_id}?token=${organizerParticipant.invitation_token}`
    : null;

  return (
    <div className="mb-4">
      {/* Cancelled banner */}
      {isCancelled && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 flex items-center gap-3" data-testid="cancelled-banner">
          <Ban className="w-5 h-5 text-red-600 flex-shrink-0" />
          <div>
            <p className="font-semibold text-red-800 text-sm">Engagement annulé</p>
            <p className="text-xs text-red-600">Les participants ont été notifiés.</p>
          </div>
        </div>
      )}

      {/* Title + Badge */}
      <div className="mb-3">
        <h1 className={`text-xl sm:text-2xl font-bold mb-1.5 ${isCancelled ? 'text-slate-400 line-through' : 'text-slate-900'}`} data-testid="appointment-title">
          {appointment.title}
        </h1>
        <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[appointment.status] || 'bg-slate-100 text-slate-600'}`} data-testid="appointment-status-badge">
          {STATUS_LABELS[appointment.status] || appointment.status}
        </span>
      </div>

      {/* Pending guarantee banner */}
      {isPendingGuarantee && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-3" data-testid="pending-guarantee-banner">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-amber-900 text-sm">En attente de votre garantie</p>
              <p className="text-xs text-amber-800 mt-1">Les invitations seront envoyées après validation.</p>
              <div className="flex flex-col gap-2 mt-2.5">
                <Button size="sm" onClick={handleResumeGuarantee} disabled={resumingGuarantee} className="bg-amber-600 hover:bg-amber-700 h-10" data-testid="banner-resume-guarantee-btn">
                  {resumingGuarantee ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <CreditCard className="w-4 h-4 mr-2" />}
                  Compléter ma garantie
                </Button>
                <Button size="sm" variant="outline" onClick={() => navigate('/settings/payment')} className="h-10" data-testid="banner-settings-btn">
                  <Settings2 className="w-4 h-4 mr-2" />
                  Configurer une carte par défaut
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Dynamic CTA */}
      {canCheckin && (
        <div className="space-y-2">
          {!organizerCheckinDone ? (
            isVideo && proofLink ? (
              <a href={proofLink} className="block" data-testid="organizer-proof-link">
                <Button className="w-full h-12 bg-slate-900 hover:bg-slate-800 text-white font-semibold text-base gap-2">
                  <Shield className="w-4 h-4" />
                  Confirmer ma présence
                </Button>
              </a>
            ) : (
              <Button onClick={handleOrganizerCheckin} disabled={checkingIn} className="w-full h-12 bg-slate-900 hover:bg-slate-800 text-white font-semibold text-base gap-2" data-testid="organizer-manual-checkin-btn">
                {checkingIn ? <Loader2 className="w-4 h-4 animate-spin" /> : <><MapPin className="w-4 h-4" /><Check className="w-4 h-4" /></>}
                Check-in avec GPS
              </Button>
            )
          ) : (
            <>
              <div className="flex items-center gap-2 px-3 py-2 bg-emerald-50 border border-emerald-200 rounded-lg" data-testid="checkin-confirmed-badge">
                <Check className="w-4 h-4 text-emerald-600" />
                <span className="text-sm font-medium text-emerald-700">Présence confirmée</span>
              </div>
              {isVideo && appointment.meeting_join_url && (
                <a href={proofLink || appointment.meeting_join_url} target={proofLink ? '_self' : '_blank'} rel="noopener noreferrer" className="block">
                  <Button variant="outline" className="w-full h-11 border-blue-300 text-blue-700 hover:bg-blue-50 font-semibold gap-2" data-testid="join-meeting-btn">
                    <ArrowRight className="w-4 h-4" />
                    Rejoindre la réunion
                  </Button>
                </a>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
