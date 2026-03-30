import React from 'react';
import { Link } from 'react-router-dom';
import { Scale, Heart, Users, ArrowDownCircle, AlertTriangle } from 'lucide-react';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';

const SECTIONS = [
  { to: '/admin/arbitration', icon: Scale, title: 'Litiges & Arbitrage', desc: 'Litiges en cours, escalades et arbitrages', testId: 'admin-arbitration-link' },
  { to: '/admin/associations', icon: Heart, title: 'Associations', desc: 'Gestion des associations caritatives', testId: 'admin-associations-link' },
  { to: '/admin/payouts', icon: ArrowDownCircle, title: 'Reversements', desc: 'Virements manuels vers les associations', testId: 'admin-payouts-link' },
  { to: '/admin/stale-payouts', icon: AlertTriangle, title: 'Payouts bloqués', desc: 'Payouts en processing depuis plus de 24h', testId: 'admin-stale-payouts-link' },
  { to: '/admin/users', icon: Users, title: 'Utilisateurs & Droits', desc: 'Gestion des roles et permissions', testId: 'admin-users-link' },
];

export default function AdminDashboard() {
  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Administration' },
      ]} />

      <div className="max-w-4xl mx-auto px-6 pb-16">
        <h1 className="text-2xl font-bold text-slate-900 mb-1" data-testid="admin-page-title">Administration</h1>
        <p className="text-sm text-slate-500 mb-8">Gestion de la plateforme NLYT</p>

        <div className="grid md:grid-cols-3 gap-4">
          {SECTIONS.map(({ to, icon: Icon, title, desc, testId }) => (
            <Link
              key={to}
              to={to}
              className="p-5 bg-white rounded-xl border border-slate-200 hover:border-slate-400 transition-colors group"
              data-testid={testId}
            >
              <Icon className="w-6 h-6 text-slate-400 group-hover:text-slate-700 mb-3 transition-colors" />
              <h3 className="font-semibold text-slate-900 mb-1">{title}</h3>
              <p className="text-sm text-slate-500">{desc}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
