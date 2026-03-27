import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ChevronRight } from 'lucide-react';
import { attendanceAPI } from '../../services/api';

export default function PendingReviewBanner() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    attendanceAPI.pendingReviews()
      .then(res => setCount(res.data.count || 0))
      .catch(() => {});
  }, []);

  if (count === 0) return null;

  return (
    <Link to="/disputes" data-testid="pending-review-banner">
      <div className="mb-6 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex items-center justify-between hover:bg-amber-100/60 transition-colors cursor-pointer group">
        <div className="flex items-center gap-3">
          <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-amber-100 flex items-center justify-center">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
          </div>
          <div>
            <p className="text-sm font-semibold text-amber-900">
              {count} decision{count > 1 ? 's' : ''} en attente
            </p>
            <p className="text-xs text-amber-700">
              Des participants necessitent votre verification avant action financiere
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1 text-amber-700 text-sm font-medium group-hover:gap-2 transition-all">
          Voir et decider
          <ChevronRight className="w-4 h-4" />
        </div>
      </div>
    </Link>
  );
}
