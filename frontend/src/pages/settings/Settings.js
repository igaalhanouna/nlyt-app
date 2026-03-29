import React from 'react';
import { Link } from 'react-router-dom';
import { User, Building2, Plug, CreditCard, BarChart3, Wallet, Heart } from 'lucide-react';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';

const SECTIONS = [
  { to: '/settings/profile', icon: User, title: 'Profil', desc: 'Informations personnelles et associations', testId: 'settings-profile-link' },
  { to: '/settings/workspace', icon: Building2, title: 'Workspace', desc: 'Configuration du workspace', testId: 'settings-workspace-link' },
  { to: '/settings/integrations', icon: Plug, title: 'Integrations', desc: 'Calendriers et visioconference', testId: 'settings-integrations-link' },
  { to: '/settings/payment', icon: CreditCard, title: 'Paiement', desc: 'Moyen de paiement pour vos garanties', testId: 'settings-payment-link' },
  { to: '/wallet', icon: Wallet, title: 'Wallet', desc: 'Solde et historique des transactions', testId: 'settings-wallet-link' },
  { to: '/settings/statistics', icon: BarChart3, title: 'Statistiques', desc: 'Analyse de vos engagements et performances', testId: 'settings-statistics-link' },
  { to: '/admin/associations', icon: Heart, title: 'Associations', desc: 'Gestion des associations caritatives', testId: 'settings-associations-link' },
];

export default function Settings() {
  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Paramètres' },
      ]} />

      <div className="max-w-4xl mx-auto px-6 pb-16">
        <h1 className="text-2xl font-bold text-slate-900 mb-1" data-testid="settings-page-title">Paramètres</h1>
        <p className="text-sm text-slate-500 mb-8">Gérez votre compte, vos intégrations et vos finances</p>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
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
