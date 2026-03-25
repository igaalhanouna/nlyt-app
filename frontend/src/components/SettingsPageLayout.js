import React from 'react';
import AppNavbar from './AppNavbar';
import AppBreadcrumb from './AppBreadcrumb';

export default function SettingsPageLayout({ title, description, breadcrumbLabel, action, children }) {
  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', shortLabel: 'Accueil', href: '/dashboard' },
        { label: 'Paramètres', href: '/settings' },
        { label: breadcrumbLabel || title },
      ]} />

      <div className="max-w-4xl mx-auto px-4 md:px-6 pb-16">
        {/* Title + Description */}
        <div className="mb-1">
          <div className="flex items-center justify-between gap-3">
            <h1 className="text-xl md:text-2xl font-bold text-slate-900" data-testid="settings-page-title">{title}</h1>
            {action && <div className="flex-shrink-0 hidden sm:block">{action}</div>}
          </div>
        </div>
        {description && (
          <p className="text-sm text-slate-500 mb-4 md:mb-6">{description}</p>
        )}
        {!description && <div className="mb-4 md:mb-6" />}
        {/* Mobile action button — full width */}
        {action && <div className="sm:hidden mb-6">{action}</div>}

        {children}
      </div>
    </div>
  );
}
