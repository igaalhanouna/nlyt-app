import React, { useState, useEffect, useCallback } from 'react';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';
import { Input } from '../../components/ui/input';
import { Button } from '../../components/ui/button';
import { Shield, ShieldCheck, Search, Mail } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const PROVIDER_LABELS = { email: 'Email', google: 'Google', microsoft: 'Microsoft' };

export default function AdminUsers() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const token = localStorage.getItem('nlyt_token');
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };

  const fetchUsers = useCallback(async () => {
    try {
      const resp = await fetch(`${API_URL}/api/admin/users`, { headers });
      if (!resp.ok) throw new Error('Erreur chargement');
      const data = await resp.json();
      setUsers(data.users || []);
    } catch (err) {
      toast.error('Impossible de charger les utilisateurs');
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleToggleRole = async (u) => {
    const newRole = u.role === 'admin' ? 'user' : 'admin';
    const action = newRole === 'admin' ? 'promouvoir en admin' : 'retirer les droits admin de';
    if (!window.confirm(`Voulez-vous ${action} ${u.email} ?`)) return;

    try {
      const resp = await fetch(`${API_URL}/api/admin/users/${u.user_id}/role`, {
        method: 'PATCH', headers, body: JSON.stringify({ role: newRole }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Erreur');
      toast.success(`${u.email} est maintenant ${newRole}`);
      fetchUsers();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const filtered = users.filter((u) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (u.email || '').toLowerCase().includes(q)
      || (u.first_name || '').toLowerCase().includes(q)
      || (u.last_name || '').toLowerCase().includes(q);
  });

  const adminCount = users.filter((u) => u.role === 'admin').length;

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
            <p className="text-sm text-slate-500 mt-1">{users.length} utilisateur{users.length !== 1 ? 's' : ''} dont {adminCount} admin{adminCount !== 1 ? 's' : ''}</p>
          </div>
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input
              placeholder="Rechercher par nom ou email..."
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
          <div className="text-center py-12 text-slate-500">{search ? 'Aucun résultat' : 'Aucun utilisateur'}</div>
        ) : (
          <div className="space-y-2" data-testid="users-list">
            {filtered.map((u) => {
              const isSelf = currentUser?.user_id === u.user_id;
              const isAdmin = u.role === 'admin';
              return (
                <div
                  key={u.user_id}
                  className={`bg-white rounded-lg border p-4 flex items-center justify-between gap-4 ${isAdmin ? 'border-amber-200' : 'border-slate-200'}`}
                  data-testid={`user-row-${u.user_id}`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-slate-900">
                        {u.first_name || ''} {u.last_name || ''}
                      </span>
                      {isAdmin && (
                        <span className="inline-flex items-center gap-1 text-xs font-semibold bg-amber-100 text-amber-700 px-2 py-0.5 rounded">
                          <ShieldCheck className="w-3 h-3" /> Admin
                        </span>
                      )}
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
                  <div className="flex-shrink-0">
                    {isSelf ? (
                      <span className="text-xs text-slate-400 italic">Votre compte</span>
                    ) : (
                      <Button
                        variant={isAdmin ? 'outline' : 'default'}
                        size="sm"
                        onClick={() => handleToggleRole(u)}
                        data-testid={`toggle-role-${u.user_id}`}
                      >
                        <Shield className="w-4 h-4 mr-1" />
                        {isAdmin ? 'Retirer admin' : 'Promouvoir admin'}
                      </Button>
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
