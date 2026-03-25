import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { Settings, LogOut, Menu, X } from 'lucide-react';

export default function AppNavbar() {
  const { logout } = useAuth();
  const { pathname } = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close drawer on route change
  useEffect(() => { setMobileOpen(false); }, [pathname]);

  // Lock body scroll when drawer is open
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [mobileOpen]);

  const isActive = (path) => {
    if (path === '/dashboard') return pathname === '/dashboard' || pathname === '/dashboard/participant';
    if (path === '/settings') return pathname.startsWith('/settings');
    return false;
  };

  const linkClass = (path) =>
    `text-sm font-medium transition-colors ${
      isActive(path) ? 'text-slate-900' : 'text-slate-400 hover:text-slate-700'
    }`;

  const mobileLinkClass = (path) =>
    `flex items-center gap-3 px-4 py-3.5 text-base font-medium rounded-lg transition-colors ${
      isActive(path)
        ? 'text-slate-900 bg-slate-100'
        : 'text-slate-600 hover:bg-slate-50 active:bg-slate-100'
    }`;

  return (
    <>
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-40" data-testid="app-navbar">
        <div className="max-w-7xl mx-auto px-4 md:px-6 h-14 flex items-center justify-between">
          {/* Logo */}
          <Link to="/dashboard" className="flex flex-col leading-none flex-shrink-0" data-testid="navbar-logo-link">
            <span className="text-lg font-bold tracking-[0.35em] text-slate-900">
              N<span className="text-slate-400">·</span>L<span className="text-slate-400">·</span>Y<span className="text-slate-400">·</span>T
            </span>
            <span className="text-[10px] font-medium tracking-[0.25em] text-slate-400 uppercase">
              Never Lose Your Time
            </span>
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-6">
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

          {/* Desktop logout */}
          <div className="hidden md:flex items-center">
            <Button variant="ghost" size="sm" onClick={logout} className="text-slate-400 hover:text-slate-700" data-testid="navbar-logout-btn">
              <LogOut className="w-4 h-4 mr-2" />
              Déconnexion
            </Button>
          </div>

          {/* Mobile hamburger */}
          <button
            onClick={() => setMobileOpen(true)}
            className="md:hidden flex items-center justify-center w-10 h-10 rounded-lg text-slate-600 hover:bg-slate-100 active:bg-slate-200 transition-colors"
            data-testid="navbar-mobile-menu-btn"
            aria-label="Menu"
          >
            <Menu className="w-5 h-5" />
          </button>
        </div>
      </nav>

      {/* Mobile drawer overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden" data-testid="navbar-mobile-drawer">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          {/* Drawer panel */}
          <div className="absolute top-0 right-0 w-72 max-w-[85vw] h-full bg-white shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
            {/* Drawer header */}
            <div className="flex items-center justify-between px-4 h-14 border-b border-slate-100">
              <span className="text-base font-bold tracking-[0.3em] text-slate-900">
                N<span className="text-slate-400">·</span>L<span className="text-slate-400">·</span>Y<span className="text-slate-400">·</span>T
              </span>
              <button
                onClick={() => setMobileOpen(false)}
                className="flex items-center justify-center w-10 h-10 rounded-lg text-slate-500 hover:bg-slate-100"
                aria-label="Fermer"
                data-testid="navbar-mobile-close-btn"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Nav links */}
            <div className="flex-1 p-3 space-y-1 overflow-y-auto">
              <Link to="/dashboard" className={mobileLinkClass('/dashboard')} data-testid="mobile-nav-dashboard">
                Tableau de bord
              </Link>
              <Link to="/settings" className={mobileLinkClass('/settings')} data-testid="mobile-nav-settings">
                <Settings className="w-4.5 h-4.5" />
                Paramètres
              </Link>
            </div>

            {/* Logout */}
            <div className="p-3 border-t border-slate-100">
              <button
                onClick={() => { setMobileOpen(false); logout(); }}
                className="flex items-center gap-3 w-full px-4 py-3.5 text-base font-medium text-red-600 rounded-lg hover:bg-red-50 active:bg-red-100 transition-colors"
                data-testid="mobile-nav-logout"
              >
                <LogOut className="w-4.5 h-4.5" />
                Déconnexion
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
