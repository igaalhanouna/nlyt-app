import React, { createContext, useContext, useState, useEffect } from 'react';
import { workspaceAPI } from '../services/api';
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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user) {
      loadWorkspaces();
    } else {
      setWorkspaces([]);
      setCurrentWorkspace(null);
      setLoading(false);
    }
  }, [user]);

  const loadWorkspaces = async () => {
    try {
      const response = await workspaceAPI.list();
      const workspaceList = response.data.workspaces || [];
      setWorkspaces(workspaceList);
      
      const savedWorkspaceId = localStorage.getItem('nlyt_current_workspace');
      if (savedWorkspaceId) {
        const workspace = workspaceList.find(w => w.workspace_id === savedWorkspaceId);
        if (workspace) {
          setCurrentWorkspace(workspace);
        } else if (workspaceList.length > 0) {
          setCurrentWorkspace(workspaceList[0]);
          localStorage.setItem('nlyt_current_workspace', workspaceList[0].workspace_id);
        }
      } else if (workspaceList.length > 0) {
        setCurrentWorkspace(workspaceList[0]);
        localStorage.setItem('nlyt_current_workspace', workspaceList[0].workspace_id);
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

  const createWorkspace = async (name, description) => {
    const response = await workspaceAPI.create({ name, description });
    const newWorkspace = response.data;
    setWorkspaces([...workspaces, newWorkspace]);
    setCurrentWorkspace(newWorkspace);
    localStorage.setItem('nlyt_current_workspace', newWorkspace.workspace_id);
    return newWorkspace;
  };

  const value = {
    currentWorkspace,
    workspaces,
    loading,
    selectWorkspace,
    createWorkspace,
    refreshWorkspaces: loadWorkspaces,
  };

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}