import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { appointmentAPI, participantAPI, invitationAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../../components/ui/dialog';
import { ArrowLeft, UserPlus, Mail, Trash2, RefreshCw, CheckCircle, Clock, XCircle, ShieldCheck, CreditCard } from 'lucide-react';
import { toast } from 'sonner';
import { formatDateTimeCompactFr } from '../../utils/dateFormat';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';

export default function ParticipantManagement() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [appointment, setAppointment] = useState(null);
  const [participants, setParticipants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  
  const [newParticipant, setNewParticipant] = useState({
    first_name: '',
    last_name: '',
    email: '',
    role: 'participant'
  });

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

  const handleAddParticipant = async () => {
    if (!newParticipant.email || !newParticipant.first_name || !newParticipant.last_name) {
      toast.error('Tous les champs sont requis');
      return;
    }

    try {
      await participantAPI.add(id, newParticipant);
      toast.success('Participant ajouté et invité');
      setNewParticipant({ first_name: '', last_name: '', email: '', role: 'participant' });
      setIsAddDialogOpen(false);
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Erreur lors de l\'ajout');
    }
  };

  const [resendingToken, setResendingToken] = useState(null);

  const handleResendInvitation = async (token) => {
    setResendingToken(token);
    try {
      await invitationAPI.resend(token);
      toast.success('Invitation renvoyée avec succès');
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erreur lors du renvoi de l'invitation");
    } finally {
      setResendingToken(null);
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      invited: { label: 'Invité', icon: Clock, className: 'bg-blue-100 text-blue-800' },
      accepted: { label: 'Accepté', icon: CheckCircle, className: 'bg-emerald-100 text-emerald-800' },
      accepted_guaranteed: { label: 'Garanti', icon: ShieldCheck, className: 'bg-emerald-100 text-emerald-800' },
      accepted_pending_guarantee: { label: 'Garantie en cours', icon: CreditCard, className: 'bg-amber-100 text-amber-800' },
      declined: { label: 'Refusé', icon: XCircle, className: 'bg-rose-100 text-rose-800' },
      cancelled_by_participant: { label: 'Participation annulée', icon: XCircle, className: 'bg-orange-100 text-orange-800' },
      guarantee_released: { label: 'Participation annulée', icon: XCircle, className: 'bg-orange-100 text-orange-800' },
    };

    const config = statusConfig[status] || statusConfig.invited;
    const Icon = config.icon;

    return (
      <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${config.className}`}>
        <Icon className="w-3 h-3" />
        {config.label}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: appointment?.title || 'Engagement', href: `/appointments/${id}` },
        { label: 'Participants' },
      ]} />

      <div className="max-w-6xl mx-auto px-4 md:px-6 pb-12">
        <Link to={`/appointments/${id}`}>
          <Button variant="ghost" className="mb-4" size="sm">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Retour à l'engagement
          </Button>
        </Link>

        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900 mb-2" data-testid="participants-title">
            Gestion des participants
          </h1>
          <p className="text-slate-600">{appointment?.title}</p>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-4 md:p-6 mb-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
            <div>
              <h2 className="text-lg sm:text-xl font-semibold text-slate-900">Gestion des participants ({participants.length})</h2>
              <p className="text-sm text-slate-600 mt-1">
                Invitez les participants à cet engagement
              </p>
            </div>
            
            <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
              <DialogTrigger asChild>
                <Button data-testid="add-participant-btn" className="w-full sm:w-auto min-h-[44px] sm:min-h-0">
                  <UserPlus className="w-4 h-4 mr-2" />
                  Ajouter un participant
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Ajouter un participant</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 mt-4">
                  <div>
                    <Label htmlFor="first_name">Prénom *</Label>
                    <Input
                      id="first_name"
                      data-testid="participant-firstname-input"
                      value={newParticipant.first_name}
                      onChange={(e) => setNewParticipant({ ...newParticipant, first_name: e.target.value })}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="last_name">Nom *</Label>
                    <Input
                      id="last_name"
                      data-testid="participant-lastname-input"
                      value={newParticipant.last_name}
                      onChange={(e) => setNewParticipant({ ...newParticipant, last_name: e.target.value })}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="email">Email *</Label>
                    <Input
                      id="email"
                      type="email"
                      data-testid="participant-email-input"
                      value={newParticipant.email}
                      onChange={(e) => setNewParticipant({ ...newParticipant, email: e.target.value })}
                      className="mt-1"
                    />
                  </div>
                  <div className="flex gap-2 sm:gap-3 pt-4">
                    <Button
                      variant="outline"
                      onClick={() => setIsAddDialogOpen(false)}
                      className="flex-1 min-h-[44px] sm:min-h-0"
                    >
                      Annuler
                    </Button>
                    <Button
                      onClick={handleAddParticipant}
                      className="flex-1 min-h-[44px] sm:min-h-0"
                      data-testid="participant-submit-btn"
                    >
                      Inviter
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          {participants.length === 0 ? (
            <div className="text-center py-12 border-2 border-dashed border-slate-200 rounded-lg">
              <UserPlus className="w-16 h-16 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-600 mb-4">Aucun participant pour le moment</p>
              <Button onClick={() => setIsAddDialogOpen(true)} variant="outline">
                Ajouter le premier participant
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {participants.map((participant) => (
                <div
                  key={participant.participant_id}
                  className="p-4 border border-slate-200 rounded-lg hover:border-slate-300 transition-colors"
                  data-testid={`participant-card-${participant.participant_id}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <h3 className="font-semibold text-slate-900">
                          {participant.first_name} {participant.last_name}
                        </h3>
                        {getStatusBadge(participant.status)}
                      </div>
                      <p className="text-sm text-slate-600 truncate">{participant.email}</p>
                      {participant.invited_at && (
                        <p className="text-xs text-slate-500 mt-1">
                          Invité le {formatDateTimeCompactFr(participant.invited_at)}
                        </p>
                      )}
                      {participant.accepted_at && (
                        <p className="text-xs text-emerald-600 mt-1">
                          Accepté le {formatDateTimeCompactFr(participant.accepted_at)}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      {participant.status === 'invited' && (
                        <Button
                          size="sm"
                          variant="ghost"
                          title="Renvoyer l'invitation"
                          data-testid={`resend-btn-${participant.participant_id}`}
                          disabled={resendingToken === participant.invitation_token}
                          onClick={() => handleResendInvitation(participant.invitation_token)}
                        >
                          <RefreshCw className={`w-4 h-4 ${resendingToken === participant.invitation_token ? 'animate-spin' : ''}`} />
                        </Button>
                      )}
                      {participant.status !== 'accepted' && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                          title="Supprimer"
                          data-testid={`remove-btn-${participant.participant_id}`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-center">
          <Button onClick={() => navigate(`/appointments/${id}`)} data-testid="back-to-appointment-btn" className="w-full sm:w-auto min-h-[44px] sm:min-h-0">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Retour à l'engagement
          </Button>
        </div>
      </div>
    </div>
  );
}
