import React from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';

export default function AppBreadcrumb({ items }) {
  if (!items || items.length === 0) return null;

  return (
    <div className="max-w-7xl mx-auto px-6 py-3" data-testid="app-breadcrumb">
      <ol className="flex items-center gap-1.5 text-sm">
        {items.map((item, i) => {
          const isLast = i === items.length - 1;
          return (
            <li key={i} className="flex items-center gap-1.5">
              {i > 0 && <ChevronRight className="w-3.5 h-3.5 text-slate-300 flex-shrink-0" />}
              {isLast ? (
                <span className="text-slate-900 font-medium">{item.label}</span>
              ) : (
                <Link
                  to={item.href}
                  className="text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {item.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
