import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { useWorkspace } from '../../contexts/WorkspaceContext';
import { useAuth } from '../../contexts/AuthContext';
import { appointmentAPI, videoEvidenceAPI } from '../../services/api';
import { safeFetchJson } from '../../utils/safeFetchJson';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { ArrowLeft, ArrowRight, Check, Calendar, MapPin, Video, DollarSign, Shield, Users, Plus, Trash2, Lock, Building2, ChevronDown, Loader2, Zap, Monitor, ExternalLink, AlertTriangle, CheckCircle, Settings2, Link2, Clock, Search, XCircle, Sparkles, Info } from 'lucide-react';
import { toast } from 'sonner';
import AddressAutocomplete from '../../components/AddressAutocomplete';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';

import { localInputToUTC, formatDateTimeFr, getUserTimezone } from '../../utils/dateFormat';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

function formatSlotRange(startISO, endISO) {
  const opts = { hour: '2-digit', minute: '2-digit' };
  const dayOpts = { weekday: 'short', day: 'numeric', month: 'short' };
  try {
    const s = new Date(startISO);
    const e = new Date(endISO);
    return `${s.toLocaleDateString('fr-FR', dayOpts)} ${s.toLocaleTimeString('fr-FR', opts)} – ${e.toLocaleTimeString('fr-FR', opts)}`;
  } catch (_) {
    return '';
  }
}

export default function AppointmentWizard() {
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = useAuth();
  const { currentWorkspace, workspaces, selectWorkspace, createWorkspace, loading: workspaceLoading } = useWorkspace();
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadingDefaults, setLoadingDefaults] = useState(true);

  // External event pre-fill data (from "NLYT me" flow)
  const fromExternalData = location.state?.fromExternal || null;
  const externalSource = fromExternalData?.source;
  const externalEventId = fromExternalData?.external_event_id;
  const [workspaceDropdownOpen, setWorkspaceDropdownOpen] = useState(false);
  const [showCreateWorkspace, setShowCreateWorkspace] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState('');
  const [newWorkspaceDescription, setNewWorkspaceDescription] = useState('');
  const [creatingWorkspace, setCreatingWorkspace] = useState(false);
  const [charityAssociations, setCharityAssociations] = useState([]);
  
  // Video provider connection status
  const [videoProviders, setVideoProviders] = useState(null);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [providerAutoSelected, setProviderAutoSelected] = useState(false);
  
  // Default payment method for organizer guarantee
  const [orgPaymentMethod, setOrgPaymentMethod] = useState(null);
  
  // Platform commission comes from server — not user-editable
  const [systemPlatformCommission, setSystemPlatformCommission] = useState(20);
  
  const [participants, setParticipants] = useState([
    { first_name: '', last_name: '', email: '' }
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

  // Auto-select best available video provider (once, on first load only)
  useEffect(() => {
    if (videoProviders && !providerAutoSelected && !formData.meeting_provider) {
      const priority = ['teams', 'meet', 'zoom', 'external'];
      const best = priority.find(p => {
        if (p === 'teams') return videoProviders[p]?.level === 'advanced';
        return videoProviders[p]?.can_auto_generate;
      }) || 'external';
      setFormData(prev => ({ ...prev, meeting_provider: best, meeting_join_url: '' }));
      setProviderAutoSelected(true);
    }
  }, [videoProviders, providerAutoSelected, formData.meeting_provider]);

  // Pre-fill from external event (NLYT me flow)
  const prefillApplied = useRef(false);
  useEffect(() => {
    if (!fromExternalData?.prefill || prefillApplied.current) return;
    prefillApplied.current = true;
    const p = fromExternalData.prefill;
    setFormData(prev => ({
      ...prev,
      title: p.title || prev.title,
      appointment_type: p.appointment_type || prev.appointment_type,
      location: p.location || prev.location,
      meeting_provider: p.meeting_provider || prev.meeting_provider,
      start_datetime: p.start_datetime || prev.start_datetime,
      duration_minutes: p.duration_minutes || prev.duration_minutes,
    }));
    if (p.suggested_participants && p.suggested_participants.length > 0) {
      setParticipants(p.suggested_participants.map(sp => ({
        first_name: sp.first_name || '',
        last_name: sp.last_name || '',
        email: sp.email || '',
      })));
    }
    if (p.meeting_provider) {
      setProviderAutoSelected(true);
    }
  }, [fromExternalData]);


  // Load user defaults and charity associations on mount
  const [conflictResult, setConflictResult] = useState(null);
  const [conflictLoading, setConflictLoading] = useState(false);
  const conflictTimer = useRef(null);

  const checkConflicts = useCallback(async (dt, dur) => {
    if (!dt || !dur) { setConflictResult(null); return; }
    setConflictLoading(true);
    try {
      const res = await appointmentAPI.checkConflicts({
        start_datetime: localInputToUTC(dt),
        duration_minutes: parseInt(dur, 10) || 60,
      });
      setConflictResult(res.data);
    } catch (_) {
      setConflictResult(null);
    } finally {
      setConflictLoading(false);
    }
  }, []);

  const debouncedCheck = useCallback((dt, dur) => {
    if (conflictTimer.current) clearTimeout(conflictTimer.current);
    conflictTimer.current = setTimeout(() => checkConflicts(dt, dur), 500);
  }, [checkConflicts]);

  useEffect(() => {
    if (formData.start_datetime && formData.duration_minutes) {
      debouncedCheck(formData.start_datetime, formData.duration_minutes);
    } else {
      setConflictResult(null);
    }
  }, [formData.start_datetime, formData.duration_minutes, debouncedCheck]);

  const applySuggestion = (isoStr) => {
    const d = new Date(isoStr);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const h = String(d.getHours()).padStart(2, '0');
    const mi = String(d.getMinutes()).padStart(2, '0');
    // Clear old result and show loading immediately for snappy feedback
    setConflictResult(null);
    setConflictLoading(true);
    setFormData(prev => ({ ...prev, start_datetime: `${y}-${m}-${day}T${h}:${mi}` }));
  };

  const handleFindBestSlot = async () => {
    const dt = formData.start_datetime || new Date().toISOString().slice(0, 16);
    setConflictLoading(true);
    try {
      const res = await appointmentAPI.checkConflicts({
        start_datetime: localInputToUTC(dt),
        duration_minutes: parseInt(formData.duration_minutes, 10) || 60,
      });
      if (res.data.suggestions?.length > 0) {
        const best = res.data.suggestions.find(s => s.label === 'optimal') || res.data.suggestions[0];
        applySuggestion(best.datetime_str);
        toast.success('Meilleur créneau sélectionné');
      } else {
        toast.info('Aucun créneau alternatif trouvé');
      }
    } catch (_) {
      toast.error('Erreur lors de la recherche');
    } finally {
      setConflictLoading(false);
    }
  };

  // Load user defaults and charity associations on mount
  useEffect(() => {
    const loadDefaults = async () => {
      try {
        // Fetch user appointment defaults
        const { ok: defaultsOk, data: defaults } = await safeFetchJson(`${API_URL}/api/user-settings/me/appointment-defaults`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (defaultsOk) {
          
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
        const { ok: assocOk, data: assocData } = await safeFetchJson(`${API_URL}/api/charity-associations/`);
        if (assocOk) {
          setCharityAssociations(assocData.associations || []);
        }

        // Fetch default payment method for organizer guarantee
        try {
          const { ok: pmOk, data: pmData } = await safeFetchJson(`${API_URL}/api/user-settings/me/payment-method`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (pmOk && pmData.has_payment_method) {
            setOrgPaymentMethod(pmData.payment_method);
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
        })
        .catch(() => setVideoProviders(null))
        .finally(() => setLoadingProviders(false));
    }
  }, [formData.appointment_type, videoProviders]);

  const steps = [
    { number: 1, title: 'Participants', icon: Users },
    { number: 2, title: 'Informations de base', icon: Calendar },
    { number: 3, title: 'Règles d\'engagement', icon: Shield },
    { number: 4, title: 'Répartition des compensations', icon: DollarSign },
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
    setParticipants([...participants, { first_name: '', last_name: '', email: '' }]);
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
          toast.error('La date et l\'heure de l\'engagement doivent être dans le futur');
          return false;
        }
        if (formData.appointment_type === 'physical' && !formData.location.trim()) {
          toast.error('Le lieu est requis pour un engagement physique');
          return false;
        }
        if (formData.appointment_type === 'video' && !formData.meeting_provider) {
          toast.error('Sélectionnez une plateforme de visioconférence');
          return false;
        }
        if (formData.appointment_type === 'video' && formData.meeting_provider && formData.meeting_provider !== 'external') {
          const p = videoProviders?.[formData.meeting_provider];
          if (p && !p.connected) {
            toast.error(`${p.label || formData.meeting_provider} n'est pas connecté. Configurez-le dans Paramètres > Intégrations.`);
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
          toast.error('Le montant de l\'engagement doit être supérieur à 0');
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
      // Include external event reference for conversion
      if (externalEventId) {
        payload.from_external_event_id = externalEventId;
      }
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
      const errorMessage = error.response?.data?.detail || 'Erreur lors de la création de l\'engagement';
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
      // Include external event reference for conversion
      if (externalEventId) {
        payload.from_external_event_id = externalEventId;
      }
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
      const errorMessage = error.response?.data?.detail || 'Erreur lors de la création de l\'engagement';
      toast.error(typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage));
    } finally {
      setLoading(false);
    }
  };

  // Step 1: Participants
  const renderStep1 = () => (
    <div className="space-y-4">
      <div className="p-3 bg-blue-50 border border-blue-100 rounded-lg">
        <p className="text-sm text-blue-800">
          Ajoutez les personnes qui participeront à cet engagement. Chaque participant recevra une invitation par email.
        </p>
      </div>

      <div className="space-y-3">
        {participants.map((participant, index) => (
          <div key={index} className="group relative border border-slate-200 rounded-lg bg-white hover:border-slate-300 transition-colors" data-testid={`participant-block-${index}`}>
            <div className="flex items-start gap-3 px-3 sm:px-4 py-3">
              <div className="flex items-center justify-center w-7 h-7 rounded-full bg-slate-900 text-white text-xs font-semibold flex-shrink-0 mt-2">
                {index + 1}
              </div>
              <div className="flex-1 grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-3">
                <Input
                  id={`participant-firstname-${index}`}
                  data-testid={`participant-firstname-${index}`}
                  value={participant.first_name}
                  onChange={(e) => updateParticipant(index, 'first_name', e.target.value)}
                  placeholder="Prénom"
                  className="h-11 sm:h-9 text-sm"
                />
                <Input
                  id={`participant-lastname-${index}`}
                  data-testid={`participant-lastname-${index}`}
                  value={participant.last_name}
                  onChange={(e) => updateParticipant(index, 'last_name', e.target.value)}
                  placeholder="Nom"
                  className="h-11 sm:h-9 text-sm"
                />
                <Input
                  id={`participant-email-${index}`}
                  type="email"
                  data-testid={`participant-email-${index}`}
                  value={participant.email}
                  onChange={(e) => updateParticipant(index, 'email', e.target.value)}
                  placeholder="email@exemple.com"
                  className="h-11 sm:h-9 text-sm"
                />
              </div>
              {participants.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeParticipant(index)}
                  className="p-2 text-slate-400 hover:text-rose-500 hover:bg-rose-50 rounded-md transition-colors flex-shrink-0 mt-1.5"
                  data-testid={`remove-participant-${index}`}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <Button
        type="button"
        variant="outline"
        onClick={addParticipant}
        className="w-full border-dashed"
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
        <Label htmlFor="title">Titre de l'engagement *</Label>
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
        <Label htmlFor="appointment_type">Type d'engagement *</Label>
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
          <Label>Visioconférence *</Label>
          {loadingProviders ? (
            <div className="flex items-center gap-2 p-3 bg-slate-50 rounded-lg border border-slate-200">
              <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
              <span className="text-sm text-slate-500">Chargement des intégrations...</span>
            </div>
          ) : (
            <div className="space-y-2" data-testid="meeting-provider-selector">

              {/* ── Microsoft Teams ── */}
              {(() => {
                const p = videoProviders?.teams;
                const canUse = p?.level === 'advanced';
                const isSelected = formData.meeting_provider === 'teams';
                return (
                  <button
                    type="button"
                    onClick={() => canUse && setFormData({ ...formData, meeting_provider: 'teams', meeting_join_url: '' })}
                    className={`w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all ${
                      isSelected ? 'border-violet-400 bg-violet-50 ring-1 ring-violet-200'
                        : canUse ? 'border-slate-200 bg-white hover:border-slate-300 cursor-pointer'
                        : 'border-slate-100 bg-slate-50/60 cursor-not-allowed'
                    }`}
                    disabled={!canUse}
                    data-testid="provider-option-teams"
                  >
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${canUse ? 'bg-violet-50' : 'bg-slate-100'}`}>
                      <Monitor className={`w-4 h-4 ${canUse ? 'text-violet-600' : 'text-slate-400'}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-medium ${canUse ? 'text-slate-900' : 'text-slate-400'}`}>Microsoft Teams</span>
                        {canUse && <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-semibold"><CheckCircle className="w-3 h-3" /> Automatique</span>}
                      </div>
                      <p className={`text-xs mt-0.5 ${canUse ? 'text-slate-500' : 'text-slate-400'}`}>
                        {canUse
                          ? 'Réunion Teams créée automatiquement sous votre identité Microsoft'
                          : p?.level === 'standard'
                            ? 'Réservé aux comptes Microsoft 365 Pro. Activez Teams avancé dans Paramètres > Intégrations.'
                            : p?.unavailable_reason || 'Connectez un compte Outlook dans Paramètres > Intégrations pour activer Teams.'
                        }
                      </p>
                    </div>
                    {isSelected && <Check className="w-4 h-4 text-violet-600 flex-shrink-0" />}
                  </button>
                );
              })()}

              {/* ── Google Meet ── */}
              {(() => {
                const p = videoProviders?.meet;
                const canUse = p?.can_auto_generate;
                const isSelected = formData.meeting_provider === 'meet';
                return (
                  <button
                    type="button"
                    onClick={() => canUse && setFormData({ ...formData, meeting_provider: 'meet', meeting_join_url: '' })}
                    className={`w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all ${
                      isSelected ? 'border-emerald-400 bg-emerald-50 ring-1 ring-emerald-200'
                        : canUse ? 'border-slate-200 bg-white hover:border-slate-300 cursor-pointer'
                        : 'border-slate-100 bg-slate-50/60 cursor-not-allowed'
                    }`}
                    disabled={!canUse}
                    data-testid="provider-option-meet"
                  >
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${canUse ? 'bg-emerald-50' : 'bg-slate-100'}`}>
                      <Video className={`w-4 h-4 ${canUse ? 'text-emerald-600' : 'text-slate-400'}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-medium ${canUse ? 'text-slate-900' : 'text-slate-400'}`}>Google Meet</span>
                        {canUse && <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-semibold"><CheckCircle className="w-3 h-3" /> Automatique</span>}
                      </div>
                      <p className={`text-xs mt-0.5 ${canUse ? 'text-slate-500' : 'text-slate-400'}`}>
                        {canUse
                          ? `Réunion Meet créée automatiquement via votre compte Google`
                          : p?.unavailable_reason || 'Connectez un compte Google dans les paramètres'
                        }
                      </p>
                    </div>
                    {isSelected && <Check className="w-4 h-4 text-emerald-600 flex-shrink-0" />}
                  </button>
                );
              })()}

              {/* ── Zoom ── */}
              {(() => {
                const p = videoProviders?.zoom;
                const canUse = p?.can_auto_generate;
                const isSelected = formData.meeting_provider === 'zoom';
                return (
                  <button
                    type="button"
                    onClick={() => canUse && setFormData({ ...formData, meeting_provider: 'zoom', meeting_join_url: '' })}
                    className={`w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all ${
                      isSelected ? 'border-blue-400 bg-blue-50 ring-1 ring-blue-200'
                        : canUse ? 'border-slate-200 bg-white hover:border-slate-300 cursor-pointer'
                        : 'border-slate-100 bg-slate-50/60 cursor-not-allowed'
                    }`}
                    disabled={!canUse}
                    data-testid="provider-option-zoom"
                  >
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${canUse ? 'bg-blue-50' : 'bg-slate-100'}`}>
                      <Video className={`w-4 h-4 ${canUse ? 'text-blue-600' : 'text-slate-400'}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-medium ${canUse ? 'text-slate-900' : 'text-slate-400'}`}>Zoom</span>
                        {canUse && <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-semibold"><CheckCircle className="w-3 h-3" /> Automatique</span>}
                      </div>
                      <p className={`text-xs mt-0.5 ${canUse ? 'text-slate-500' : 'text-slate-400'}`}>
                        {canUse
                          ? `Réunion Zoom créée automatiquement via votre compte Zoom`
                          : p?.unavailable_reason || 'Connectez votre compte Zoom dans les paramètres'
                        }
                      </p>
                    </div>
                    {isSelected && <Check className="w-4 h-4 text-blue-600 flex-shrink-0" />}
                  </button>
                );
              })()}

              {/* ── Autre plateforme ── */}
              {(() => {
                const isSelected = formData.meeting_provider === 'external';
                return (
                  <button
                    type="button"
                    onClick={() => setFormData({ ...formData, meeting_provider: 'external', meeting_join_url: '' })}
                    className={`w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all ${
                      isSelected ? 'border-slate-400 bg-slate-50 ring-1 ring-slate-300'
                        : 'border-slate-200 bg-white hover:border-slate-300 cursor-pointer'
                    }`}
                    data-testid="provider-option-external"
                  >
                    <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center flex-shrink-0">
                      <Link2 className="w-4 h-4 text-slate-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <span className="text-sm font-medium text-slate-900">Autre plateforme</span>
                      <p className="text-xs text-slate-500 mt-0.5">Collez un lien Teams, Zoom, Google Meet ou autre</p>
                    </div>
                    {isSelected && <Check className="w-4 h-4 text-slate-600 flex-shrink-0" />}
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

          {/* Auto-creation confirmation for connected providers */}
          {formData.meeting_provider && formData.meeting_provider !== 'external' && (
            formData.meeting_provider === 'teams'
              ? videoProviders?.teams?.level === 'advanced'
              : videoProviders?.[formData.meeting_provider]?.can_auto_generate
          ) && (
            <div className="flex items-start gap-2 p-2.5 bg-blue-50 border border-blue-100 rounded-lg mt-2">
              <Zap className="w-3.5 h-3.5 text-blue-600 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-blue-700">
                Le lien de réunion sera créé automatiquement et inclus dans les invitations.
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
            La date et l'heure de l'engagement doivent être dans le futur
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

      {/* ── Conflict Detection Panel ── */}
      {formData.start_datetime && (
        <div data-testid="conflict-panel">
          {conflictLoading ? (
            <div className="flex items-center gap-2 text-sm text-slate-400 py-2">
              <Loader2 className="w-4 h-4 animate-spin" /> Vérification de la disponibilité...
            </div>
          ) : conflictResult ? (
            <div className="space-y-3">
              {/* Status badge */}
              {conflictResult.status === 'conflict' && (
                <div className="border border-red-200 bg-red-50 rounded-lg p-4" data-testid="conflict-alert">
                  <div className="flex items-start gap-2.5">
                    <XCircle className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
                    <div className="flex-1">
                      <p className="text-sm font-bold text-red-700">Conflit détecté</p>
                      <p className="text-xs text-red-600 mt-0.5">Ce créneau chevauche un engagement existant</p>
                      {conflictResult.conflicts?.map((c, i) => {
                        const srcCfg = {
                          nlyt: { label: 'NLYT', cls: 'bg-indigo-100 text-indigo-700 border-indigo-200', icon: <Calendar className="w-3 h-3" /> },
                          google: { label: 'Google', cls: 'bg-red-50 text-red-600 border-red-200', icon: <ExternalLink className="w-3 h-3" /> },
                          outlook: { label: 'Outlook', cls: 'bg-sky-50 text-sky-700 border-sky-200', icon: <ExternalLink className="w-3 h-3" /> },
                        }[c.source] || { label: c.source, cls: 'bg-slate-100 text-slate-600 border-slate-200', icon: null };
                        return (
                          <div key={i} className="mt-2.5 bg-white border border-red-100 rounded-lg px-3 py-2.5 shadow-sm" data-testid={`conflict-item-${i}`}>
                            <div className="flex items-center justify-between gap-2">
                              <p className="text-[13px] font-semibold text-slate-800">{c.title}</p>
                              <span className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full border ${srcCfg.cls}`} data-testid={`conflict-source-${i}`}>
                                {srcCfg.icon}{srcCfg.label}
                              </span>
                            </div>
                            <p className="text-xs text-slate-500 mt-1">{formatSlotRange(c.start, c.end)}</p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}
              {conflictResult.status === 'warning' && (
                <div className="border border-amber-200 bg-amber-50 rounded-lg p-4" data-testid="warning-alert">
                  <div className="flex items-start gap-2.5">
                    <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" />
                    <div className="flex-1">
                      <p className="text-sm font-bold text-amber-700">Enchaînement serré</p>
                      <p className="text-xs text-amber-600 mt-0.5">Moins de 30 min entre ce créneau et un engagement proche</p>
                      {conflictResult.warnings?.map((w, i) => {
                        const srcCfg = {
                          nlyt: { label: 'NLYT', cls: 'bg-indigo-100 text-indigo-700 border-indigo-200', icon: <Calendar className="w-3 h-3" /> },
                          google: { label: 'Google', cls: 'bg-red-50 text-red-600 border-red-200', icon: <ExternalLink className="w-3 h-3" /> },
                          outlook: { label: 'Outlook', cls: 'bg-sky-50 text-sky-700 border-sky-200', icon: <ExternalLink className="w-3 h-3" /> },
                        }[w.source] || { label: w.source, cls: 'bg-slate-100 text-slate-600 border-slate-200', icon: null };
                        return (
                          <div key={i} className="mt-2.5 bg-white border border-amber-100 rounded-lg px-3 py-2.5 shadow-sm" data-testid={`warning-item-${i}`}>
                            <div className="flex items-center justify-between gap-2">
                              <p className="text-[13px] font-semibold text-slate-800">{w.title}</p>
                              <span className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full border ${srcCfg.cls}`} data-testid={`warning-source-${i}`}>
                                {srcCfg.icon}{srcCfg.label}
                              </span>
                            </div>
                            <p className="text-xs text-slate-500 mt-1">{formatSlotRange(w.start, w.end)}</p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}
              {conflictResult.status === 'available' && (
                <div className="flex items-center gap-2 py-2" data-testid="available-badge">
                  <CheckCircle className="w-4 h-4 text-emerald-500" />
                  <span className="text-sm text-emerald-700 font-medium">Créneau disponible</span>
                  {conflictResult.sources_checked?.length > 1 ? (
                    <span className="text-[11px] text-slate-400 ml-1">vérifié sur {conflictResult.sources_checked.map(s => s === 'nlyt' ? 'NLYT' : s.charAt(0).toUpperCase() + s.slice(1)).join(' + ')}</span>
                  ) : (
                    <span className="text-[11px] text-slate-400 ml-1">aucun conflit NLYT détecté</span>
                  )}
                </div>
              )}

              {/* Suggestions */}
              {conflictResult.suggestions?.length > 0 && (
                <div className="space-y-2" data-testid="suggestions-panel">
                  <p className="text-xs font-semibold text-slate-600">Créneaux alternatifs disponibles :</p>
                  <div className="flex flex-wrap gap-2">
                    {conflictResult.suggestions.map((s, i) => {
                      const d = new Date(s.datetime_str);
                      const dayLabel = d.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' });
                      const timeLabel = d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
                      const labelCfg = {
                        optimal: { text: 'optimal', cls: 'border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 hover:border-emerald-400' },
                        comfortable: { text: 'confort', cls: 'border-blue-300 bg-blue-50 text-blue-700 hover:bg-blue-100 hover:border-blue-400' },
                        tight: { text: 'serré', cls: 'border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100 hover:border-amber-400' },
                      }[s.label] || { text: s.label, cls: 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100' };
                      return (
                        <button
                          key={i}
                          type="button"
                          onClick={() => applySuggestion(s.datetime_str)}
                          className={`px-3 py-2 rounded-lg border text-xs font-medium transition-all cursor-pointer shadow-sm hover:shadow ${labelCfg.cls}`}
                          data-testid={`suggestion-${i}`}
                        >
                          <span className="font-semibold">{dayLabel} {timeLabel}</span>
                          <span className="opacity-50 ml-1.5 text-[10px]">{labelCfg.text}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Confidence + transparency */}
              <div className="flex items-center gap-2 pt-2" data-testid="confidence-indicator">
                <div className={`w-2 h-2 rounded-full ${conflictResult.confidence === 'high' ? 'bg-emerald-500' : 'bg-amber-400'}`} />
                <span className="text-[11px] text-slate-400">
                  {conflictResult.confidence === 'high' ? 'Fiabilité élevée' : 'Fiabilité partielle'}
                  {conflictResult.confidence_detail ? ` — ${conflictResult.confidence_detail}` : ''}
                </span>
              </div>
            </div>
          ) : null}

          {/* Smart find */}
          <div className="flex items-center justify-between mt-2">
            <button
              type="button"
              onClick={handleFindBestSlot}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 transition-colors"
              disabled={conflictLoading}
              data-testid="find-best-slot-btn"
            >
              <Sparkles className="w-3.5 h-3.5" /> Trouver le meilleur créneau
            </button>
            {conflictResult?.sources_checked?.length > 1 && (
              <div className="flex items-center gap-1.5 text-[11px] text-emerald-500">
                <CheckCircle className="w-3 h-3" />
                <span>Calendriers connectés actifs</span>
              </div>
            )}
          </div>
        </div>
      )}
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
        <Label htmlFor="tolerated_delay_minutes">Dépassement toléré (minutes) *</Label>
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
          Délai de grâce avant application de la compensation
        </p>
      </div>

      <div>
        <Label htmlFor="cancellation_deadline_hours">Délai de désengagement (heures) *</Label>
        <Input
          id="cancellation_deadline_hours"
          type="number"
          data-testid="appointment-cancellation-input"
          value={formData.cancellation_deadline_hours}
          onChange={(e) => setFormData({ ...formData, cancellation_deadline_hours: parseInt(e.target.value) || 0 })}
          min="0"
          className="mt-1"
        />
        {(() => {
          if (!formData.start_datetime) return null;
          const now = new Date();
          const start = new Date(formData.start_datetime);
          const hoursUntil = Math.max(0, (start - now) / 3600000);
          const configured = formData.cancellation_deadline_hours || 0;
          if (configured > hoursUntil && hoursUntil > 0) {
            const effective = Math.floor(hoursUntil);
            return (
              <div className="flex items-start gap-2 mt-2 p-2.5 bg-amber-50 border border-amber-200 rounded-lg" data-testid="short-notice-warning">
                <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
                <p className="text-xs text-amber-700">
                  L'engagement est dans <strong>{hoursUntil < 1 ? `${Math.round(hoursUntil * 60)} min` : `${hoursUntil.toFixed(1)}h`}</strong>.
                  Le délai de désengagement sera automatiquement réduit à <strong>{effective}h</strong> (au lieu de {configured}h).
                </p>
              </div>
            );
          }
          return null;
        })()}
        <p className="text-sm text-slate-500 mt-1">
          Délai minimum pour se désengager sans compensation
        </p>
      </div>

      <div>
        <Label htmlFor="penalty_amount">Montant de l'engagement (€) *</Label>
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
          Montant de la garantie d'engagement en cas de dépassement ou d'absence
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
            Définissez comment les compensations collectées seront réparties.
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
          <h3 className="text-xl font-semibold text-slate-900 mb-6">Récapitulatif de l'engagement solidaire</h3>
          
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
                  <span className="text-slate-600">Dépassement toléré:</span>
                  <span className="font-medium text-slate-900">{formData.tolerated_delay_minutes} minutes</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">Délai d'annulation:</span>
                  <span className="font-medium text-slate-900">{formData.cancellation_deadline_hours} heures</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">Compensation:</span>
                  <span className="font-medium text-emerald-600">{formData.penalty_amount} {formData.penalty_currency.toUpperCase()}</span>
                </div>
              </div>
            </div>

            <div>
              <h4 className="font-medium text-slate-700 mb-2">Répartition des compensations</h4>
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
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Nouvel engagement' },
      ]} />

      <div className="max-w-4xl mx-auto px-4 md:px-6 pb-12">

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
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900 mb-2">Créer un engagement solidaire</h1>
          <p className="text-slate-600 mb-4">Définissez les conditions de votre engagement solidaire</p>
          
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
                <div className="absolute left-0 right-0 sm:right-auto top-full mt-2 w-auto sm:w-80 bg-white rounded-lg shadow-lg border border-slate-200 z-20" data-testid="wizard-workspace-dropdown">
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

        <div className="mb-8 overflow-x-auto scrollbar-none -mx-1 px-1">
          <div className="flex items-center justify-between min-w-[340px]">
            {steps.map((step, index) => (
              <React.Fragment key={step.number}>
                <div className="flex flex-col items-center flex-shrink-0">
                  <div className={`w-10 h-10 md:w-12 md:h-12 rounded-full flex items-center justify-center ${
                    currentStep === step.number
                      ? 'bg-slate-900 text-white'
                      : currentStep > step.number
                      ? 'bg-emerald-600 text-white'
                      : 'bg-slate-200 text-slate-600'
                  }`}>
                    {currentStep > step.number ? <Check className="w-5 h-5 md:w-6 md:h-6" /> : <step.icon className="w-5 h-5 md:w-6 md:h-6" />}
                  </div>
                  <span className={`text-[11px] md:text-xs mt-2 text-center max-w-[60px] md:max-w-[100px] ${
                    currentStep === step.number ? 'font-medium text-slate-900' : 'text-slate-600'
                  }`}>
                    {step.title}
                  </span>
                </div>
                {index < steps.length - 1 && (
                  <div className={`flex-1 h-1 mx-1 md:mx-4 min-w-[12px] ${
                    currentStep > step.number ? 'bg-emerald-600' : 'bg-slate-200'
                  }`} />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-4 sm:p-6 md:p-8">
          {fromExternalData && (
            <div className="mb-6 p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-start gap-3" data-testid="from-external-banner">
              <Info className="w-4 h-4 text-slate-500 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm text-slate-700">
                  Pré-rempli à partir de votre événement {externalSource === 'google' ? 'Google' : externalSource === 'outlook' ? 'Outlook' : 'externe'}. Tous les champs restent modifiables.
                </p>
              </div>
            </div>
          )}
          {currentStep === 1 && renderStep1()}
          {currentStep === 2 && renderStep2()}
          {currentStep === 3 && renderStep3()}
          {currentStep === 4 && renderStep4()}
          {currentStep === 5 && renderStep5()}

          <div className="flex flex-col-reverse sm:flex-row sm:justify-between gap-3 mt-8 pt-6 border-t border-slate-200">
            <Button
              type="button"
              variant="outline"
              onClick={handleBack}
              disabled={currentStep === 1}
              className="min-h-[44px] sm:min-h-0"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Précédent
            </Button>

            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-3">
              {currentStep === 2 && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleQuickCreate}
                  disabled={loading}
                  className="border-amber-300 text-amber-700 hover:bg-amber-50 hover:border-amber-400 min-h-[44px] sm:min-h-0"
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
                <Button type="button" onClick={handleNext} data-testid="wizard-next-btn" className="min-h-[44px] sm:min-h-0">
                  Suivant
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              ) : (
                <Button type="button" onClick={handleSubmit} disabled={loading} data-testid="wizard-create-btn" className="min-h-[44px] sm:min-h-0">
                  {loading ? 'Création...' : 'Créer l\'engagement solidaire'}
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
