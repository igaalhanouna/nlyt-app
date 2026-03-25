import React from 'react';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';

export default function ReviewerDashboard() {
  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Administration' },
      ]} />
      <div className="max-w-7xl mx-auto px-6 pb-12">
        <h1 className="text-2xl font-bold text-slate-900 mb-4">Tableau de bord administrateur</h1>
        <div className="bg-white p-8 rounded-lg border border-slate-200">
          <p className="text-slate-600">Dashboard administrateur pour la revue des cas.</p>
        </div>
      </div>
    </div>
  );
}
