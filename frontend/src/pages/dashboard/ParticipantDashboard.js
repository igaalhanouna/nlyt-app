import React from 'react';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';

export default function ParticipantDashboard() {
  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Mes invitations' },
      ]} />
      <div className="max-w-6xl mx-auto px-6 pb-12">
        <h1 className="text-2xl font-bold text-slate-900 mb-4">Mes invitations</h1>
        <div className="bg-white p-8 rounded-lg border border-slate-200">
          <p className="text-slate-600">Vos invitations aux engagements apparaitront ici.</p>
        </div>
      </div>
    </div>
  );
}
