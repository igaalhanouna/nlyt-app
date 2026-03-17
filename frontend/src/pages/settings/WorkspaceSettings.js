import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { ArrowLeft, Building2, ChevronDown, Check, Plus, Settings, Trash2 } from 'lucide-react';
import { useWorkspace } from '../../contexts/WorkspaceContext';
import { toast } from 'sonner';

export default function WorkspaceSettings() {
  const navigate = useNavigate();
  const { currentWorkspace, workspaces, selectWorkspace, createWorkspace } = useWorkspace();
  const [workspaceDropdownOpen, setWorkspaceDropdownOpen] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState('');
  const [newWorkspaceDescription, setNewWorkspaceDescription] = useState('');
  const [creatingWorkspace, setCreatingWorkspace] = useState(false);

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

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-4xl mx-auto">
        <Link to="/settings">
          <Button variant="ghost" className="mb-6">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Retour
          </Button>
        </Link>
        
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold">Paramètres du workspace</h1>
          
          {/* Workspace Selector */}
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
            
            {/* Dropdown */}
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
        </div>

        {/* Current Workspace Info */}
        <div className="bg-white p-6 rounded-lg border border-slate-200 mb-6">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-slate-100 rounded-lg">
              <Building2 className="w-6 h-6 text-slate-700" />
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-semibold text-slate-900 mb-1">{currentWorkspace?.name}</h2>
              <p className="text-slate-600">{currentWorkspace?.description || 'Aucune description'}</p>
            </div>
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
                    <p className="text-sm text-slate-500">{workspace.description || 'Aucune description'}</p>
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
      </div>
    </div>
  );
}
