import React, { useState, useEffect, useCallback } from 'react';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';
import { Input } from '../../components/ui/input';
import { Search, Mail, ChevronDown, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { safeFetchJson } from '../../utils/safeFetchJson';
import { useAuth } from '../../contexts/AuthContext';
import { ALL_ROLES, ROLE_LABELS, ROLE_COLORS } from '../../utils/permissions';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const PROVIDER_LABELS = { email: 'Email', google: 'Google', microsoft: 'Microsoft' };

export default function AdminUsers() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [changingRole, setChangingRole] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [pendingRoleChange, setPendingRoleChange] = useState(null); // { userId, email, newRole }

  const token = localStorage.getItem('nlyt_token');
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };

  const fetchUsers = useCallback(async () => {
    try {
      const { ok, data } = await safeFetchJson(`${API_URL}/api/admin/users`, { headers });
      if (!ok) throw new Error('Erreur chargement');
      setUsers(data.users || []);
    } catch {
      toast.error('Impossible de charger les utilisateurs');
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleRoleChange = async (u, newRole) => {
    if (newRole === (u.role || 'user')) return;
    if (!pendingRoleChange || pendingRoleChange.userId !== u.user_id || pendingRoleChange.newRole !== newRole) {
      setPendingRoleChange({ userId: u.user_id, email: u.email, newRole });
      return;
    }
    setPendingRoleChange(null);
    setChangingRole(u.user_id);
    try {
      const { ok, data } = await safeFetchJson(`${API_URL}/api/admin/users/${u.user_id}/role`, {
        method: 'PATCH', headers, body: JSON.stringify({ role: newRole }),
      });
      if (!ok) throw new Error(data.detail || 'Erreur');
      toast.success(`${u.email} est maintenant ${label}`);
      fetchUsers();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setChangingRole(null);
    }
  };

  const handleDeleteUser = async (u) => {
    if (confirmDeleteId !== u.user_id) {
      setConfirmDeleteId(u.user_id);
      return;
    }
    setConfirmDeleteId(null);
    setDeleting(u.user_id);
    try {
      const { ok, data } = await safeFetchJson(`${API_URL}/api/admin/users/${u.user_id}`, {
        method: 'DELETE', headers,
      });
      if (!ok) throw new Error(data.detail || 'Erreur');
      toast.success(`${u.email} supprimé`);
      fetchUsers();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setDeleting(null);
    }
  };

  const filtered = users.filter((u) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (u.email || '').toLowerCase().includes(q)
      || (u.first_name || '').toLowerCase().includes(q)
      || (u.last_name || '').toLowerCase().includes(q)
      || (ROLE_LABELS[u.role] || '').toLowerCase().includes(q);
  });

  const roleCounts = {};
  ALL_ROLES.forEach(r => { roleCounts[r] = 0; });
  users.forEach(u => { roleCounts[u.role || 'user'] = (roleCounts[u.role || 'user'] || 0) + 1; });

  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Administration', href: '/admin' },
        { label: 'Utilisateurs' },
      ]} />
      <div className="max-w-5xl mx-auto px-6 pb-12">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900" data-testid="admin-users-title">Utilisateurs & Droits</h1>
            <div className="flex flex-wrap gap-2 mt-2">
              {ALL_ROLES.map(r => (
                <span key={r} className={`text-xs px-2 py-0.5 rounded border ${ROLE_COLORS[r]}`}>
                  {ROLE_LABELS[r]} : {roleCounts[r] || 0}
                </span>
              ))}
            </div>
          </div>
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input
              placeholder="Rechercher par nom, email ou role..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10"
              data-testid="users-search-input"
            />
          </div>
        </div>

        {loading ? (
          <div className="text-center py-12 text-slate-500">Chargement...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 text-slate-500">{search ? 'Aucun resultat' : 'Aucun utilisateur'}</div>
        ) : (
          <div className="space-y-2" data-testid="users-list">
            {filtered.map((u) => {
              const isSelf = currentUser?.user_id === u.user_id;
              const role = u.role || 'user';
              const colorClass = ROLE_COLORS[role] || ROLE_COLORS.user;

              return (
                <div
                  key={u.user_id}
                  className={`bg-white rounded-lg border p-4 flex items-center justify-between gap-4 ${role !== 'user' ? 'border-l-4' : ''} ${role === 'admin' ? 'border-l-amber-400' : role === 'arbitrator' ? 'border-l-purple-400' : role === 'payer' ? 'border-l-blue-400' : role === 'accreditor' ? 'border-l-emerald-400' : ''}`}
                  data-testid={`user-row-${u.user_id}`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-slate-900">
                        {u.first_name || ''} {u.last_name || ''}
                      </span>
                      <span className={`inline-flex items-center text-xs font-semibold px-2 py-0.5 rounded border ${colorClass}`}>
                        {ROLE_LABELS[role]}
                      </span>
                      {isSelf && (
                        <span className="text-xs text-slate-400">(vous)</span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-sm text-slate-500">
                      <span className="inline-flex items-center gap-1"><Mail className="w-3 h-3" /> {u.email}</span>
                      <span className="text-slate-300">|</span>
                      <span>{(u.providers || []).map((p) => PROVIDER_LABELS[p] || p).join(', ')}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {isSelf ? (
                      <span className="text-xs text-slate-400 italic">Votre compte</span>
                    ) : (
                      <>
                        <div className="relative">
                          <select
                            value={role}
                            onChange={(e) => handleRoleChange(u, e.target.value)}
                            disabled={changingRole === u.user_id}
                            className="appearance-none bg-white border border-slate-200 rounded-md pl-3 pr-8 py-1.5 text-sm font-medium text-slate-700 cursor-pointer hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-1 disabled:opacity-50"
                            data-testid={`role-select-${u.user_id}`}
                          >
                            {ALL_ROLES.map(r => (
                              <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                            ))}
                          </select>
                          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
                        </div>
                        {pendingRoleChange && pendingRoleChange.userId === u.user_id && (
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs text-amber-600 font-medium">{ROLE_LABELS[pendingRoleChange.newRole]} ?</span>
                            <button onClick={() => handleRoleChange(u, pendingRoleChange.newRole)} className="px-2 py-1 text-xs font-bold text-white bg-amber-600 rounded hover:bg-amber-700 transition-colors" data-testid={`confirm-role-${u.user_id}`}>Oui</button>
                            <button onClick={() => setPendingRoleChange(null)} className="px-2 py-1 text-xs font-medium text-slate-600 bg-slate-100 rounded hover:bg-slate-200 transition-colors" data-testid={`cancel-role-${u.user_id}`}>Non</button>
                          </div>
                        )}
                        {confirmDeleteId === u.user_id ? (
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs text-red-600 font-medium">Supprimer ?</span>
                            <button
                              onClick={() => handleDeleteUser(u)}
                              disabled={deleting === u.user_id}
                              className="px-2 py-1 text-xs font-bold text-white bg-red-600 rounded hover:bg-red-700 transition-colors disabled:opacity-50"
                              data-testid={`confirm-delete-${u.user_id}`}
                            >
                              Oui
                            </button>
                            <button
                              onClick={() => setConfirmDeleteId(null)}
                              className="px-2 py-1 text-xs font-medium text-slate-600 bg-slate-100 rounded hover:bg-slate-200 transition-colors"
                              data-testid={`cancel-delete-${u.user_id}`}
                            >
                              Non
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => handleDeleteUser(u)}
                            disabled={deleting === u.user_id}
                            className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors disabled:opacity-50"
                            title="Supprimer cet utilisateur"
                            data-testid={`delete-user-${u.user_id}`}
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
