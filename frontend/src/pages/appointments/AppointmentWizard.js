import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useWorkspace } from '../../contexts/WorkspaceContext';
import { useAuth } from '../../contexts/AuthContext';
import { appointmentAPI, videoEvidenceAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { ArrowLeft, ArrowRight, Check, Calendar, MapPin, Video, DollarSign, Shield, Users, Plus, Trash2, Lock, Building2, ChevronDown, Loader2, Zap, Monitor, ExternalLink, AlertTriangle, CheckCircle, Settings2 } from 'lucide-react';
import { toast } from 'sonner';
import AddressAutocomplete from '../../components/AddressAutocomplete';

import { localInputToUTC, formatDateTimeFr, getUserTimezone } from '../../utils/dateFormat';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function AppointmentWizard() {
  const navigate = useNavigate();
  const { token } = useAuth();
  const { currentWorkspace, workspaces, selectWorkspace, createWorkspace, loading: workspaceLoading } = useWorkspace();
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadingDefaults, setLoadingDefaults] = useState(true);
  const [workspaceDropdownOpen, setWorkspaceDropdownOpen] = useState(false);
  const [showCreateWorkspace, setShowCreateWorkspace] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState('');
  const [newWorkspaceDescription, setNewWorkspaceDescription] = useState('');
  const [creatingWorkspace, setCreatingWorkspace] = useState(false);
  const [charityAssociations, setCharityAssociations] = useState([]);
  
  // Video provider connection status
  const [videoProviders, setVideoProviders] = useState(null);
  const [loadingProviders, setLoadingProviders] = useState(false);
  
  // Default payment method for organizer guarantee
  const [orgPaymentMethod, setOrgPaymentMethod] = useState(null);
  
  // Platform commission comes from server — not user-editable
  const [systemPlatformCommission, setSystemPlatformCommission] = useState(20);
  
  const [participants, setParticipants] = useState([
    { first_name: '', last_name: '', email: '', role: 'participant' }
  ]);
  
  const [formData, setFormData] = useState({
    title: '',
    appointment_type: 'physical',
    location: '',
    location_latitude: null,
    location_longitude: null,
    location_place_id: null,
    meeting_provider: null,
    start_datetime: '',
    duration_minutes: 60,
    tolerated_delay_minutes: 15,
    cancellation_deadline_hours: 24,
    penalty_amount: 50,
    penalty_currency: 'eur',
    affected_compensation_percent: 80,
    platform_commission_percent: 20,
    charity_percent: 0,
    charity_association_id: ''
  });

  // Load user defaults and charity associations on mount
  useEffect(() => {
    const loadDefaults = async () => {
      try {
        // Fetch user appointment defaults
        const defaultsResponse = await fetch(`${API_URL}/api/user-settings/me/appointment-defaults`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (defaultsResponse.ok) {
          const defaults = await defaultsResponse.json();
          
          // Platform commission is a SYSTEM value from the server
          const serverPlatformPct = defaults.platform_commission_percent ?? 20;
          setSystemPlatformCommission(serverPlatformPct);
          
          // Pre-fill form with user defaults, respecting platform constraint
          const profileParticipant = defaults.default_participant_percent ?? 80;
          const maxForOthers = 100 - serverPlatformPct;
          const participantPct = Math.min(profileParticipant, maxForOthers);
          const charityPct = Math.max(0, maxForOthers - participantPct);
          
          setFormData(prev => ({
            ...prev,
            cancellation_deadline_hours: defaults.default_cancellation_hours ?? 24,
            tolerated_delay_minutes: defaults.default_late_tolerance_minutes ?? 15,
            penalty_amount: defaults.default_penalty_amount ?? 50,
            penalty_currency: defaults.default_penalty_currency ?? 'eur',
            affected_compensation_percent: participantPct,
            charity_percent: charityPct,
            charity_association_id: defaults.default_charity_association_id || '',
            platform_commission_percent: serverPlatformPct
          }));
        }
        
        // Fetch charity associations
        const assocResponse = await fetch(`${API_URL}/api/charity-associations/`);
        if (assocResponse.ok) {
          const assocData = await assocResponse.json();
          setCharityAssociations(assocData.associations || []);
        }

        // Fetch default payment method for organizer guarantee
        try {
          const pmResponse = await fetch(`${API_URL}/api/user-settings/me/payment-method`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (pmResponse.ok) {
            const pmData = await pmResponse.json();
            if (pmData.has_payment_method) {
              setOrgPaymentMethod(pmData.payment_method);
            }
          }
        } catch { /* non-blocking */ }
      } catch (error) {
        console.error('Error loading defaults:', error);
        // Keep default values if fetch fails
      } finally {
        setLoadingDefaults(false);
      }
    };
    
    loadDefaults();
  }, [token]);

  // Load video provider status when switching to video type
  useEffect(() => {
    if (formData.appointment_type === 'video' && !videoProviders) {
      setLoadingProviders(true);
      videoEvidenceAPI.providerStatus()
        .then(res => {
          setVideoProviders(res.data);
          // Auto-select Zoom as default provider if available and no provider selected
          if (!formData.meeting_provider && res.data?.zoom?.connected) {
            setFormData(prev => ({ ...prev, meeting_provider: 'zoom', meeting_join_url: '' }));
          }
        })
        .catch(() => setVideoProviders(null))
        .finally(() => setLoadingProviders(false));
    }
  }, [formData.appointment_type, videoProviders]);

  const steps = [
    { number: 1, title: 'Participants', icon: Users },
    { number: 2, title: 'Informations de base', icon: Calendar },
    { number: 3, title: 'Règles d\'engagement', icon: Shield },
    { number: 4, title: 'Répartition des pénalités', icon: DollarSign },
    { number: 5, title: 'Révision', icon: Check }
  ];

  const handleSelectWorkspace = (workspace) => {
    selectWorkspace(workspace);
    setWorkspaceDropdownOpen(false);
  };

  const handleCreateWorkspace = async () => {
    if (!newWorkspaceName.trim()) {
      toast.error('Le nom du workspace est requis');
      return;
    }
    
    setCreatingWorkspace(true);
    try {
      await createWorkspace(newWorkspaceName.trim(), newWorkspaceDescription.trim());
      toast.success('Workspace créé');
      setShowCreateWorkspace(false);
      setNewWorkspaceName('');
      setNewWorkspaceDescription('');
      setWorkspaceDropdownOpen(false);
    } catch (error) {
      toast.error('Erreur lors de la création du workspace');
    } finally {
      setCreatingWorkspace(false);
    }
  };

  // Show loading while workspace is being fetched
  if (workspaceLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900 mx-auto mb-4"></div>
          <p className="text-slate-600">Chargement...</p>
        </div>
      </div>
    );
  }

  const addParticipant = () => {
    setParticipants([...participants, { first_name: '', last_name: '', email: '', role: 'participant' }]);
  };

  const removeParticipant = (index) => {
    if (participants.length > 1) {
      setParticipants(participants.filter((_, i) => i !== index));
    }
  };

  const updateParticipant = (index, field, value) => {
    const updated = [...participants];
    updated[index][field] = value;
    setParticipants(updated);
  };

  const validateStep = (step) => {
    switch (step) {
      case 1:
        // Validate participants
        const validParticipants = participants.filter(p => p.email.trim() !== '');
        if (validParticipants.length === 0) {
          toast.error('Ajoutez au moins un participant');
          return false;
        }
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        for (const p of validParticipants) {
          if (!p.first_name || !p.first_name.trim()) {
            toast.error('Le prénom est requis pour chaque participant');
            return false;
          }
          if (!p.last_name || !p.last_name.trim()) {
            toast.error('Le nom est requis pour chaque participant');
            return false;
          }
          if (!emailRegex.test(p.email)) {
            toast.error(`Email invalide: ${p.email}`);
            return false;
          }
        }
        return true;
      case 2:
        if (!formData.title.trim()) {
          toast.error('Le titre est requis');
          return false;
        }
        if (!formData.start_datetime) {
          toast.error('La date et l\'heure sont requises');
          return false;
        }
        // Reject past dates — datetime-local values are local time
        if (new Date(formData.start_datetime) <= new Date()) {
          toast.error('La date et l\'heure du rendez-vous doivent être dans le futur');
          return false;
        }
        if (formData.appointment_type === 'physical' && !formData.location.trim()) {
          toast.error('Le lieu est requis pour un rendez-vous physique');
          return false;
        }
        if (formData.appointment_type === 'video' && !formData.meeting_provider) {
          toast.error('Sélectionnez une plateforme de visioconférence');
          return false;
        }
        if (formData.appointment_type === 'video' && formData.meeting_provider && formData.meeting_provider !== 'external') {
          const p = videoProviders?.[formData.meeting_provider];
          if (p && !p.connected) {
            if (p.mode === 'central') {
              toast.error(`${p.label || formData.meeting_provider} n'est pas encore disponible. Configuration en cours par l'administrateur.`);
            } else {
              toast.error(`${p.label || formData.meeting_provider} n'est pas connecté. Configurez-le dans Paramètres > Intégrations.`);
            }
            return false;
          }
        }
        if (formData.appointment_type === 'video' && formData.meeting_provider === 'external' && !formData.meeting_join_url?.trim()) {
          toast.error('L\'URL de la réunion est requise pour un lien externe');
          return false;
        }
        return true;
      case 3:
        if (formData.penalty_amount <= 0) {
          toast.error('Le montant de la pénalité doit être supérieur à 0');
          return false;
        }
        return true;
      case 4:
        const total = formData.affected_compensation_percent + formData.platform_commission_percent + formData.charity_percent;
        if (total !== 100) {
          toast.error('La répartition doit totaliser 100%');
          return false;
        }
        return true;
      default:
        return true;
    }
  };

  const handleNext = () => {
    if (validateStep(currentStep)) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    setCurrentStep(currentStep - 1);
  };

  const handleSubmit = async () => {
    if (!currentWorkspace || !currentWorkspace.workspace_id) {
      console.error('No workspace available - this should not happen');
      toast.error('Une erreur technique est survenue. Veuillez vous reconnecter.');
      navigate('/signin');
      return;
    }
    
    setLoading(true);
    try {
      const validParticipants = participants.filter(p => p.email.trim() !== '');
      const payload = {
        ...formData,
        // Convert local datetime to UTC for backend storage
        start_datetime: localInputToUTC(formData.start_datetime),
        appointment_timezone: getUserTimezone(),
        workspace_id: currentWorkspace.workspace_id,
        participants: validParticipants
      };
      // Clean video-only fields for physical appointments
      if (payload.appointment_type !== 'video') {
        delete payload.meeting_provider;
        delete payload.meeting_join_url;
      } else if (!payload.meeting_provider) {
        delete payload.meeting_provider;
      }
      
      const response = await appointmentAPI.create(payload);
      
      // If organizer needs to provide Stripe guarantee, redirect to checkout
      if (response.data.organizer_checkout_url) {
        toast.info('Vous allez être redirigé vers Stripe pour valider votre garantie organisateur. Les invitations seront envoyées après validation.');
        window.location.href = response.data.organizer_checkout_url;
      } else {
        toast.success('Rendez-vous créé et invitations envoyées');
        navigate(`/appointments/${response.data.appointment_id}`);
      }
    } catch (error) {
      console.error('Appointment creation error:', error);
      const errorMessage = error.response?.data?.detail || 'Erreur lors de la création du rendez-vous';
      toast.error(typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage));
    } finally {
      setLoading(false);
    }
  };

  const handleQuickCreate = async () => {
    // Validate participants (step 1) and basic info (step 2)
    if (!validateStep(1) || !validateStep(2)) return;

    if (!currentWorkspace || !currentWorkspace.workspace_id) {
      toast.error('Une erreur technique est survenue. Veuillez vous reconnecter.');
      navigate('/signin');
      return;
    }

    setLoading(true);
    try {
      const validParticipants = participants.filter(p => p.email.trim() !== '');
      const payload = {
        ...formData,
        start_datetime: localInputToUTC(formData.start_datetime),
        appointment_timezone: getUserTimezone(),
        workspace_id: currentWorkspace.workspace_id,
        participants: validParticipants
      };
      // Clean video-only fields for physical appointments
      if (payload.appointment_type !== 'video') {
        delete payload.meeting_provider;
        delete payload.meeting_join_url;
      } else if (!payload.meeting_provider) {
        delete payload.meeting_provider;
      }

      const response = await appointmentAPI.create(payload);
      if (response.data.organizer_checkout_url) {
        toast.info('Vous allez être redirigé vers Stripe pour valider votre garantie organisateur.');
        window.location.href = response.data.organizer_checkout_url;
      } else {
        toast.success('Rendez-vous créé en express — invitations envoyées');
        navigate(`/appointments/${response.data.appointment_id}`);
      }
    } catch (error) {
      console.error('Quick create error:', error);
      const errorMessage = error.response?.data?.detail || 'Erreur lors de la création du rendez-vous';
      toast.error(typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage));
    } finally {
      setLoading(false);
    }
  };

  // Step 1: Participants
  const renderStep1 = () => (
    <div className="space-y-6">
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-sm text-blue-900">
          Ajoutez les personnes qui participeront à ce rendez-vous. Chaque participant recevra une invitation par email.
        </p>
      </div>

      <div className="space-y-4">
        {participants.map((participant, index) => (
          <div key={index} className="p-4 border border-slate-200 rounded-lg bg-slate-50">
            <div className="flex justify-between items-center mb-3">
              <span className="font-medium text-slate-700">Participant {index + 1}</span>
              {participants.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeParticipant(index)}
                  className="text-rose-600 hover:text-rose-800 p-1"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div>
                <Label htmlFor={`participant-firstname-${index}`}>Prénom *</Label>
                <Input
                  id={`participant-firstname-${index}`}
                  data-testid={`participant-firstname-${index}`}
                  value={participant.first_name}
                  onChange={(e) => updateParticipant(index, 'first_name', e.target.value)}
                  placeholder="Prénom"
                  className="mt-1"
                />
              </div>
              
              <div>
                <Label htmlFor={`participant-lastname-${index}`}>Nom *</Label>
                <Input
                  id={`participant-lastname-${index}`}
                  data-testid={`participant-lastname-${index}`}
                  value={participant.last_name}
                  onChange={(e) => updateParticipant(index, 'last_name', e.target.value)}
                  placeholder="Nom"
                  className="mt-1"
                />
              </div>

              <div>
                <Label htmlFor={`participant-email-${index}`}>Email *</Label>
                <Input
                  id={`participant-email-${index}`}
                  type="email"
                  data-testid={`participant-email-${index}`}
                  value={participant.email}
                  onChange={(e) => updateParticipant(index, 'email', e.target.value)}
                  placeholder="email@exemple.com"
                  className="mt-1"
                />
              </div>
              
              <div>
                <Label htmlFor={`participant-role-${index}`}>Rôle</Label>
                <Select
                  value={participant.role}
                  onValueChange={(value) => updateParticipant(index, 'role', value)}
                >
                  <SelectTrigger className="mt-1" data-testid={`participant-role-${index}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="participant">Participant</SelectItem>
                    <SelectItem value="organizer">Organisateur</SelectItem>
                    <SelectItem value="observer">Observateur</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        ))}
      </div>

      <Button
        type="button"
        variant="outline"
        onClick={addParticipant}
        className="w-full"
        data-testid="add-participant-btn"
      >
        <Plus className="w-4 h-4 mr-2" />
        Ajouter un participant
      </Button>
    </div>
  );

  // Step 2: Basic info
  const renderStep2 = () => (
    <div className="space-y-6">
      <div>
        <Label htmlFor="title">Titre du rendez-vous *</Label>
        <Input
          id="title"
          data-testid="appointment-title-input"
          value={formData.title}
          onChange={(e) => setFormData({ ...formData, title: e.target.value })}
          placeholder="Ex: Consultation client, Réunion d'équipe..."
          className="mt-1"
        />
      </div>

      <div>
        <Label htmlFor="appointment_type">Type de rendez-vous *</Label>
        <Select
          value={formData.appointment_type}
          onValueChange={(value) => setFormData({ ...formData, appointment_type: value })}
        >
          <SelectTrigger className="mt-1" data-testid="appointment-type-select">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="physical">
              <div className="flex items-center gap-2">
                <MapPin className="w-4 h-4" />
                Physique
              </div>
            </SelectItem>
            <SelectItem value="video">
              <div className="flex items-center gap-2">
                <Video className="w-4 h-4" />
                Visioconférence
              </div>
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      {formData.appointment_type === 'physical' ? (
        <div>
          <Label htmlFor="location">Lieu *</Label>
          <div className="mt-1">
            <AddressAutocomplete
              value={formData.location}
              onChange={(value) => setFormData({ ...formData, location: value })}
              onSelect={(addressData) => {
                setFormData({
                  ...formData,
                  location: addressData.address,
                  location_latitude: addressData.latitude,
                  location_longitude: addressData.longitude,
                  location_place_id: addressData.place_id
                });
              }}
              placeholder="Tapez une adresse..."
              data-testid="appointment-location-input"
            />
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Commencez à taper pour voir les suggestions d'adresses
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <Label>Plateforme de visioconférence *</Label>
          {loadingProviders ? (
            <div className="flex items-center gap-2 p-3 bg-slate-50 rounded-lg border border-slate-200">
              <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
              <span className="text-sm text-slate-500">Chargement des intégrations...</span>
            </div>
          ) : (
            <div className="space-y-2" data-testid="meeting-provider-selector">
              {/* Zoom — Default / Recommended */}
              {(() => {
                const zoomInfo = videoProviders?.zoom;
                const isConfigured = zoomInfo?.connected;
                const isSelected = formData.meeting_provider === 'zoom';
                return (
                  <button
                    type="button"
                    onClick={() => isConfigured && setFormData({ ...formData, meeting_provider: 'zoom', meeting_join_url: '' })}
                    className={`w-full flex items-center gap-3 p-3.5 rounded-lg border text-left transition-all ${
                      isSelected
                        ? 'border-blue-400 bg-blue-50 ring-1 ring-blue-200'
                        : isConfigured
                          ? 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 cursor-pointer'
                          : 'border-dashed border-slate-200 bg-slate-50/50 opacity-70 cursor-not-allowed'
                    }`}
                    disabled={!isConfigured}
                    data-testid="provider-option-zoom"
                  >
                    <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center flex-shrink-0">
                      <Video className="w-5 h-5 text-blue-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-slate-900">Zoom</span>
                        {isConfigured ? (
                          <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-semibold" data-testid="zoom-recommended-badge">
                            Recommandé
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-600 font-medium" data-testid="zoom-pending-badge">
                            Configuration en cours
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5" data-testid="zoom-description">
                        {isConfigured
                          ? 'Aucun compte requis — réunion créée automatiquement'
                          : 'Bientôt disponible — en attente de configuration'}
                      </p>
                    </div>
                    {isSelected && <Check className="w-5 h-5 text-blue-600 flex-shrink-0" />}
                  </button>
                );
              })()}

              {/* Microsoft Teams — Advanced */}
              {(() => {
                const teamsInfo = videoProviders?.teams;
                const isConnected = teamsInfo?.connected;
                const isSelected = formData.meeting_provider === 'teams';
                return (
                  <button
                    type="button"
                    onClick={() => isConnected && setFormData({ ...formData, meeting_provider: 'teams', meeting_join_url: '' })}
                    className={`w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all ${
                      isSelected
                        ? 'border-violet-400 bg-violet-50 ring-1 ring-violet-200'
                        : isConnected
                          ? 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 cursor-pointer'
                          : 'border-slate-100 bg-slate-50 opacity-60 cursor-not-allowed'
                    }`}
                    disabled={!isConnected}
                    data-testid="provider-option-teams"
                  >
                    <div className="w-9 h-9 rounded-lg bg-violet-50 flex items-center justify-center flex-shrink-0">
                      <Monitor className="w-4 h-4 text-violet-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium text-slate-900">Microsoft Teams</span>
                        <span className="inline-flex items-center text-xs px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500 font-medium">
                          Avancé
                        </span>
                        {isConnected ? (
                          <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-medium">
                            <CheckCircle className="w-3 h-3" /> Connecté
                          </span>
                        ) : null}
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {isConnected
                          ? `Compte Microsoft 365 : ${teamsInfo?.email || ''}`
                          : <><Link to="/settings/integrations" className="text-violet-500 hover:underline">Connecter un compte Microsoft 365</Link></>
                        }
                      </p>
                    </div>
                    {isSelected && <Check className="w-4 h-4 text-violet-600 flex-shrink-0" />}
                  </button>
                );
              })()}

              {/* Google Meet — Limited */}
              {(() => {
                const meetInfo = videoProviders?.meet;
                const isConnected = meetInfo?.connected;
                const isSelected = formData.meeting_provider === 'meet';
                return (
                  <button
                    type="button"
                    onClick={() => isConnected && setFormData({ ...formData, meeting_provider: 'meet', meeting_join_url: '' })}
                    className={`w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all ${
                      isSelected
                        ? 'border-emerald-400 bg-emerald-50 ring-1 ring-emerald-200'
                        : isConnected
                          ? 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 cursor-pointer'
                          : 'border-slate-100 bg-slate-50 opacity-60 cursor-not-allowed'
                    }`}
                    disabled={!isConnected}
                    data-testid="provider-option-meet"
                  >
                    <div className="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center flex-shrink-0">
                      <Video className="w-4 h-4 text-emerald-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium text-slate-900">Google Meet</span>
                        <span className="inline-flex items-center text-xs px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-600 font-medium">
                          Limité
                        </span>
                        {isConnected ? (
                          <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-medium">
                            <CheckCircle className="w-3 h-3" /> via Google Calendar
                          </span>
                        ) : null}
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {isConnected
                          ? `Fonctionnalités limitées — ${meetInfo?.email || ''}`
                          : <><Link to="/settings/integrations" className="text-emerald-500 hover:underline">Connecter Google Calendar</Link></>
                        }
                      </p>
                    </div>
                    {isSelected && <Check className="w-4 h-4 text-emerald-600 flex-shrink-0" />}
                  </button>
                );
              })()}

              {/* External link */}
              {(() => {
                const isSelected = formData.meeting_provider === 'external';
                return (
                  <button
                    type="button"
                    onClick={() => setFormData({ ...formData, meeting_provider: 'external', meeting_join_url: '' })}
                    className={`w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all ${
                      isSelected
                        ? 'border-amber-400 bg-amber-50 ring-1 ring-amber-200'
                        : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 cursor-pointer'
                    }`}
                    data-testid="provider-option-external"
                  >
                    <div className="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center flex-shrink-0">
                      <ExternalLink className="w-4 h-4 text-amber-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-900">Lien externe</span>
                        <span className="inline-flex items-center text-xs px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500 font-medium">
                          Manuel
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">Collez le lien d'une réunion déjà créée</p>
                    </div>
                    {isSelected && <Check className="w-4 h-4 text-amber-600 flex-shrink-0" />}
                  </button>
                );
              })()}
            </div>
          )}

          {/* External URL input */}
          {formData.meeting_provider === 'external' && (
            <div className="mt-3">
              <Label htmlFor="meeting_join_url">URL de la réunion *</Label>
              <Input
                id="meeting_join_url"
                data-testid="external-meeting-url-input"
                type="url"
                value={formData.meeting_join_url || ''}
                onChange={(e) => setFormData({ ...formData, meeting_join_url: e.target.value })}
                placeholder="https://zoom.us/j/... ou https://meet.google.com/..."
                className="mt-1"
              />
              <p className="text-xs text-slate-500 mt-1">Collez le lien de la réunion que vous avez créée manuellement</p>
            </div>
          )}

          {/* Info: auto-creation note for connected providers */}
          {formData.meeting_provider && formData.meeting_provider !== 'external' && videoProviders?.[formData.meeting_provider]?.connected && (
            <div className="flex items-start gap-2 p-2.5 bg-blue-50 border border-blue-100 rounded-lg mt-2">
              <Zap className="w-3.5 h-3.5 text-blue-600 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-blue-700">
                {videoProviders[formData.meeting_provider]?.mode === 'central'
                  ? 'Le lien de réunion Zoom sera créé automatiquement. Aucun compte Zoom requis pour les participants.'
                  : `Le lien de réunion sera créé automatiquement via l'API ${videoProviders[formData.meeting_provider]?.label || formData.meeting_provider} et inclus dans les invitations.`
                }
              </p>
            </div>
          )}
        </div>
      )}

      <div>
        <Label htmlFor="start_datetime">Date et heure *</Label>
        <Input
          id="start_datetime"
          type="datetime-local"
          data-testid="appointment-datetime-input"
          value={formData.start_datetime}
          min={(() => {
            const now = new Date();
            const y = now.getFullYear();
            const m = String(now.getMonth() + 1).padStart(2, '0');
            const d = String(now.getDate()).padStart(2, '0');
            const h = String(now.getHours()).padStart(2, '0');
            const mi = String(now.getMinutes()).padStart(2, '0');
            return `${y}-${m}-${d}T${h}:${mi}`;
          })()}
          onChange={(e) => setFormData({ ...formData, start_datetime: e.target.value })}
          className="mt-1"
        />
        {formData.start_datetime && new Date(formData.start_datetime) <= new Date() && (
          <p className="text-sm text-red-600 mt-1" data-testid="datetime-past-error">
            La date et l'heure du rendez-vous doivent être dans le futur
          </p>
        )}
      </div>

      <div>
        <Label htmlFor="duration_minutes">Durée (minutes) *</Label>
        <Input
          id="duration_minutes"
          type="number"
          data-testid="appointment-duration-input"
          value={formData.duration_minutes}
          onChange={(e) => setFormData({ ...formData, duration_minutes: parseInt(e.target.value) })}
          min="15"
          step="15"
          className="mt-1"
        />
      </div>
    </div>
  );

  // Step 3: Engagement rules
  const renderStep3 = () => (
    <div className="space-y-6">
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-sm text-blue-900">
          Définissez les règles d'engagement que tous les participants devront accepter.
        </p>
      </div>

      <div>
        <Label htmlFor="tolerated_delay_minutes">Retard toléré (minutes) *</Label>
        <Input
          id="tolerated_delay_minutes"
          type="number"
          data-testid="appointment-delay-input"
          value={formData.tolerated_delay_minutes}
          onChange={(e) => setFormData({ ...formData, tolerated_delay_minutes: parseInt(e.target.value) })}
          min="0"
          className="mt-1"
        />
        <p className="text-sm text-slate-500 mt-1">
          Délai de grâce avant application de la pénalité
        </p>
      </div>

      <div>
        <Label htmlFor="cancellation_deadline_hours">Délai d'annulation (heures) *</Label>
        <Input
          id="cancellation_deadline_hours"
          type="number"
          data-testid="appointment-cancellation-input"
          value={formData.cancellation_deadline_hours}
          onChange={(e) => setFormData({ ...formData, cancellation_deadline_hours: parseInt(e.target.value) })}
          min="1"
          className="mt-1"
        />
        <p className="text-sm text-slate-500 mt-1">
          Délai minimum pour annuler sans pénalité
        </p>
      </div>

      <div>
        <Label htmlFor="penalty_amount">Montant de la pénalité (€) *</Label>
        <Input
          id="penalty_amount"
          type="number"
          data-testid="appointment-penalty-input"
          value={formData.penalty_amount}
          onChange={(e) => setFormData({ ...formData, penalty_amount: parseFloat(e.target.value) })}
          min="1"
          step="0.01"
          className="mt-1"
        />
        <p className="text-sm text-slate-500 mt-1">
          Montant appliqué en cas de retard excessif ou d'absence
        </p>
      </div>
    </div>
  );

  // Step 4: Penalty distribution
  const renderStep4 = () => {
    const handleCompensationChange = (value) => {
      const newValue = parseFloat(value) || 0;
      // Auto-adjust charity to maintain 100% total
      const remaining = 100 - systemPlatformCommission - newValue;
      setFormData({
        ...formData,
        affected_compensation_percent: newValue,
        charity_percent: Math.max(0, remaining)
      });
    };

    const handleCharityChange = (value) => {
      const newValue = parseFloat(value) || 0;
      // Auto-adjust compensation to maintain 100% total
      const remaining = 100 - systemPlatformCommission - newValue;
      setFormData({
        ...formData,
        charity_percent: newValue,
        affected_compensation_percent: Math.max(0, remaining)
      });
    };

    return (
      <div className="space-y-6">
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
          <p className="text-sm text-emerald-900">
            Définissez comment les pénalités collectées seront réparties.
          </p>
        </div>

        <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg flex items-start gap-3">
          <Lock className="w-5 h-5 text-slate-500 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-slate-700">Commission plateforme NLYT</p>
            <p className="text-sm text-slate-600 mt-1">
              La commission plateforme est fixée à {systemPlatformCommission}%. Ce taux est une donnée système non modifiable.
            </p>
          </div>
        </div>

        <div>
          <Label htmlFor="affected_compensation_percent">Compensation participants affectés (%) *</Label>
          <Input
            id="affected_compensation_percent"
            type="number"
            data-testid="compensation-percent-input"
            value={formData.affected_compensation_percent}
            onChange={(e) => handleCompensationChange(e.target.value)}
            min="0"
            max={100 - systemPlatformCommission}
            className="mt-1"
          />
          <p className="text-sm text-slate-500 mt-1">
            Part versée aux participants présents à l'heure
          </p>
        </div>

        <div>
          <div className="flex items-center gap-2">
            <Label htmlFor="platform_commission_percent">Commission plateforme (%) *</Label>
            <Lock className="w-4 h-4 text-slate-400" />
          </div>
          <Input
            id="platform_commission_percent"
            type="number"
            data-testid="platform-percent-input"
            value={formData.platform_commission_percent}
            disabled={true}
            className="mt-1 bg-slate-100 cursor-not-allowed"
          />
          <p className="text-sm text-slate-500 mt-1">
            Donnée système — fixée à {systemPlatformCommission}%
          </p>
        </div>

        <div>
          <Label htmlFor="charity_percent">Don caritatif (%) *</Label>
          <Input
            id="charity_percent"
            type="number"
            data-testid="charity-percent-input"
            value={formData.charity_percent}
            onChange={(e) => handleCharityChange(e.target.value)}
            min="0"
            max={100 - systemPlatformCommission}
            className="mt-1"
          />
          <p className="text-sm text-slate-500 mt-1">Optionnel - Reversé à une association partenaire</p>
        </div>

        {/* Charity Association Selection */}
        {formData.charity_percent > 0 && (
          <div>
            <Label htmlFor="charity_association">Association bénéficiaire</Label>
            <Select
              value={formData.charity_association_id || "none"}
              onValueChange={(value) => setFormData({ ...formData, charity_association_id: value === "none" ? '' : value })}
            >
              <SelectTrigger className="mt-1" data-testid="charity-association-select">
                <SelectValue placeholder="Sélectionnez une association" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Aucune association</SelectItem>
                {charityAssociations.map((assoc) => (
                  <SelectItem key={assoc.association_id} value={assoc.association_id}>
                    {assoc.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-sm text-slate-500 mt-1">
              Choisissez l'association qui recevra le don caritatif
            </p>
          </div>
        )}

        <div className="p-4 bg-slate-50 rounded-lg">
          <div className="flex justify-between items-center">
            <span className="font-medium">Total répartition:</span>
            <span className={`text-lg font-bold ${
              formData.affected_compensation_percent + formData.platform_commission_percent + formData.charity_percent === 100
                ? 'text-emerald-600'
                : 'text-rose-600'
            }`}>
              {formData.affected_compensation_percent + formData.platform_commission_percent + formData.charity_percent}%
            </span>
          </div>
        </div>
      </div>
    );
  };

  // Step 5: Review
  const renderStep5 = () => {
    const validParticipants = participants.filter(p => p.email.trim() !== '');
    
    return (
      <div className="space-y-6">
        <div className="p-6 bg-white border-t-4 border-slate-900 rounded-lg shadow-sm">
          <h3 className="text-xl font-semibold text-slate-900 mb-6">Récapitulatif du rendez-vous</h3>
          
          <div className="space-y-4">
            <div className="border-b border-slate-200 pb-4">
              <h4 className="font-medium text-slate-700 mb-2">Participants ({validParticipants.length})</h4>
              <div className="space-y-2 text-sm">
                {validParticipants.map((p, i) => (
                  <div key={i} className="flex justify-between">
                    <span className="text-slate-600">{p.first_name} {p.last_name}</span>
                    <span className="font-medium text-slate-900">{p.email}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="border-b border-slate-200 pb-4">
              <h4 className="font-medium text-slate-700 mb-2">Informations générales</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-600">Titre:</span>
                  <span className="font-medium text-slate-900">{formData.title}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">Type:</span>
                  <span className="font-medium text-slate-900">{formData.appointment_type === 'physical' ? 'Physique' : 'Visioconférence'}</span>
                </div>
                {formData.appointment_type === 'physical' ? (
                  <div className="flex justify-between">
                    <span className="text-slate-600">Lieu:</span>
                    <span className="font-medium text-slate-900">{formData.location}</span>
                  </div>
                ) : (
                  <div className="flex justify-between">
                    <span className="text-slate-600">Plateforme:</span>
                    <span className="font-medium text-slate-900">
                      {{ zoom: 'Zoom', teams: 'Microsoft Teams', meet: 'Google Meet', external: 'Lien externe' }[formData.meeting_provider] || formData.meeting_provider}
                    </span>
                  </div>
                )}
                {formData.meeting_provider === 'external' && formData.meeting_join_url && (
                  <div className="flex justify-between">
                    <span className="text-slate-600">URL:</span>
                    <a href={formData.meeting_join_url} target="_blank" rel="noopener noreferrer" className="font-medium text-blue-600 hover:underline truncate max-w-[250px]">
                      {formData.meeting_join_url}
                    </a>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-slate-600">Date et heure:</span>
                  <span className="font-medium text-slate-900">
                    {formData.start_datetime ? formatDateTimeFr(formData.start_datetime) : '-'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">Durée:</span>
                  <span className="font-medium text-slate-900">{formData.duration_minutes} minutes</span>
                </div>
              </div>
            </div>

            <div className="border-b border-slate-200 pb-4">
              <h4 className="font-medium text-slate-700 mb-2">Règles d'engagement</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-600">Retard toléré:</span>
                  <span className="font-medium text-slate-900">{formData.tolerated_delay_minutes} minutes</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">Délai d'annulation:</span>
                  <span className="font-medium text-slate-900">{formData.cancellation_deadline_hours} heures</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">Pénalité:</span>
                  <span className="font-medium text-emerald-600">{formData.penalty_amount} {formData.penalty_currency.toUpperCase()}</span>
                </div>
              </div>
            </div>

            <div>
              <h4 className="font-medium text-slate-700 mb-2">Répartition des pénalités</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-600">Compensation participants:</span>
                  <span className="font-medium text-slate-900">{formData.affected_compensation_percent}%</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-600">Commission plateforme:</span>
                  <span className="font-medium text-slate-900 flex items-center gap-1">
                    {formData.platform_commission_percent}%
                    <Lock className="w-3 h-3 text-slate-400" />
                  </span>
                </div>
                {formData.charity_percent > 0 && (
                  <div className="flex justify-between">
                    <span className="text-slate-600">Don caritatif:</span>
                    <span className="font-medium text-slate-900">{formData.charity_percent}%</span>
                  </div>
                )}
              </div>
            </div>

            {/* Organizer guarantee info */}
            {formData.penalty_amount > 0 && (
              <div data-testid="organizer-guarantee-info">
                {orgPaymentMethod ? (
                  <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 flex items-start gap-3">
                    <CheckCircle className="w-5 h-5 text-emerald-600 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-emerald-800">Votre garantie organisateur sera couverte automatiquement</p>
                      <p className="text-xs text-emerald-700 mt-1">
                        Carte {orgPaymentMethod.brand?.toUpperCase()} •••• {orgPaymentMethod.last4} — Les invitations seront envoyées immédiatement.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-amber-800">Redirection Stripe requise</p>
                      <p className="text-xs text-amber-700 mt-1">
                        Vous serez redirigé vers Stripe pour valider votre garantie. Les invitations ne seront envoyées qu'après validation.
                      </p>
                      <a href="/settings/payment" className="text-xs text-amber-800 underline mt-2 inline-block">
                        Configurer une carte par défaut pour éviter cette étape
                      </a>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-background py-8 px-4">
      <div className="max-w-4xl mx-auto">
        <button
          onClick={() => navigate('/dashboard')}
          className="flex items-center gap-2 text-slate-600 hover:text-slate-900 mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Retour au tableau de bord
        </button>

        {loadingDefaults ? (
          <div className="flex items-center justify-center py-12">
            <div className="flex items-center gap-3 text-slate-500">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Chargement de vos paramètres par défaut...</span>
            </div>
          </div>
        ) : (
          <>
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Créer un rendez-vous</h1>
          <p className="text-slate-600 mb-4">Définissez les conditions d'engagement pour votre rendez-vous</p>
          
          {/* Workspace Selector */}
          <div className="relative inline-block">
            <button
              onClick={() => setWorkspaceDropdownOpen(!workspaceDropdownOpen)}
              className="flex items-center gap-2 px-3 py-2 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors text-sm"
              data-testid="wizard-workspace-switcher-btn"
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
                  onClick={() => {
                    setWorkspaceDropdownOpen(false);
                    setShowCreateWorkspace(false);
                  }}
                />
                
                {/* Dropdown Menu */}
                <div className="absolute left-0 top-full mt-2 w-80 bg-white rounded-lg shadow-lg border border-slate-200 z-20" data-testid="wizard-workspace-dropdown">
                  {!showCreateWorkspace ? (
                    <>
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
                            data-testid={`wizard-workspace-option-${workspace.workspace_id}`}
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
                          onClick={() => setShowCreateWorkspace(true)}
                          className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-left hover:bg-slate-50 text-slate-700 transition-colors"
                          data-testid="wizard-create-new-workspace-btn"
                        >
                          <Plus className="w-4 h-4 text-slate-500" />
                          <span className="font-medium">Créer un nouveau workspace</span>
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className="p-4">
                      <h4 className="font-medium text-slate-800 mb-3">Nouveau workspace</h4>
                      <div className="space-y-3">
                        <div>
                          <Label htmlFor="new-workspace-name" className="text-sm">Nom *</Label>
                          <Input
                            id="new-workspace-name"
                            value={newWorkspaceName}
                            onChange={(e) => setNewWorkspaceName(e.target.value)}
                            placeholder="Ex: Cabinet Médical"
                            className="mt-1"
                            data-testid="wizard-new-workspace-name"
                          />
                        </div>
                        <div>
                          <Label htmlFor="new-workspace-desc" className="text-sm">Description (optionnel)</Label>
                          <Input
                            id="new-workspace-desc"
                            value={newWorkspaceDescription}
                            onChange={(e) => setNewWorkspaceDescription(e.target.value)}
                            placeholder="Description..."
                            className="mt-1"
                            data-testid="wizard-new-workspace-desc"
                          />
                        </div>
                        <div className="flex gap-2 pt-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setShowCreateWorkspace(false);
                              setNewWorkspaceName('');
                              setNewWorkspaceDescription('');
                            }}
                            className="flex-1"
                          >
                            Annuler
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            onClick={handleCreateWorkspace}
                            disabled={creatingWorkspace || !newWorkspaceName.trim()}
                            className="flex-1"
                            data-testid="wizard-confirm-create-workspace"
                          >
                            {creatingWorkspace ? 'Création...' : 'Créer'}
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>

        <div className="mb-8">
          <div className="flex items-center justify-between">
            {steps.map((step, index) => (
              <React.Fragment key={step.number}>
                <div className="flex flex-col items-center">
                  <div className={`w-10 h-10 md:w-12 md:h-12 rounded-full flex items-center justify-center ${
                    currentStep === step.number
                      ? 'bg-slate-900 text-white'
                      : currentStep > step.number
                      ? 'bg-emerald-600 text-white'
                      : 'bg-slate-200 text-slate-600'
                  }`}>
                    {currentStep > step.number ? <Check className="w-5 h-5 md:w-6 md:h-6" /> : <step.icon className="w-5 h-5 md:w-6 md:h-6" />}
                  </div>
                  <span className={`text-xs mt-2 text-center max-w-[80px] md:max-w-[100px] ${
                    currentStep === step.number ? 'font-medium text-slate-900' : 'text-slate-600'
                  }`}>
                    {step.title}
                  </span>
                </div>
                {index < steps.length - 1 && (
                  <div className={`flex-1 h-1 mx-2 md:mx-4 ${
                    currentStep > step.number ? 'bg-emerald-600' : 'bg-slate-200'
                  }`} />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-6 md:p-8">
          {currentStep === 1 && renderStep1()}
          {currentStep === 2 && renderStep2()}
          {currentStep === 3 && renderStep3()}
          {currentStep === 4 && renderStep4()}
          {currentStep === 5 && renderStep5()}

          <div className="flex justify-between mt-8 pt-6 border-t border-slate-200">
            <Button
              type="button"
              variant="outline"
              onClick={handleBack}
              disabled={currentStep === 1}
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Précédent
            </Button>

            <div className="flex items-center gap-3">
              {currentStep === 2 && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleQuickCreate}
                  disabled={loading}
                  className="border-amber-300 text-amber-700 hover:bg-amber-50 hover:border-amber-400"
                  data-testid="quick-create-btn"
                >
                  {loading ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Zap className="w-4 h-4 mr-2" />
                  )}
                  Validation express avec les paramètres du profil
                </Button>
              )}

              {currentStep < 5 ? (
                <Button type="button" onClick={handleNext} data-testid="wizard-next-btn">
                  Suivant
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              ) : (
                <Button type="button" onClick={handleSubmit} disabled={loading} data-testid="wizard-create-btn">
                  {loading ? 'Création...' : 'Créer le rendez-vous'}
                </Button>
              )}
            </div>
          </div>
        </div>
          </>
        )}
      </div>
    </div>
  );
}
