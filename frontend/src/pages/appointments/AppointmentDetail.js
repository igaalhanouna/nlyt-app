import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { appointmentAPI, participantAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { ArrowLeft, Calendar, MapPin, Video, Clock, Users, Ban, Check, X, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

export default function AppointmentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [appointment, setAppointment] = useState(null);
  const [participants, setParticipants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    loadData();
  }, [id]);

  const loadData = async () => {
    try {
      const [appointmentRes, participantsRes] = await Promise.all([
        appointmentAPI.get(id),
        participantAPI.list(id)
      ]);
      setAppointment(appointmentRes.data);
      setParticipants(participantsRes.data.participants || []);
    } catch (error) {
      toast.error('Erreur lors du chargement');
    } finally {
      setLoading(false);
    }
  };

  const handleCancelAppointment = async () => {
    try {
      setCancelling(true);
      const response = await appointmentAPI.cancel(id);
      toast.success(`Rendez-vous annulé. ${response.data.participants_notified} participant(s) notifié(s).`);
      setShowCancelModal(false);
      // Reload data to show updated status
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Erreur lors de l\'annulation');
    } finally {
      setCancelling(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900"></div>
      </div>
    );
  }

  if (!appointment) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-600 mb-4">Rendez-vous introuvable</p>
          <Button onClick={() => navigate('/dashboard')}>Retour au tableau de bord</Button>
        </div>
      </div>
    );
  }

  const acceptedCount = participants.filter(p => p.status === 'accepted').length;
  const pendingCount = participants.filter(p => p.status === 'invited').length;
  const isCancelled = appointment.status === 'cancelled';

  // Status badge helper
  const getParticipantStatusBadge = (status) => {
    switch (status) {
      case 'accepted':
        return <span className="inline-flex items-center gap-1 px-2 py-1 bg-emerald-100 text-emerald-800 rounded-full text-xs font-medium"><Check className="w-3 h-3" /> Accepté</span>;
      case 'declined':
        return <span className="inline-flex items-center gap-1 px-2 py-1 bg-red-100 text-red-800 rounded-full text-xs font-medium"><X className="w-3 h-3" /> Refusé</span>;
      case 'cancelled_by_participant':
        return <span className="inline-flex items-center gap-1 px-2 py-1 bg-orange-100 text-orange-800 rounded-full text-xs font-medium"><Ban className="w-3 h-3" /> Annulé</span>;
      default:
        return <span className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-medium"><Clock className="w-3 h-3" /> Invité</span>;
    }
  };

  return (
    <div className="min-h-screen bg-background py-8 px-4">
      <div className="max-w-6xl mx-auto">
        <Link to="/dashboard">
          <Button variant="ghost" className="mb-6">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Retour au tableau de bord
          </Button>
        </Link>

        {/* Cancelled Banner */}
        {isCancelled && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 flex items-center gap-3">
            <Ban className="w-6 h-6 text-red-600" />
            <div>
              <p className="font-semibold text-red-800">Ce rendez-vous a été annulé</p>
              <p className="text-sm text-red-600">
                Les participants ont été notifiés. Ce rendez-vous n'aura pas lieu.
              </p>
            </div>
          </div>
        )}

        <div className="mb-6 flex items-start justify-between">
          <div>
            <h1 className={`text-3xl font-bold mb-2 ${isCancelled ? 'text-slate-400 line-through' : 'text-slate-900'}`} data-testid="appointment-title">
              {appointment.title}
            </h1>
            <span className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${
              appointment.status === 'active' ? 'bg-emerald-100 text-emerald-800' :
              appointment.status === 'cancelled' ? 'bg-red-100 text-red-800' :
              appointment.status === 'draft' ? 'bg-slate-100 text-slate-800' :
              'bg-slate-100 text-slate-600'
            }`}>
              {appointment.status === 'active' ? 'Actif' : 
               appointment.status === 'cancelled' ? 'Annulé' :
               appointment.status === 'draft' ? 'Brouillon' : appointment.status}
            </span>
          </div>
          <div className="flex gap-2">
            {!isCancelled && (
              <>
                <Link to={`/appointments/${id}/participants`}>
                  <Button variant="outline">
                    <Users className="w-4 h-4 mr-2" />
                    Gérer les participants
                  </Button>
                </Link>
                <Button 
                  variant="outline" 
                  className="text-red-600 border-red-300 hover:bg-red-50"
                  onClick={() => setShowCancelModal(true)}
                  data-testid="cancel-appointment-btn"
                >
                  <Ban className="w-4 h-4 mr-2" />
                  Annuler le rendez-vous
                </Button>
              </>
            )}
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-6 mb-6">
          <div className={`bg-white p-6 rounded-lg border ${isCancelled ? 'border-slate-200 opacity-60' : 'border-slate-200'}`}>
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Users className="w-5 h-5 text-blue-700" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">{participants.length}</p>
                <p className="text-sm text-slate-600">Participants</p>
              </div>
            </div>
            <div className="text-xs text-slate-500">
              {acceptedCount} accepté(s), {pendingCount} en attente
            </div>
          </div>

          <div className={`bg-white p-6 rounded-lg border ${isCancelled ? 'border-slate-200 opacity-60' : 'border-slate-200'}`}>
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-emerald-100 rounded-lg">
                <Clock className="w-5 h-5 text-emerald-700" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">{appointment.tolerated_delay_minutes}</p>
                <p className="text-sm text-slate-600">Minutes de retard</p>
              </div>
            </div>
            <div className="text-xs text-slate-500">Tolérance autorisée</div>
          </div>

          <div className={`bg-white p-6 rounded-lg border ${isCancelled ? 'border-slate-200 opacity-60' : 'border-slate-200'}`}>
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-amber-100 rounded-lg">
                <Calendar className="w-5 h-5 text-amber-700" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">{appointment.cancellation_deadline_hours}h</p>
                <p className="text-sm text-slate-600">Délai d'annulation</p>
              </div>
            </div>
            <div className="text-xs text-slate-500">Avant pénalité</div>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className={`bg-white rounded-lg border p-6 ${isCancelled ? 'border-slate-200 opacity-60' : 'border-slate-200'}`}>
            <h2 className="text-lg font-semibold text-slate-900 mb-4">Informations générales</h2>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <Calendar className="w-5 h-5 text-slate-500 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-slate-700">Date et heure</p>
                  <p className="text-slate-900">
                    {new Date(appointment.start_datetime).toLocaleString('fr-FR', {
                      dateStyle: 'full',
                      timeStyle: 'short'
                    })}
                  </p>
                  <p className="text-sm text-slate-500 mt-1">Durée : {appointment.duration_minutes} minutes</p>
                </div>
              </div>

              {appointment.appointment_type === 'physical' && appointment.location && (
                <div className="flex items-start gap-3">
                  <MapPin className="w-5 h-5 text-slate-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-slate-700">Lieu</p>
                    <p className="text-slate-900">{appointment.location}</p>
                  </div>
                </div>
              )}

              {appointment.appointment_type === 'video' && appointment.meeting_provider && (
                <div className="flex items-start gap-3">
                  <Video className="w-5 h-5 text-slate-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-slate-700">Plateforme</p>
                    <p className="text-slate-900">{appointment.meeting_provider}</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className={`bg-white rounded-lg border p-6 ${isCancelled ? 'border-slate-200 opacity-60' : 'border-slate-200'}`}>
            <h2 className="text-lg font-semibold text-slate-900 mb-4">Conditions financières</h2>
            <div className="space-y-3">
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg">
                <p className="text-sm font-medium text-rose-900">Pénalité</p>
                <p className="text-2xl font-bold text-rose-900">
                  {appointment.penalty_amount} {appointment.penalty_currency.toUpperCase()}
                </p>
              </div>
              
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-600">Compensation participants</span>
                  <span className="font-medium text-slate-900">{appointment.affected_compensation_percent}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">Commission plateforme</span>
                  <span className="font-medium text-slate-900">{appointment.platform_commission_percent}%</span>
                </div>
                {appointment.charity_percent > 0 && (
                  <div className="flex justify-between">
                    <span className="text-slate-600">Don caritatif</span>
                    <span className="font-medium text-slate-900">{appointment.charity_percent}%</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {participants.length > 0 && (
          <div className={`bg-white rounded-lg border p-6 mt-6 ${isCancelled ? 'border-slate-200 opacity-60' : 'border-slate-200'}`}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900">Participants</h2>
              {!isCancelled && (
                <Link to={`/appointments/${id}/participants`}>
                  <Button variant="ghost" size="sm">
                    Voir tout
                  </Button>
                </Link>
              )}
            </div>
            <div className="space-y-2">
              {participants.slice(0, 5).map((participant) => (
                <div
                  key={participant.participant_id}
                  className="flex items-center justify-between p-3 border border-slate-200 rounded-lg"
                >
                  <div>
                    <p className="font-medium text-slate-900">
                      {participant.first_name} {participant.last_name}
                    </p>
                    <p className="text-sm text-slate-600">{participant.email}</p>
                  </div>
                  {getParticipantStatusBadge(participant.status)}
                </div>
              ))}
            </div>
            {participants.length > 5 && (
              <p className="text-sm text-slate-500 text-center mt-3">
                Et {participants.length - 5} autre(s) participant(s)
              </p>
            )}
          </div>
        )}
      </div>

      {/* Cancel Confirmation Modal */}
      {showCancelModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => !cancelling && setShowCancelModal(false)}>
          <div 
            className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            <div className="bg-red-50 p-4 flex items-center gap-3 border-b border-red-100">
              <div className="p-2 bg-red-100 rounded-full">
                <AlertTriangle className="w-6 h-6 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-red-800">Annuler le rendez-vous</h3>
            </div>
            
            <div className="p-6">
              <p className="text-slate-700 mb-4">
                Voulez-vous vraiment annuler ce rendez-vous ?
              </p>
              <ul className="text-sm text-slate-600 space-y-2 mb-6">
                <li className="flex items-start gap-2">
                  <span className="text-red-500">•</span>
                  Les {participants.length} participant(s) seront immédiatement notifié(s) par email.
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-red-500">•</span>
                  Le rendez-vous sera conservé dans l'historique avec le statut "Annulé".
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-red-500">•</span>
                  Les invitations ne pourront plus être acceptées.
                </li>
              </ul>
            </div>
            
            <div className="flex gap-3 p-4 bg-slate-50 border-t border-slate-100">
              <Button
                variant="outline"
                onClick={() => setShowCancelModal(false)}
                disabled={cancelling}
                className="flex-1"
              >
                Retour
              </Button>
              <Button
                onClick={handleCancelAppointment}
                disabled={cancelling}
                className="flex-1 bg-red-600 hover:bg-red-700 text-white"
                data-testid="confirm-cancel-btn"
              >
                {cancelling ? 'Annulation...' : 'Confirmer l\'annulation'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
