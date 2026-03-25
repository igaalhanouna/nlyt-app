import React from 'react';
import { Link } from 'react-router-dom';
import { User, Building2, Plug, CreditCard, Wallet } from 'lucide-react';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';

export default function Settings() {
  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Paramètres' },
      ]} />

      <div className="max-w-4xl mx-auto px-6 pb-12">
        <h1 className="text-2xl font-bold text-slate-900 mb-6">Paramètres</h1>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          <Link to="/settings/profile" className="p-5 bg-white rounded-lg border border-slate-200 hover:border-slate-400 transition-colors group" data-testid="settings-profile-link">
            <User className="w-6 h-6 text-slate-400 group-hover:text-slate-700 mb-3 transition-colors" />
            <h3 className="font-semibold text-slate-900 mb-1">Profil</h3>
            <p className="text-sm text-slate-500">Informations personnelles et associations</p>
          </Link>
          <Link to="/settings/workspace" className="p-5 bg-white rounded-lg border border-slate-200 hover:border-slate-400 transition-colors group" data-testid="settings-workspace-link">
            <Building2 className="w-6 h-6 text-slate-400 group-hover:text-slate-700 mb-3 transition-colors" />
            <h3 className="font-semibold text-slate-900 mb-1">Workspace</h3>
            <p className="text-sm text-slate-500">Configuration du workspace</p>
          </Link>
          <Link to="/settings/integrations" className="p-5 bg-white rounded-lg border border-slate-200 hover:border-slate-400 transition-colors group" data-testid="settings-integrations-link">
            <Plug className="w-6 h-6 text-slate-400 group-hover:text-slate-700 mb-3 transition-colors" />
            <h3 className="font-semibold text-slate-900 mb-1">Integrations</h3>
            <p className="text-sm text-slate-500">Calendriers et visioconference</p>
          </Link>
          <Link to="/settings/payment" className="p-5 bg-white rounded-lg border border-slate-200 hover:border-slate-400 transition-colors group" data-testid="settings-payment-link">
            <CreditCard className="w-6 h-6 text-slate-400 group-hover:text-slate-700 mb-3 transition-colors" />
            <h3 className="font-semibold text-slate-900 mb-1">Paiement</h3>
            <p className="text-sm text-slate-500">Moyen de paiement pour vos garanties</p>
          </Link>
          <Link to="/settings/wallet" className="p-5 bg-white rounded-lg border border-slate-200 hover:border-slate-400 transition-colors group" data-testid="settings-wallet-link">
            <Wallet className="w-6 h-6 text-slate-400 group-hover:text-slate-700 mb-3 transition-colors" />
            <h3 className="font-semibold text-slate-900 mb-1">Wallet</h3>
            <p className="text-sm text-slate-500">Solde, retraits et compte Stripe Connect</p>
          </Link>
        </div>
      </div>
    </div>
  );
}
