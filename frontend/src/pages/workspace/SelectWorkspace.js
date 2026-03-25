import React, { useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useWorkspace } from '../../contexts/WorkspaceContext';
import { Button } from '../../components/ui/button';
import { Plus, Building2 } from 'lucide-react';

export default function SelectWorkspace() {
  const navigate = useNavigate();
  const { workspaces, loading, selectWorkspace } = useWorkspace();

  useEffect(() => {
    if (!loading && workspaces.length === 0) {
      navigate('/workspace/create');
    }
  }, [loading, workspaces, navigate]);

  const handleSelectWorkspace = (workspace) => {
    selectWorkspace(workspace);
    navigate('/dashboard');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background py-12 px-4">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-end mb-4">
          <div>
            <span className="block text-lg font-bold tracking-[0.35em] text-slate-900 text-right">N<span className="text-slate-400">·</span>L<span className="text-slate-400">·</span>Y<span className="text-slate-400">·</span>T</span>
            <span className="block text-[10px] font-medium tracking-[0.25em] text-slate-400 uppercase text-right">Never Lose Your Time</span>
          </div>
        </div>
        <div className="text-center mb-12">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Sélectionnez un workspace</h1>
          <p className="text-slate-600">Choisissez le workspace dans lequel vous souhaitez travailler</p>
        </div>

        <div className="grid md:grid-cols-2 gap-6 mb-8">
          {workspaces.map((workspace) => (
            <div
              key={workspace.workspace_id}
              className="bg-white p-6 rounded-lg border border-slate-200 hover:border-slate-300 cursor-pointer transition-colors"
              onClick={() => handleSelectWorkspace(workspace)}
              data-testid={`workspace-card-${workspace.workspace_id}`}
            >
              <div className="flex items-start gap-4">
                <div className="p-3 bg-slate-100 rounded-lg">
                  <Building2 className="w-6 h-6 text-slate-700" />
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-slate-900 mb-1">{workspace.name}</h3>
                  <p className="text-sm text-slate-600">{workspace.description || 'Aucune description'}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="text-center">
          <Link to="/workspace/create">
            <Button variant="outline" data-testid="create-workspace-btn">
              <Plus className="w-4 h-4 mr-2" />
              Créer un nouveau workspace
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}