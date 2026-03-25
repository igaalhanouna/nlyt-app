import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useWorkspace } from '../../contexts/WorkspaceContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { toast } from 'sonner';

export default function CreateWorkspace() {
  const navigate = useNavigate();
  const { createWorkspace } = useWorkspace();
  const [formData, setFormData] = useState({
    name: '',
    description: ''
  });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      await createWorkspace(formData.name, formData.description);
      toast.success('Workspace créé');
      navigate('/dashboard');
    } catch (error) {
      toast.error('Erreur lors de la création');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background py-12 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Créer un workspace</h1>
          <p className="text-slate-600">Organisez vos engagements dans des espaces dédiés</p>
        </div>

        <div className="bg-white p-8 rounded-lg shadow-sm border border-slate-200">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <Label htmlFor="name">Nom du workspace *</Label>
              <Input
                id="name"
                data-testid="workspace-name-input"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
                placeholder="Ex: Cabinet Médical, Consulting, etc."
                className="mt-1"
              />
            </div>

            <div>
              <Label htmlFor="description">Description (optionnel)</Label>
              <Textarea
                id="description"
                data-testid="workspace-description-input"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Ajoutez une description pour votre workspace"
                className="mt-1"
                rows={4}
              />
            </div>

            <div className="flex gap-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate('/workspace/select')}
                className="flex-1"
              >
                Annuler
              </Button>
              <Button type="submit" disabled={loading} className="flex-1" data-testid="workspace-submit-btn">
                {loading ? 'Création...' : 'Créer le workspace'}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}