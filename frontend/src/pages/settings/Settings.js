import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { ArrowLeft, User, Building2, Plug, CreditCard, Wallet } from 'lucide-react';

export default function Settings() {
  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <span className="block text-lg font-bold tracking-[0.35em] text-slate-900">N<span className="text-slate-400">·</span>L<span className="text-slate-400">·</span>Y<span className="text-slate-400">·</span>T</span>
            <span className="block text-[10px] font-medium tracking-[0.25em] text-slate-400 uppercase">Never Lose Your Time</span>
          </div>
          <h1 className="text-3xl font-bold">Paramètres</h1>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Link to="/settings/profile" className="p-6 bg-white rounded-lg border border-slate-200 hover:border-slate-300 transition-colors" data-testid="settings-profile-link">
            <User className="w-8 h-8 text-slate-700 mb-3" />
            <h3 className="font-semibold text-slate-900 mb-1">Profil</h3>
            <p className="text-sm text-slate-600">Gérez vos informations personnelles et choisissez vos associations préférées</p>
          </Link>
          <Link to="/settings/workspace" className="p-6 bg-white rounded-lg border border-slate-200 hover:border-slate-300 transition-colors" data-testid="settings-workspace-link">
            <Building2 className="w-8 h-8 text-slate-700 mb-3" />
            <h3 className="font-semibold text-slate-900 mb-1">Workspace</h3>
            <p className="text-sm text-slate-600">Configuration du workspace</p>
          </Link>
          <Link to="/settings/integrations" className="p-6 bg-white rounded-lg border border-slate-200 hover:border-slate-300 transition-colors" data-testid="settings-integrations-link">
            <Plug className="w-8 h-8 text-slate-700 mb-3" />
            <h3 className="font-semibold text-slate-900 mb-1">Intégrations</h3>
            <p className="text-sm text-slate-600">Calendriers et visioconférence</p>
          </Link>
          <Link to="/settings/payment" className="p-6 bg-white rounded-lg border border-slate-200 hover:border-slate-300 transition-colors" data-testid="settings-payment-link">
            <CreditCard className="w-8 h-8 text-slate-700 mb-3" />
            <h3 className="font-semibold text-slate-900 mb-1">Paiement</h3>
            <p className="text-sm text-slate-600">Moyen de paiement par défaut pour vos garanties</p>
          </Link>
          <Link to="/settings/wallet" className="p-6 bg-white rounded-lg border border-slate-200 hover:border-slate-300 transition-colors" data-testid="settings-wallet-link">
            <Wallet className="w-8 h-8 text-slate-700 mb-3" />
            <h3 className="font-semibold text-slate-900 mb-1">Wallet</h3>
            <p className="text-sm text-slate-600">Solde, retraits et compte de paiement Stripe Connect</p>
          </Link>
        </div>
      </div>
    </div>
  );
}
