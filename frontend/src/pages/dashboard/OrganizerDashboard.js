import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useWorkspace } from '../../contexts/WorkspaceContext';
import { useAuth } from '../../contexts/AuthContext';
import { appointmentAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { CalendarPlus, LogOut, Settings, Calendar, Users, MapPin, Video, Trash2, Check, X, Clock, Building2, ChevronDown, Plus, Ban, ShieldCheck, CreditCard } from 'lucide-react';
import { toast } from 'sonner';

export default function OrganizerDashboard() {
  const { user, logout } = useAuth();
  const { currentWorkspace, workspaces, selectWorkspace } = useWorkspace();
  const navigate = useNavigate();
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleteModal, setDeleteModal] = useState({ open: false, appointment: null });
  const [deleting, setDeleting] = useState(false);
  const [workspaceDropdownOpen, setWorkspaceDropdownOpen] = useState(false);

  useEffect(() => {
    if (currentWorkspace) {
      loadAppointments();
    }
  }, [currentWorkspace]);

  const loadAppointments = async () => {
    try {
      const response = await appointmentAPI.list(currentWorkspace.workspace_id);
      setAppointments(response.data.appointments || []);
    } catch (error) {
      toast.error('Erreur lors du chargement des rendez-vous');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteClick = (e, appointment) => {
    e.preventDefault(); // Prevent navigation to appointment detail
    e.stopPropagation();
    setDeleteModal({ open: true, appointment });
  };

  const handleConfirmDelete = async () => {
    if (!deleteModal.appointment) return;
    
    setDeleting(true);
    try {
      await appointmentAPI.delete(deleteModal.appointment.appointment_id);
      // Optimistic UI update - remove from list immediately
      setAppointments(prev => prev.filter(a => a.appointment_id !== deleteModal.appointment.appointment_id));
      toast.success('Rendez-vous supprimé avec succès');
      setDeleteModal({ open: false, appointment: null });
    } catch (error) {
      console.error('Delete error:', error);
      toast.error('Erreur lors de la suppression du rendez-vous');
    } finally {
      setDeleting(false);
    }
  };

  const handleCancelDelete = () => {
    setDeleteModal({ open: false, appointment: null });
  };

  const handleSelectWorkspace = (workspace) => {
    selectWorkspace(workspace);
    setWorkspaceDropdownOpen(false);
    setLoading(true);
    // Appointments will reload via useEffect when currentWorkspace changes
  };

  const handleCreateWorkspace = () => {
    setWorkspaceDropdownOpen(false);
    navigate('/workspace/create');
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Delete Confirmation Modal */}
      {deleteModal.open && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={handleCancelDelete}>
          <div 
            className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-rose-100 flex items-center justify-center">
                <Trash2 className="w-5 h-5 text-rose-600" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900">Supprimer le rendez-vous</h3>
            </div>
            
            <p className="text-slate-600 mb-2">
              Voulez-vous vraiment supprimer ce rendez-vous ?
            </p>
            <p className="text-sm text-slate-500 mb-6">
              <strong>"{deleteModal.appointment?.title}"</strong>
              <br />
              Cette action est irréversible.
            </p>
            
            <div className="flex gap-3 justify-end">
              <Button 
                variant="outline" 
                onClick={handleCancelDelete}
                disabled={deleting}
              >
                Annuler
              </Button>
              <Button 
                variant="destructive"
                onClick={handleConfirmDelete}
                disabled={deleting}
                className="bg-rose-600 hover:bg-rose-700 text-white"
                data-testid="confirm-delete-btn"
              >
                {deleting ? 'Suppression...' : 'Supprimer'}
              </Button>
            </div>
          </div>
        </div>
      )}

      <nav className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <h1 className="text-2xl font-bold text-slate-900">NLYT</h1>
            <div className="flex items-center gap-6">
              <Link to="/dashboard" className="text-sm font-medium text-slate-900">
                Tableau de bord
              </Link>
              <Link to="/policies" className="text-sm text-slate-600 hover:text-slate-900">
                Modèles
              </Link>
              <Link to="/analytics" className="text-sm text-slate-600 hover:text-slate-900">
                Analytiques
              </Link>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <Link to="/settings">
              <Button variant="ghost" size="sm">
                <Settings className="w-4 h-4 mr-2" />
                Paramètres
              </Button>
            </Link>
            <Button variant="ghost" size="sm" onClick={logout} data-testid="logout-btn">
              <LogOut className="w-4 h-4 mr-2" />
              Déconnexion
            </Button>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-slate-900 mb-2" data-testid="dashboard-title">
            Bonjour, {user?.first_name}
          </h2>
          
          {/* Workspace Switcher */}
          <div className="relative inline-block">
            <button
              onClick={() => setWorkspaceDropdownOpen(!workspaceDropdownOpen)}
              className="flex items-center gap-2 px-3 py-2 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors text-sm"
              data-testid="workspace-switcher-btn"
            >
              <Building2 className="w-4 h-4 text-slate-600" />
              <span className="font-medium text-slate-800">{currentWorkspace?.name}</span>
              <ChevronDown className={`w-4 h-4 text-slate-500 transition-transform ${workspaceDropdownOpen ? 'rotate-180' : ''}`} />
            </button>
            
            {/* Dropdown */}
            {workspaceDropdownOpen && (
              <>
                {/* Backdrop */}
                <div 
                  className="fixed inset-0 z-10" 
                  onClick={() => setWorkspaceDropdownOpen(false)}
                />
                
                {/* Dropdown Menu */}
                <div className="absolute left-0 top-full mt-2 w-72 bg-white rounded-lg shadow-lg border border-slate-200 z-20" data-testid="workspace-dropdown">
                  <div className="p-2">
                    <p className="text-xs font-medium text-slate-500 uppercase px-2 py-1">Vos workspaces</p>
                    
                    {workspaces.map((workspace) => (
                      <button
                        key={workspace.workspace_id}
                        onClick={() => handleSelectWorkspace(workspace)}
                        className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-left transition-colors ${
                          workspace.workspace_id === currentWorkspace?.workspace_id
                            ? 'bg-slate-100 text-slate-900'
                            : 'hover:bg-slate-50 text-slate-700'
                        }`}
                        data-testid={`workspace-option-${workspace.workspace_id}`}
                      >
                        <Building2 className="w-4 h-4 text-slate-500" />
                        <div className="flex-1 min-w-0">
                          <p className="font-medium truncate">{workspace.name}</p>
                          {workspace.description && (
                            <p className="text-xs text-slate-500 truncate">{workspace.description}</p>
                          )}
                        </div>
                        {workspace.workspace_id === currentWorkspace?.workspace_id && (
                          <Check className="w-4 h-4 text-green-600" />
                        )}
                      </button>
                    ))}
                  </div>
                  
                  <div className="border-t border-slate-100 p-2">
                    <button
                      onClick={handleCreateWorkspace}
                      className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-left hover:bg-slate-50 text-slate-700 transition-colors"
                      data-testid="create-new-workspace-btn"
                    >
                      <Plus className="w-4 h-4 text-slate-500" />
                      <span className="font-medium">Créer un nouveau workspace</span>
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="mb-8">
          <Link to="/appointments/create">
            <Button size="lg" data-testid="create-appointment-btn">
              <CalendarPlus className="w-5 h-5 mr-2" />
              Créer un rendez-vous
            </Button>
          </Link>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-6">
          <h3 className="text-xl font-semibold text-slate-900 mb-4">Mes rendez-vous</h3>
          
          {loading ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900 mx-auto"></div>
            </div>
          ) : appointments.length === 0 ? (
            <div className="text-center py-12">
              <Calendar className="w-16 h-16 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-600 mb-4">Aucun rendez-vous pour le moment</p>
              <Link to="/appointments/create">
                <Button variant="outline">Créer votre premier rendez-vous</Button>
              </Link>
            </div>
          ) : (
            <div className="space-y-4">
              {appointments.map((appointment) => (
                <div
                  key={appointment.appointment_id}
                  className="relative p-4 border border-slate-200 rounded-lg hover:border-slate-300 hover:shadow-sm transition-all"
                  data-testid={`appointment-card-${appointment.appointment_id}`}
                >
                  <Link
                    to={`/appointments/${appointment.appointment_id}`}
                    className="block"
                  >
                    <div className="flex items-start justify-between pr-10">
                      <div className="flex-1">
                        <h4 className="font-semibold text-slate-900 mb-1">{appointment.title}</h4>
                        <p className="text-sm text-slate-600 mb-2">
                          {new Date(appointment.start_datetime).toLocaleString('fr-FR', {
                            weekday: 'long',
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          })}
                        </p>
                        
                        <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500">
                          <span className="flex items-center gap-1">
                            {appointment.appointment_type === 'physical' ? (
                              <><MapPin className="w-4 h-4" /> {appointment.location}</>
                            ) : (
                              <><Video className="w-4 h-4" /> {appointment.meeting_provider}</>
                            )}
                          </span>
                          <span>• {appointment.duration_minutes} min</span>
                        </div>

                        {/* Participants with status */}
                        {appointment.participants && appointment.participants.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-slate-100">
                            <div className="flex items-center gap-2 text-sm text-slate-600 mb-2">
                              <Users className="w-4 h-4" />
                              <span className="font-medium">{appointment.participants.length} participant{appointment.participants.length > 1 ? 's' : ''}</span>
                              {/* Status summary */}
                              {appointment.participants_status_summary && (
                                <span className="text-xs text-slate-500">
                                  ({appointment.participants_status_summary.accepted || 0} accepté{(appointment.participants_status_summary.accepted || 0) > 1 ? 's' : ''}, 
                                  {' '}{appointment.participants_status_summary.invited || 0} en attente)
                                </span>
                              )}
                            </div>
                            <div className="flex flex-wrap gap-2">
                              {appointment.participants.slice(0, 5).map((p, idx) => {
                                const name = p.first_name && p.last_name 
                                  ? `${p.first_name} ${p.last_name}`
                                  : p.name || p.email.split('@')[0];
                                const status = p.status || 'invited';
                                
                                // Determine status label and style
                                const getStatusInfo = (s) => {
                                  switch(s) {
                                    case 'accepted_guaranteed':
                                      return { label: 'Garanti', icon: ShieldCheck, className: 'bg-green-100 text-green-800' };
                                    case 'accepted_pending_guarantee':
                                      return { label: 'Garantie en cours', icon: CreditCard, className: 'bg-amber-100 text-amber-800' };
                                    case 'accepted':
                                      return { label: 'Accepté', icon: Check, className: 'bg-green-100 text-green-800' };
                                    case 'declined':
                                      return { label: 'Refusé', icon: X, className: 'bg-red-100 text-red-800' };
                                    case 'cancelled_by_participant':
                                      return { label: 'Annulé', icon: Ban, className: 'bg-orange-100 text-orange-800' };
                                    default:
                                      return { label: 'En attente', icon: Clock, className: 'bg-slate-100 text-slate-800' };
                                  }
                                };
                                
                                const statusInfo = getStatusInfo(status);
                                const StatusIcon = statusInfo.icon;
                                
                                return (
                                  <span 
                                    key={idx}
                                    className={`inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full ${statusInfo.className}`}
                                    title={`${name} - ${statusInfo.label}`}
                                  >
                                    <StatusIcon className="w-3 h-3" />
                                    {name}
                                  </span>
                                );
                              })}
                              {appointment.participants.length > 5 && (
                                <span className="inline-flex items-center px-2 py-1 bg-slate-200 text-slate-600 text-xs rounded-full">
                                  +{appointment.participants.length - 5} autres
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                      
                      <span className={`ml-4 px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap ${
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
                  </Link>
                  
                  {/* Delete Button - positioned absolutely */}
                  <button
                    onClick={(e) => handleDeleteClick(e, appointment)}
                    className="absolute top-4 right-4 p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                    title="Supprimer le rendez-vous"
                    data-testid={`delete-appointment-${appointment.appointment_id}`}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
