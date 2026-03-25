import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Building2, ChevronDown, Check, Plus, Trash2, Pencil, X, Loader2 } from 'lucide-react';
import { useWorkspace } from '../../contexts/WorkspaceContext';
import { toast } from 'sonner';
import SettingsPageLayout from '../../components/SettingsPageLayout';

export default function WorkspaceSettings() {
  const navigate = useNavigate();
  const { currentWorkspace, workspaces, selectWorkspace, createWorkspace, updateWorkspace } = useWorkspace();
  const [workspaceDropdownOpen, setWorkspaceDropdownOpen] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState('');
  const [newWorkspaceDescription, setNewWorkspaceDescription] = useState('');
  const [creatingWorkspace, setCreatingWorkspace] = useState(false);

  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [saving, setSaving] = useState(false);
  const nameInputRef = useRef(null);

  useEffect(() => {
    if (editing && nameInputRef.current) nameInputRef.current.focus();
  }, [editing]);

  const startEditing = () => {
    setEditName(currentWorkspace?.name || '');
    setEditDescription(currentWorkspace?.description || '');
    setEditing(true);
  };

  const cancelEditing = () => {
    setEditing(false);
  };

  const handleSaveEdit = async () => {
    if (!editName.trim()) {
      toast.error('Le nom du workspace est requis');
      return;
    }
    setSaving(true);
    try {
      await updateWorkspace(currentWorkspace.workspace_id, {
        name: editName.trim(),
        description: editDescription.trim(),
      });
      toast.success('Workspace mis à jour');
      setEditing(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Erreur lors de la mise à jour');
    } finally {
      setSaving(false);
    }
  };

  const handleEditKeyDown = (e) => {
    if (e.key === 'Escape') cancelEditing();
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSaveEdit();
    }
  };

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
      toast.success('Workspace créé avec succès');
      setShowCreateForm(false);
      setNewWorkspaceName('');
      setNewWorkspaceDescription('');
    } catch (error) {
      toast.error('Erreur lors de la création du workspace');
    } finally {
      setCreatingWorkspace(false);
    }
  };

  const workspaceSelectorAction = (
    <div className="relative">
      <button
        onClick={() => setWorkspaceDropdownOpen(!workspaceDropdownOpen)}
        className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
        data-testid="settings-workspace-switcher-btn"
      >
        <Building2 className="w-4 h-4 text-slate-600" />
        <span className="font-medium text-slate-800">{currentWorkspace?.name}</span>
        <ChevronDown className={`w-4 h-4 text-slate-500 transition-transform ${workspaceDropdownOpen ? 'rotate-180' : ''}`} />
      </button>
      
      {workspaceDropdownOpen && (
        <>
          <div 
            className="fixed inset-0 z-10" 
            onClick={() => setWorkspaceDropdownOpen(false)}
          />
          
          <div className="absolute right-0 top-full mt-2 w-80 bg-white rounded-lg shadow-lg border border-slate-200 z-20">
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
                onClick={() => {
                  setWorkspaceDropdownOpen(false);
                  setShowCreateForm(true);
                }}
                className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-left hover:bg-slate-50 text-slate-700 transition-colors"
                data-testid="settings-create-workspace-btn"
              >
                <Plus className="w-4 h-4 text-slate-500" />
                <span className="font-medium">Créer un nouveau workspace</span>
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );

  return (
    <SettingsPageLayout
      title="Workspace"
      description="Configuration et gestion de vos workspaces"
      action={workspaceSelectorAction}
    >

        {/* Current Workspace Info */}
        <div className="bg-white p-4 md:p-6 rounded-lg border border-slate-200 mb-6">
          <div className="flex items-start gap-3 md:gap-4">
            <div className="p-3 bg-slate-100 rounded-lg">
              <Building2 className="w-6 h-6 text-slate-700" />
            </div>
            <div className="flex-1">
              {editing ? (
                <div className="space-y-3" data-testid="workspace-edit-form">
                  <Input
                    ref={nameInputRef}
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    onKeyDown={handleEditKeyDown}
                    placeholder="Nom du workspace"
                    className="text-lg font-semibold"
                    data-testid="workspace-edit-name"
                  />
                  <textarea
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    onKeyDown={handleEditKeyDown}
                    placeholder="Description (optionnelle)"
                    rows={2}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
                    data-testid="workspace-edit-description"
                  />
                  <div className="flex items-center gap-2">
                    <Button size="sm" onClick={handleSaveEdit} disabled={saving} data-testid="workspace-edit-save">
                      {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Check className="w-3.5 h-3.5 mr-1.5" />}
                      Enregistrer
                    </Button>
                    <Button size="sm" variant="ghost" onClick={cancelEditing} disabled={saving} data-testid="workspace-edit-cancel">
                      <X className="w-3.5 h-3.5 mr-1.5" />
                      Annuler
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <h2 className="text-xl font-semibold text-slate-900 mb-1" data-testid="workspace-name">{currentWorkspace?.name}</h2>
                  {currentWorkspace?.description ? (
                    <p className="text-slate-600" data-testid="workspace-description">{currentWorkspace.description}</p>
                  ) : (
                    <button
                      onClick={startEditing}
                      className="text-sm text-slate-400 hover:text-slate-600 transition-colors"
                      data-testid="workspace-add-description"
                    >
                      Ajouter une description
                    </button>
                  )}
                </>
              )}
            </div>
            {!editing && (
              <button
                onClick={startEditing}
                className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
                title="Modifier"
                data-testid="workspace-edit-btn"
              >
                <Pencil className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* All Workspaces List */}
        <div className="bg-white rounded-lg border border-slate-200">
          <div className="p-4 border-b border-slate-100 flex items-center justify-between">
            <h3 className="font-semibold text-slate-900">Tous vos workspaces ({workspaces.length})</h3>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowCreateForm(true)}
              data-testid="create-workspace-btn"
            >
              <Plus className="w-4 h-4 mr-2" />
              Créer un workspace
            </Button>
          </div>
          
          <div className="divide-y divide-slate-100">
            {workspaces.map((workspace) => (
              <div 
                key={workspace.workspace_id}
                className={`p-4 flex items-center justify-between hover:bg-slate-50 transition-colors ${
                  workspace.workspace_id === currentWorkspace?.workspace_id ? 'bg-slate-50' : ''
                }`}
              >
                <div className="flex items-center gap-3">
                  <Building2 className="w-5 h-5 text-slate-500" />
                  <div>
                    <p className="font-medium text-slate-900">{workspace.name}</p>
                    <p className="text-sm text-slate-500">{workspace.description || 'Pas de description'}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {workspace.workspace_id === currentWorkspace?.workspace_id ? (
                    <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full font-medium">
                      Actif
                    </span>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => selectWorkspace(workspace)}
                    >
                      Sélectionner
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Create Workspace Modal */}
        {showCreateForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowCreateForm(false)}>
            <div 
              className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6"
              onClick={e => e.stopPropagation()}
            >
              <h3 className="text-xl font-semibold text-slate-900 mb-4">Créer un nouveau workspace</h3>
              
              <div className="space-y-4">
                <div>
                  <Label htmlFor="workspace-name">Nom du workspace *</Label>
                  <Input
                    id="workspace-name"
                    value={newWorkspaceName}
                    onChange={(e) => setNewWorkspaceName(e.target.value)}
                    placeholder="Ex: Cabinet Médical, Consulting..."
                    className="mt-1"
                    data-testid="new-workspace-name-input"
                  />
                </div>
                
                <div>
                  <Label htmlFor="workspace-description">Description (optionnel)</Label>
                  <Input
                    id="workspace-description"
                    value={newWorkspaceDescription}
                    onChange={(e) => setNewWorkspaceDescription(e.target.value)}
                    placeholder="Description de votre workspace"
                    className="mt-1"
                    data-testid="new-workspace-description-input"
                  />
                </div>
              </div>
              
              <div className="flex gap-3 mt-6">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowCreateForm(false);
                    setNewWorkspaceName('');
                    setNewWorkspaceDescription('');
                  }}
                  className="flex-1"
                >
                  Annuler
                </Button>
                <Button
                  onClick={handleCreateWorkspace}
                  disabled={creatingWorkspace || !newWorkspaceName.trim()}
                  className="flex-1"
                  data-testid="confirm-create-workspace-btn"
                >
                  {creatingWorkspace ? 'Création...' : 'Créer le workspace'}
                </Button>
              </div>
            </div>
          </div>
        )}
    </SettingsPageLayout>
  );
}
