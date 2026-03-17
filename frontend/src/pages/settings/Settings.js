import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { ArrowLeft, User, Building2, Plug } from 'lucide-react';

export default function Settings() {
  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-4xl mx-auto">
        <Link to="/dashboard"><Button variant="ghost" className="mb-6"><ArrowLeft className="w-4 h-4 mr-2" />Retour</Button></Link>
        <h1 className="text-3xl font-bold mb-8">Paramètres</h1>
        <div className="grid md:grid-cols-3 gap-6">
          <Link to="/settings/profile" className="p-6 bg-white rounded-lg border border-slate-200 hover:border-slate-300 transition-colors">
            <User className="w-8 h-8 text-slate-700 mb-3" />
            <h3 className="font-semibold text-slate-900 mb-1">Profil</h3>
            <p className="text-sm text-slate-600">Gérez vos informations personnelles</p>
          </Link>
          <Link to="/settings/workspace" className="p-6 bg-white rounded-lg border border-slate-200 hover:border-slate-300 transition-colors">
            <Building2 className="w-8 h-8 text-slate-700 mb-3" />
            <h3 className="font-semibold text-slate-900 mb-1">Workspace</h3>
            <p className="text-sm text-slate-600">Configuration du workspace</p>
          </Link>
          <Link to="/settings/integrations" className="p-6 bg-white rounded-lg border border-slate-200 hover:border-slate-300 transition-colors">
            <Plug className="w-8 h-8 text-slate-700 mb-3" />
            <h3 className="font-semibold text-slate-900 mb-1">Intégrations</h3>
            <p className="text-sm text-slate-600">Calendriers et paiements</p>
          </Link>
        </div>
      </div>
    </div>
  );
}
