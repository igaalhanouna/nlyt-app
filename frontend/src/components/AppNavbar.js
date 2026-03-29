import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { Settings, LogOut, Menu, X, AlertTriangle, TrendingUp, ClipboardCheck, CalendarDays } from 'lucide-react';
import { attendanceAPI, notificationAPI } from '../services/api';
import api from '../services/api';

export default function AppNavbar() {
  const { logout, user } = useAuth();
  const { pathname } = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [pendingReviewCount, setPendingReviewCount] = useState(0);
  const [activeDisputeCount, setActiveDisputeCount] = useState(0);
  const [unreadDecisions, setUnreadDecisions] = useState(0);
  const [unreadDisputes, setUnreadDisputes] = useState(0);

  // Close drawer on route change
  useEffect(() => { setMobileOpen(false); }, [pathname]);

  // Lock body scroll when drawer is open
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [mobileOpen]);

  // Fetch pending declarative sheets count
  useEffect(() => {
    const fetchCount = async () => {
      try {
        const res = await attendanceAPI.pendingSheets();
        setPendingReviewCount(res.data.count || 0);
      } catch {
        // Silently ignore — non-critical
      }
    };
    fetchCount();
    const interval = setInterval(fetchCount, 60000);
    return () => clearInterval(interval);
  }, []);

  // Fetch active disputes count
  useEffect(() => {
    const fetchDisputes = async () => {
      try {
        const res = await api.get('/api/disputes/mine');
        const disputes = res.data.disputes || [];
        const active = disputes.filter(d => d.display_state !== 'resolved').length;
        setActiveDisputeCount(active);
      } catch {
        // Silently ignore
      }
    };
    fetchDisputes();
    const interval = setInterval(fetchDisputes, 60000);
    return () => clearInterval(interval);
  }, []);

  // Fetch unread notification counts (decisions + disputes)
  useEffect(() => {
    const fetchNotifCounts = async () => {
      try {
        const res = await notificationAPI.getCounts();
        setUnreadDecisions(res.data.decisions || 0);
        setUnreadDisputes(res.data.disputes || 0);
      } catch {
        // Silently ignore
      }
    };
    fetchNotifCounts();
    const interval = setInterval(fetchNotifCounts, 30000);
    return () => clearInterval(interval);
  }, []);

  const isActive = (path) => {
    if (path === '/dashboard') return pathname === '/dashboard' || pathname === '/dashboard/participant';
    if (path === '/settings') return pathname.startsWith('/settings');
    if (path === '/presences') return pathname === '/presences';
    if (path === '/litiges') return pathname.startsWith('/litiges');
    if (path === '/decisions') return pathname.startsWith('/decisions');
    if (path === '/mes-resultats') return pathname === '/mes-resultats';
    if (path === '/admin/arbitration') return pathname.startsWith('/admin/arbitration');
    return false;
  };

  const isAdmin = user?.role === 'admin';

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
            <Link to="/agenda" className={linkClass('/agenda')} data-testid="navbar-agenda-link">
              Agenda
            </Link>
            <Link to="/dashboard" className={linkClass('/dashboard')} data-testid="navbar-dashboard-link">
              Tableau de bord
            </Link>
            <Link to="/presences" className={`${linkClass('/presences')} relative flex items-center gap-1.5`} data-testid="navbar-presences-link">
              Presences
              {pendingReviewCount > 0 && (
                <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-amber-500 text-white text-[10px] font-bold leading-none" data-testid="navbar-presences-badge">
                  {pendingReviewCount}
                </span>
              )}
            </Link>
            <Link to="/litiges" className={`${linkClass('/litiges')} relative flex items-center gap-1.5`} data-testid="navbar-litiges-link">
              Litiges
              {(activeDisputeCount > 0 || unreadDisputes > 0) && (
                <span className={`inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-white text-[10px] font-bold leading-none ${unreadDisputes > 0 ? 'bg-red-500' : 'bg-amber-500'}`} data-testid="navbar-litiges-badge">
                  {unreadDisputes > 0 ? unreadDisputes : activeDisputeCount}
                </span>
              )}
            </Link>
            <Link to="/decisions" className={`${linkClass('/decisions')} relative flex items-center gap-1.5`} data-testid="navbar-decisions-link">
              Decisions
              {unreadDecisions > 0 && (
                <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold leading-none" data-testid="navbar-decisions-badge">
                  {unreadDecisions}
                </span>
              )}
            </Link>
            {isAdmin && (
              <Link to="/admin/arbitration" className={linkClass('/admin/arbitration')} data-testid="navbar-admin-link">
                Arbitrage
              </Link>
            )}
            <Link to="/mes-resultats" className={linkClass('/mes-resultats')} data-testid="navbar-results-link">
              Contributions
            </Link>
            <Link to="/settings" className={linkClass('/settings')} data-testid="navbar-settings-link">
              <span className="flex items-center gap-1.5">
                <Settings className="w-3.5 h-3.5" />
                Parametres
              </span>
            </Link>
          </div>

          {/* Desktop logout */}
          <div className="hidden md:flex items-center">
            <Button variant="ghost" size="sm" onClick={logout} className="text-slate-400 hover:text-slate-700" data-testid="navbar-logout-btn">
              <LogOut className="w-4 h-4 mr-2" />
              Deconnexion
            </Button>
          </div>

          {/* Mobile hamburger */}
          <button
            onClick={() => setMobileOpen(true)}
            className="md:hidden flex items-center justify-center w-11 h-11 rounded-lg text-slate-600 hover:bg-slate-100 active:bg-slate-200 transition-colors relative"
            data-testid="navbar-mobile-menu-btn"
            aria-label="Menu"
          >
            <Menu className="w-5 h-5" />
            {(pendingReviewCount > 0 || activeDisputeCount > 0 || unreadDecisions > 0 || unreadDisputes > 0) && (
              <span className={`absolute top-1 right-1 w-2.5 h-2.5 rounded-full ${unreadDecisions > 0 || unreadDisputes > 0 ? 'bg-red-500' : 'bg-amber-500'}`} />
            )}
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
              <Link to="/agenda" className={mobileLinkClass('/agenda')} data-testid="mobile-nav-agenda">
                <CalendarDays className="w-4.5 h-4.5" />
                Agenda
              </Link>
              <Link to="/dashboard" className={mobileLinkClass('/dashboard')} data-testid="mobile-nav-dashboard">
                Tableau de bord
              </Link>
              <Link to="/presences" className={mobileLinkClass('/presences')} data-testid="mobile-nav-presences">
                <ClipboardCheck className="w-4.5 h-4.5" />
                Presences
                {pendingReviewCount > 0 && (
                  <span className="ml-auto inline-flex items-center justify-center min-w-[22px] h-[22px] px-1.5 rounded-full bg-amber-500 text-white text-xs font-bold">
                    {pendingReviewCount}
                  </span>
                )}
              </Link>
              <Link to="/litiges" className={mobileLinkClass('/litiges')} data-testid="mobile-nav-litiges">
                Litiges
                {(activeDisputeCount > 0 || unreadDisputes > 0) && (
                  <span className={`ml-auto inline-flex items-center justify-center min-w-[22px] h-[22px] px-1.5 rounded-full text-white text-xs font-bold ${unreadDisputes > 0 ? 'bg-red-500' : 'bg-amber-500'}`}>
                    {unreadDisputes > 0 ? unreadDisputes : activeDisputeCount}
                  </span>
                )}
              </Link>
              <Link to="/decisions" className={mobileLinkClass('/decisions')} data-testid="mobile-nav-decisions">
                Decisions
                {unreadDecisions > 0 && (
                  <span className="ml-auto inline-flex items-center justify-center min-w-[22px] h-[22px] px-1.5 rounded-full bg-red-500 text-white text-xs font-bold">
                    {unreadDecisions}
                  </span>
                )}
              </Link>
              {isAdmin && (
                <Link to="/admin/arbitration" className={mobileLinkClass('/admin/arbitration')} data-testid="mobile-nav-admin">
                  Arbitrage
                </Link>
              )}
              <Link to="/mes-resultats" className={mobileLinkClass('/mes-resultats')} data-testid="mobile-nav-results">
                <TrendingUp className="w-4.5 h-4.5" />
                Contributions
              </Link>
              <Link to="/settings" className={mobileLinkClass('/settings')} data-testid="mobile-nav-settings">
                <Settings className="w-4.5 h-4.5" />
                Parametres
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
                Deconnexion
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
