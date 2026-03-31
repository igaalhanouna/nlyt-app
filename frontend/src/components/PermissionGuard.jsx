import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { hasPermission } from '../utils/permissions';
import { toast } from 'sonner';

/**
 * Route guard that checks if the current user has the required permission.
 * Redirects to /dashboard with a toast if access is denied.
 *
 * Usage:
 *   <PermissionGuard permission="admin:arbitration">
 *     <AdminArbitrationList />
 *   </PermissionGuard>
 */
export default function PermissionGuard({ permission, children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/signin" replace />;
  }

  const role = user.role || 'user';
  if (!hasPermission(role, permission)) {
    toast.error('Acces non autorise');
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}
