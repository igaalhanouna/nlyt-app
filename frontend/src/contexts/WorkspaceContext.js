import React, { createContext, useContext, useState, useEffect } from 'react';
import { workspaceAPI, userSettingsAPI } from '../services/api';
import { useAuth } from './AuthContext';

const WorkspaceContext = createContext();

export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error('useWorkspace must be used within WorkspaceProvider');
  }
  return context;
}

export function WorkspaceProvider({ children }) {
  const { user } = useAuth();
  const [currentWorkspace, setCurrentWorkspace] = useState(null);
  const [workspaces, setWorkspaces] = useState([]);
  const [defaultWorkspaceId, setDefaultWorkspaceId] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user) {
      loadWorkspaces();
    } else {
      setWorkspaces([]);
      setCurrentWorkspace(null);
      setDefaultWorkspaceId(null);
      setLoading(false);
    }
  }, [user]);

  const loadWorkspaces = async () => {
    try {
      const [wsResponse, settingsResponse] = await Promise.all([
        workspaceAPI.list(),
        userSettingsAPI.get().catch(() => ({ data: {} })),
      ]);
      const workspaceList = wsResponse.data.workspaces || [];
      setWorkspaces(workspaceList);

      const serverDefault = settingsResponse.data?.default_workspace_id || null;
      setDefaultWorkspaceId(serverDefault);

      // Priority: server default > localStorage > first workspace
      const savedWorkspaceId = localStorage.getItem('nlyt_current_workspace');
      const priorityId = serverDefault || savedWorkspaceId;

      if (priorityId) {
        const workspace = workspaceList.find(w => w.workspace_id === priorityId);
        if (workspace) {
          setCurrentWorkspace(workspace);
          localStorage.setItem('nlyt_current_workspace', workspace.workspace_id);
        } else if (workspaceList.length > 0) {
          setCurrentWorkspace(workspaceList[0]);
          localStorage.setItem('nlyt_current_workspace', workspaceList[0].workspace_id);
        }
      } else if (workspaceList.length > 0) {
        setCurrentWorkspace(workspaceList[0]);
        localStorage.setItem('nlyt_current_workspace', workspaceList[0].workspace_id);
      }

      // Auto-set default if single workspace and no default set
      if (workspaceList.length === 1 && !serverDefault) {
        userSettingsAPI.setDefaultWorkspace(workspaceList[0].workspace_id)
          .then(() => setDefaultWorkspaceId(workspaceList[0].workspace_id))
          .catch(() => {});
      }
    } catch (error) {
      console.error('Error loading workspaces:', error);
    } finally {
      setLoading(false);
    }
  };

  const selectWorkspace = (workspace) => {
    setCurrentWorkspace(workspace);
    localStorage.setItem('nlyt_current_workspace', workspace.workspace_id);
  };

  const setDefaultWorkspace = async (workspaceId) => {
    await userSettingsAPI.setDefaultWorkspace(workspaceId);
    setDefaultWorkspaceId(workspaceId);
  };

  const createWorkspace = async (name, description) => {
    const response = await workspaceAPI.create({ name, description });
    const newWorkspace = response.data;
    setWorkspaces([...workspaces, newWorkspace]);
    setCurrentWorkspace(newWorkspace);
    localStorage.setItem('nlyt_current_workspace', newWorkspace.workspace_id);
    return newWorkspace;
  };

  const updateWorkspace = async (workspaceId, data) => {
    const response = await workspaceAPI.update(workspaceId, data);
    const updated = response.data;
    setWorkspaces(prev => prev.map(w => w.workspace_id === workspaceId ? updated : w));
    if (currentWorkspace?.workspace_id === workspaceId) {
      setCurrentWorkspace(updated);
    }
    return updated;
  };

  const value = {
    currentWorkspace,
    workspaces,
    defaultWorkspaceId,
    loading,
    selectWorkspace,
    setDefaultWorkspace,
    createWorkspace,
    updateWorkspace,
    refreshWorkspaces: loadWorkspaces,
  };

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}