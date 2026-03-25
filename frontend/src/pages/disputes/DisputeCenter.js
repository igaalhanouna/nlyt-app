import React from 'react';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';

export default function DisputeCenter() {
  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Contestations' },
      ]} />
      <div className="max-w-6xl mx-auto px-6 pb-12">
        <h1 className="text-2xl font-bold text-slate-900 mb-4">Centre de contestations</h1>
        <div className="bg-white p-8 rounded-lg border border-slate-200">
          <p className="text-slate-600">Les contestations apparaitront ici.</p>
        </div>
      </div>
    </div>
  );
}
