import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { ArrowLeft, User, Settings, Clock, Euro, Heart, Save, Loader2, Check, AlertCircle } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function Profile() {
  const { user, token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [associations, setAssociations] = useState([]);
  const [hasChanges, setHasChanges] = useState(false);
  
  // Profile data
  const [profileData, setProfileData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    // Appointment defaults
    default_cancellation_hours: 24,
    default_late_tolerance_minutes: 15,
    default_penalty_amount: 50,
    default_penalty_currency: 'eur',
    default_participant_percent: 70,
    default_charity_percent: 0,
    default_charity_association_id: ''
  });

  // Fetch user settings and associations on mount
  useEffect(() => {
    fetchUserSettings();
    fetchAssociations();
  }, []);

  const fetchUserSettings = async () => {
    try {
      const response = await fetch(`${API_URL}/api/user-settings/me`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        const defaults = data.appointment_defaults || {};
        
        setProfileData({
          first_name: data.first_name || '',
          last_name: data.last_name || '',
          email: data.email || '',
          phone: data.phone || '',
          default_cancellation_hours: defaults.default_cancellation_hours ?? 24,
          default_late_tolerance_minutes: defaults.default_late_tolerance_minutes ?? 15,
          default_penalty_amount: defaults.default_penalty_amount ?? 50,
          default_penalty_currency: defaults.default_penalty_currency ?? 'eur',
          default_participant_percent: defaults.default_participant_percent ?? 70,
          default_charity_percent: defaults.default_charity_percent ?? 0,
          default_charity_association_id: defaults.default_charity_association_id || ''
        });
      }
    } catch (error) {
      console.error('Error fetching settings:', error);
      toast.error('Erreur lors du chargement des paramètres');
    } finally {
      setLoading(false);
    }
  };

  const fetchAssociations = async () => {
    try {
      const response = await fetch(`${API_URL}/api/charity-associations/`);
      if (response.ok) {
        const data = await response.json();
        setAssociations(data.associations || []);
      }
    } catch (error) {
      console.error('Error fetching associations:', error);
    }
  };

  const handleInputChange = (field, value) => {
    setProfileData(prev => ({ ...prev, [field]: value }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const response = await fetch(`${API_URL}/api/user-settings/me`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          first_name: profileData.first_name,
          last_name: profileData.last_name,
          phone: profileData.phone,
          appointment_defaults: {
            default_cancellation_hours: parseInt(profileData.default_cancellation_hours),
            default_late_tolerance_minutes: parseInt(profileData.default_late_tolerance_minutes),
            default_penalty_amount: parseFloat(profileData.default_penalty_amount),
            default_penalty_currency: profileData.default_penalty_currency,
            default_participant_percent: parseFloat(profileData.default_participant_percent),
            default_charity_percent: parseFloat(profileData.default_charity_percent),
            default_charity_association_id: profileData.default_charity_association_id || null
          }
        })
      });

      if (response.ok) {
        toast.success('Paramètres enregistrés avec succès');
        setHasChanges(false);
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Erreur lors de la sauvegarde');
      }
    } catch (error) {
      console.error('Error saving settings:', error);
      toast.error('Erreur lors de la sauvegarde');
    } finally {
      setSaving(false);
    }
  };

  // Calculate platform percent
  const platformPercent = 100 - profileData.default_participant_percent - profileData.default_charity_percent;
  const isDistributionValid = platformPercent >= 0 && platformPercent <= 100;

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <Link to="/dashboard">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Retour
              </Button>
            </Link>
            <h1 className="text-2xl font-bold text-slate-900">Mon profil</h1>
          </div>
          
          <Button 
            onClick={handleSave} 
            disabled={saving || !hasChanges}
            className="bg-slate-900 hover:bg-slate-800"
            data-testid="save-profile-btn"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            Enregistrer
          </Button>
        </div>

        {/* Section 1: Informations personnelles */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center">
              <User className="w-5 h-5 text-slate-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Informations personnelles</h2>
              <p className="text-sm text-slate-500">Vos informations de profil</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <Label htmlFor="first_name">Prénom</Label>
              <Input
                id="first_name"
                value={profileData.first_name}
                onChange={(e) => handleInputChange('first_name', e.target.value)}
                className="mt-1"
                data-testid="profile-firstname"
              />
            </div>
            <div>
              <Label htmlFor="last_name">Nom</Label>
              <Input
                id="last_name"
                value={profileData.last_name}
                onChange={(e) => handleInputChange('last_name', e.target.value)}
                className="mt-1"
                data-testid="profile-lastname"
              />
            </div>
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                value={profileData.email}
                disabled
                className="mt-1 bg-slate-50"
              />
              <p className="text-xs text-slate-400 mt-1">L'email ne peut pas être modifié</p>
            </div>
            <div>
              <Label htmlFor="phone">Téléphone</Label>
              <Input
                id="phone"
                value={profileData.phone}
                onChange={(e) => handleInputChange('phone', e.target.value)}
                placeholder="+33 6 12 34 56 78"
                className="mt-1"
                data-testid="profile-phone"
              />
            </div>
          </div>
        </div>

        {/* Section 2: Paramètres par défaut des rendez-vous */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
              <Settings className="w-5 h-5 text-emerald-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Paramètres par défaut des rendez-vous</h2>
              <p className="text-sm text-slate-500">Ces valeurs seront préremplies dans le wizard de création</p>
            </div>
          </div>

          {/* Règles d'engagement */}
          <div className="mb-8">
            <h3 className="text-md font-medium text-slate-800 mb-4 flex items-center gap-2">
              <Clock className="w-4 h-4" />
              Règles d'engagement par défaut
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <Label htmlFor="cancellation_hours">Délai d'annulation (heures)</Label>
                <Input
                  id="cancellation_hours"
                  type="number"
                  min="1"
                  max="168"
                  value={profileData.default_cancellation_hours}
                  onChange={(e) => handleInputChange('default_cancellation_hours', e.target.value)}
                  className="mt-1"
                  data-testid="profile-cancellation-hours"
                />
                <p className="text-xs text-slate-400 mt-1">Minimum 1h, maximum 168h (7 jours)</p>
              </div>
              
              <div>
                <Label htmlFor="late_tolerance">Retard toléré (minutes)</Label>
                <Input
                  id="late_tolerance"
                  type="number"
                  min="0"
                  max="60"
                  value={profileData.default_late_tolerance_minutes}
                  onChange={(e) => handleInputChange('default_late_tolerance_minutes', e.target.value)}
                  className="mt-1"
                  data-testid="profile-late-tolerance"
                />
                <p className="text-xs text-slate-400 mt-1">0 = aucune tolérance</p>
              </div>
              
              <div>
                <Label htmlFor="penalty_amount">Montant de pénalité par défaut (€)</Label>
                <Input
                  id="penalty_amount"
                  type="number"
                  min="0"
                  max="10000"
                  step="0.01"
                  value={profileData.default_penalty_amount}
                  onChange={(e) => handleInputChange('default_penalty_amount', e.target.value)}
                  className="mt-1"
                  data-testid="profile-penalty-amount"
                />
              </div>
            </div>
          </div>

          {/* Répartition des pénalités */}
          <div className="mb-8">
            <h3 className="text-md font-medium text-slate-800 mb-4 flex items-center gap-2">
              <Euro className="w-4 h-4" />
              Répartition des pénalités par défaut
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <Label htmlFor="participant_percent">Part participant affecté (%)</Label>
                <Input
                  id="participant_percent"
                  type="number"
                  min="0"
                  max="100"
                  value={profileData.default_participant_percent}
                  onChange={(e) => handleInputChange('default_participant_percent', parseFloat(e.target.value) || 0)}
                  className="mt-1"
                  data-testid="profile-participant-percent"
                />
              </div>
              
              <div>
                <Label htmlFor="charity_percent">Part don caritatif (%)</Label>
                <Input
                  id="charity_percent"
                  type="number"
                  min="0"
                  max="100"
                  value={profileData.default_charity_percent}
                  onChange={(e) => handleInputChange('default_charity_percent', parseFloat(e.target.value) || 0)}
                  className="mt-1"
                  data-testid="profile-charity-percent"
                />
              </div>
              
              <div>
                <Label>Part plateforme NLYT (%)</Label>
                <div className={`mt-1 px-3 py-2 border rounded-md bg-slate-50 ${!isDistributionValid ? 'border-red-300 bg-red-50' : 'border-slate-200'}`}>
                  <span className={`font-medium ${!isDistributionValid ? 'text-red-600' : 'text-slate-700'}`}>
                    {platformPercent.toFixed(0)}%
                  </span>
                  <span className="text-xs text-slate-400 ml-2">(calculé automatiquement)</span>
                </div>
              </div>
            </div>

            {!isDistributionValid && (
              <div className="mt-4 flex items-center gap-2 text-red-600 text-sm">
                <AlertCircle className="w-4 h-4" />
                La somme des pourcentages ne peut pas dépasser 100%
              </div>
            )}

            {/* Visual distribution bar */}
            {isDistributionValid && (
              <div className="mt-4">
                <div className="h-3 bg-slate-100 rounded-full overflow-hidden flex">
                  <div 
                    className="bg-emerald-500 transition-all"
                    style={{ width: `${profileData.default_participant_percent}%` }}
                    title={`Participant: ${profileData.default_participant_percent}%`}
                  />
                  <div 
                    className="bg-pink-500 transition-all"
                    style={{ width: `${profileData.default_charity_percent}%` }}
                    title={`Charity: ${profileData.default_charity_percent}%`}
                  />
                  <div 
                    className="bg-slate-400 transition-all"
                    style={{ width: `${platformPercent}%` }}
                    title={`Plateforme: ${platformPercent}%`}
                  />
                </div>
                <div className="flex justify-between text-xs text-slate-500 mt-2">
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 bg-emerald-500 rounded-full"></span>
                    Participant
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 bg-pink-500 rounded-full"></span>
                    Caritatif
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 bg-slate-400 rounded-full"></span>
                    Plateforme
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Association caritative */}
          <div>
            <h3 className="text-md font-medium text-slate-800 mb-4 flex items-center gap-2">
              <Heart className="w-4 h-4 text-pink-500" />
              Association caritative par défaut
            </h3>
            
            <div className="max-w-md">
              <Label htmlFor="charity_association">Association bénéficiaire</Label>
              <Select
                value={profileData.default_charity_association_id || "none"}
                onValueChange={(value) => handleInputChange('default_charity_association_id', value === "none" ? '' : value)}
              >
                <SelectTrigger className="mt-1" data-testid="profile-charity-association">
                  <SelectValue placeholder="Sélectionnez une association (optionnel)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Aucune association</SelectItem>
                  {associations.map((assoc) => (
                    <SelectItem key={assoc.association_id} value={assoc.association_id}>
                      {assoc.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-slate-400 mt-2">
                Cette association recevra la part caritative des pénalités de vos rendez-vous par défaut.
                Vous pourrez toujours changer l'association pour chaque rendez-vous.
              </p>
            </div>
          </div>
        </div>

        {/* Info box */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
              <Check className="w-4 h-4 text-blue-600" />
            </div>
            <div>
              <h4 className="font-medium text-blue-900">Comment ça marche ?</h4>
              <p className="text-sm text-blue-700 mt-1">
                Ces paramètres seront automatiquement préremplis lorsque vous créez un nouveau rendez-vous.
                Vous pouvez toujours les modifier pour chaque rendez-vous individuel, sans que cela n'affecte vos paramètres par défaut.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
