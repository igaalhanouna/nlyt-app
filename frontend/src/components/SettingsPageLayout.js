import React from 'react';
import AppNavbar from './AppNavbar';
import AppBreadcrumb from './AppBreadcrumb';

export default function SettingsPageLayout({ title, description, breadcrumbLabel, action, children }) {
  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Paramètres', href: '/settings' },
        { label: breadcrumbLabel || title },
      ]} />

      <div className="max-w-4xl mx-auto px-6 pb-16">
        <div className="flex items-center justify-between mb-1">
          <h1 className="text-2xl font-bold text-slate-900" data-testid="settings-page-title">{title}</h1>
          {action && <div className="flex-shrink-0">{action}</div>}
        </div>
        {description && (
          <p className="text-sm text-slate-500 mb-8">{description}</p>
        )}
        {!description && <div className="mb-8" />}

        {children}
      </div>
    </div>
  );
}
