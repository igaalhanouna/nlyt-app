import React, { useState, useEffect, useCallback } from 'react';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Plus, Pencil, X, ExternalLink, Globe, Mail } from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

function AssociationForm({ initial, onSave, onCancel, saving }) {
  const [form, setForm] = useState({
    name: initial?.name || '',
    description: initial?.description || '',
    website: initial?.website || '',
    contact_email: initial?.contact_email || '',
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!form.name.trim()) { toast.error('Le nom est requis'); return; }
    onSave({
      name: form.name.trim(),
      description: form.description.trim(),
      website: form.website.trim() || null,
      contact_email: form.contact_email.trim() || null,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <Label htmlFor="assoc-name">Nom *</Label>
        <Input id="assoc-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required className="mt-1" data-testid="assoc-form-name" />
      </div>
      <div>
        <Label htmlFor="assoc-desc">Description</Label>
        <Input id="assoc-desc" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="mt-1" data-testid="assoc-form-description" />
      </div>
      <div>
        <Label htmlFor="assoc-web">Site web</Label>
        <Input id="assoc-web" type="url" value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} placeholder="https://..." className="mt-1" data-testid="assoc-form-website" />
      </div>
      <div>
        <Label htmlFor="assoc-email">Email de contact</Label>
        <Input id="assoc-email" type="email" value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })} className="mt-1" data-testid="assoc-form-email" />
      </div>
      <div className="flex justify-end gap-3 pt-2">
        <Button type="button" variant="outline" onClick={onCancel} data-testid="assoc-form-cancel">Annuler</Button>
        <Button type="submit" disabled={saving} data-testid="assoc-form-submit">{saving ? 'Enregistrement...' : (initial ? 'Modifier' : 'Ajouter')}</Button>
      </div>
    </form>
  );
}

export default function AdminAssociations() {
  const [associations, setAssociations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editAssoc, setEditAssoc] = useState(null);
  const [saving, setSaving] = useState(false);

  const token = localStorage.getItem('nlyt_token');
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };

  const fetchAssociations = useCallback(async () => {
    try {
      const resp = await fetch(`${API_URL}/api/charity-associations/admin/list`, { headers });
      if (!resp.ok) throw new Error('Erreur chargement');
      const data = await resp.json();
      setAssociations(data.associations || []);
    } catch (err) {
      toast.error('Impossible de charger les associations');
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fetchAssociations(); }, [fetchAssociations]);

  const handleCreate = async (formData) => {
    setSaving(true);
    try {
      const resp = await fetch(`${API_URL}/api/charity-associations/admin/create`, { method: 'POST', headers, body: JSON.stringify(formData) });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Erreur');
      toast.success(`${data.name} ajoutée`);
      setShowForm(false);
      fetchAssociations();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async (formData) => {
    setSaving(true);
    try {
      const resp = await fetch(`${API_URL}/api/charity-associations/admin/${editAssoc.association_id}`, { method: 'PUT', headers, body: JSON.stringify(formData) });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Erreur');
      toast.success(`${data.name} modifiée`);
      setEditAssoc(null);
      fetchAssociations();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (assoc) => {
    try {
      const resp = await fetch(`${API_URL}/api/charity-associations/admin/${assoc.association_id}/toggle`, { method: 'PATCH', headers });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Erreur');
      toast.success(data.message);
      fetchAssociations();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const activeCount = associations.filter((a) => a.is_active).length;

  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Administration', href: '/admin/review' },
        { label: 'Associations' },
      ]} />
      <div className="max-w-5xl mx-auto px-6 pb-12">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900" data-testid="admin-associations-title">Associations caritatives</h1>
            <p className="text-sm text-slate-500 mt-1">{activeCount} active{activeCount !== 1 ? 's' : ''} sur {associations.length} au total</p>
          </div>
          {!showForm && !editAssoc && (
            <Button onClick={() => setShowForm(true)} data-testid="add-association-btn">
              <Plus className="w-4 h-4 mr-2" /> Ajouter
            </Button>
          )}
        </div>

        {/* Create form */}
        {showForm && (
          <div className="bg-white p-6 rounded-lg border border-slate-200 mb-6" data-testid="create-association-form">
            <h2 className="text-lg font-semibold text-slate-800 mb-4">Nouvelle association</h2>
            <AssociationForm onSave={handleCreate} onCancel={() => setShowForm(false)} saving={saving} />
          </div>
        )}

        {/* Edit form */}
        {editAssoc && (
          <div className="bg-white p-6 rounded-lg border border-blue-200 mb-6" data-testid="edit-association-form">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-800">Modifier : {editAssoc.name}</h2>
              <button onClick={() => setEditAssoc(null)} className="text-slate-400 hover:text-slate-600"><X className="w-5 h-5" /></button>
            </div>
            <AssociationForm initial={editAssoc} onSave={handleUpdate} onCancel={() => setEditAssoc(null)} saving={saving} />
          </div>
        )}

        {/* List */}
        {loading ? (
          <div className="text-center py-12 text-slate-500">Chargement...</div>
        ) : associations.length === 0 ? (
          <div className="text-center py-12 text-slate-500">Aucune association enregistrée</div>
        ) : (
          <div className="space-y-3" data-testid="associations-list">
            {associations.map((assoc) => (
              <div
                key={assoc.association_id}
                className={`bg-white rounded-lg border p-4 flex items-center justify-between gap-4 transition-opacity ${assoc.is_active ? 'border-slate-200' : 'border-slate-100 opacity-60'}`}
                data-testid={`assoc-row-${assoc.association_id}`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-900 truncate">{assoc.name}</span>
                    {!assoc.is_active && (
                      <span className="inline-flex items-center text-xs font-medium bg-slate-100 text-slate-500 px-2 py-0.5 rounded">Inactive</span>
                    )}
                  </div>
                  {assoc.description && <p className="text-sm text-slate-500 mt-0.5 truncate">{assoc.description}</p>}
                  <div className="flex items-center gap-4 mt-1">
                    {assoc.website && (
                      <a href={assoc.website} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 hover:underline inline-flex items-center gap-1">
                        <Globe className="w-3 h-3" /> Site web <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                    {assoc.contact_email && (
                      <span className="text-xs text-slate-400 inline-flex items-center gap-1">
                        <Mail className="w-3 h-3" /> {assoc.contact_email}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-300 mt-1 font-mono">{assoc.association_id}</p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => { setEditAssoc(assoc); setShowForm(false); }}
                    data-testid={`edit-assoc-${assoc.association_id}`}
                  >
                    <Pencil className="w-4 h-4" />
                  </Button>
                  <Button
                    variant={assoc.is_active ? 'outline' : 'default'}
                    size="sm"
                    onClick={() => handleToggle(assoc)}
                    data-testid={`toggle-assoc-${assoc.association_id}`}
                  >
                    {assoc.is_active ? 'Désactiver' : 'Activer'}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
