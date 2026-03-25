import React from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';

export default function AppBreadcrumb({ items }) {
  if (!items || items.length === 0) return null;

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-6 py-2.5 md:py-3 overflow-hidden" data-testid="app-breadcrumb">
      <ol className="flex items-center gap-1 md:gap-1.5 text-sm overflow-x-auto scrollbar-none">
        {items.map((item, i) => {
          const isLast = i === items.length - 1;
          return (
            <li key={i} className="flex items-center gap-1 md:gap-1.5 flex-shrink-0">
              {i > 0 && <ChevronRight className="w-3 h-3 md:w-3.5 md:h-3.5 text-slate-300 flex-shrink-0" />}
              {isLast ? (
                <span className="text-slate-900 font-medium truncate max-w-[200px] md:max-w-none">{item.label}</span>
              ) : (
                <Link
                  to={item.href}
                  className="text-slate-400 hover:text-slate-600 transition-colors whitespace-nowrap"
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
