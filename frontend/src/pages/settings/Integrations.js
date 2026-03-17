import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { ArrowLeft, Calendar, CreditCard } from 'lucide-react';

export default function Integrations() {
  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-4xl mx-auto">
        <Link to="/settings"><Button variant="ghost" className="mb-6"><ArrowLeft className="w-4 h-4 mr-2" />Retour</Button></Link>
        <h1 className="text-3xl font-bold mb-8">Intégrations</h1>
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-lg border border-slate-200">
            <div className="flex items-start gap-4">
              <Calendar className="w-8 h-8 text-slate-700" />
              <div className="flex-1">
                <h3 className="font-semibold text-slate-900 mb-2">Calendriers</h3>
                <p className="text-sm text-slate-600 mb-4">Connectez Google Calendar ou Outlook</p>
                <Button variant="outline" size="sm">Configurer</Button>
              </div>
            </div>
          </div>
          <div className="bg-white p-6 rounded-lg border border-slate-200">
            <div className="flex items-start gap-4">
              <CreditCard className="w-8 h-8 text-slate-700" />
              <div className="flex-1">
                <h3 className="font-semibold text-slate-900 mb-2">Paiements Stripe</h3>
                <p className="text-sm text-slate-600 mb-4">Configuré et actif</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
