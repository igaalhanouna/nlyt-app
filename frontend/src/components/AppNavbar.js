import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { Settings, LogOut } from 'lucide-react';

export default function AppNavbar() {
  const { logout } = useAuth();
  const { pathname } = useLocation();

  const isActive = (path) => {
    if (path === '/dashboard') return pathname === '/dashboard' || pathname === '/dashboard/participant';
    if (path === '/settings') return pathname.startsWith('/settings');
    return false;
  };

  const linkClass = (path) =>
    `text-sm font-medium transition-colors ${
      isActive(path)
        ? 'text-slate-900'
        : 'text-slate-400 hover:text-slate-700'
    }`;

  return (
    <nav className="bg-white border-b border-slate-200 sticky top-0 z-40" data-testid="app-navbar">
      <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <Link to="/dashboard" className="flex flex-col leading-none" data-testid="navbar-logo-link">
            <span className="text-lg font-bold tracking-[0.35em] text-slate-900">
              N<span className="text-slate-400">·</span>L<span className="text-slate-400">·</span>Y<span className="text-slate-400">·</span>T
            </span>
            <span className="text-[10px] font-medium tracking-[0.25em] text-slate-400 uppercase">
              Never Lose Your Time
            </span>
          </Link>
          <div className="flex items-center gap-6">
            <Link to="/dashboard" className={linkClass('/dashboard')} data-testid="navbar-dashboard-link">
              Tableau de bord
            </Link>
            <Link to="/settings" className={linkClass('/settings')} data-testid="navbar-settings-link">
              <span className="flex items-center gap-1.5">
                <Settings className="w-3.5 h-3.5" />
                Paramètres
              </span>
            </Link>
          </div>
        </div>
        <div className="flex items-center">
          <Button variant="ghost" size="sm" onClick={logout} className="text-slate-400 hover:text-slate-700" data-testid="navbar-logout-btn">
            <LogOut className="w-4 h-4 mr-2" />
            Déconnexion
          </Button>
        </div>
      </div>
    </nav>
  );
}
