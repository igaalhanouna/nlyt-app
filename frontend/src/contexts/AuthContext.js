import React, { createContext, useContext, useState, useEffect } from 'react';
import { authAPI } from '../services/api';
import { hasPermission, hasAnyAdminPermission } from '../utils/permissions';

const AuthContext = createContext();

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // CRITICAL: If returning from OAuth callback, skip loading from localStorage.
    // AuthCallback will exchange the session_id / code and establish the session.
    if (window.location.hash?.includes('session_id=')) {
      setLoading(false);
      return;
    }

    const token = localStorage.getItem('nlyt_token');
    const storedUser = localStorage.getItem('nlyt_user');
    
    if (token && storedUser) {
      setUser(JSON.parse(storedUser));
    }
    setLoading(false);
  }, []);

  const login = async (email, password) => {
    const response = await authAPI.login({ email, password });
    const { access_token, user: userData } = response.data;
    
    localStorage.setItem('nlyt_token', access_token);
    localStorage.setItem('nlyt_user', JSON.stringify(userData));
    setUser(userData);
    
    return userData;
  };

  const register = async (userData) => {
    const response = await authAPI.register(userData);
    
    // Check if the response indicates an unverified existing account
    if (response.data && response.data.error === 'not_verified') {
      return response.data;
    }
    
    return response.data;
  };

  const loginWithToken = (accessToken, userData) => {
    localStorage.setItem('nlyt_token', accessToken);
    localStorage.setItem('nlyt_user', JSON.stringify(userData));
    setUser(userData);
  };

  const logout = () => {
    localStorage.removeItem('nlyt_token');
    localStorage.removeItem('nlyt_user');
    setUser(null);
  };

  // Get token from localStorage
  const token = localStorage.getItem('nlyt_token');

  const canAccess = (permission) => {
    if (!user) return false;
    return hasPermission(user.role || 'user', permission);
  };

  const isAnyAdmin = user ? hasAnyAdminPermission(user.role || 'user') : false;

  const value = {
    user,
    token,
    loading,
    login,
    loginWithToken,
    register,
    logout,
    canAccess,
    isAnyAdmin,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}