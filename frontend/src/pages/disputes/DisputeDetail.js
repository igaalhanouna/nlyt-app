import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { ArrowLeft } from 'lucide-react';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';

export default function DisputeDetail() {
  const { id } = useParams();
  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Contestations', href: '/disputes' },
        { label: `Contestation #${id?.slice(0, 8)}` },
      ]} />
      <div className="max-w-6xl mx-auto px-6 pb-12">
        <Link to="/disputes">
          <Button variant="ghost" className="mb-4" size="sm">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Retour aux contestations
          </Button>
        </Link>
        <h1 className="text-2xl font-bold text-slate-900 mb-4">Details de la contestation</h1>
        <div className="bg-white p-8 rounded-lg border border-slate-200">
          <p className="text-slate-600">Contestation ID: {id}</p>
        </div>
      </div>
    </div>
  );
}
