import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, ArrowRight } from 'lucide-react';
import { Button } from '../../components/ui/button';
import api from '../../services/api';

export default function MilestonesSection() {
  const [data, setData] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.get('/api/wallet/milestones')
      .then((r) => setData(r.data))
      .catch(() => {});
  }, []);

  if (!data || data.attended_count === 0) return null;

  const reached = data.milestones.filter((m) => m.reached);
  const next = data.milestones.find((m) => !m.reached);
  const progress = next
    ? Math.round((data.attended_count / next.threshold) * 100)
    : 100;

  return (
    <div data-testid="milestones-section" className="bg-white border border-slate-200 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100">
        <span className="text-sm font-semibold text-slate-900">
          Vos engagements
        </span>
      </div>

      <div className="p-4">
        {/* Counter */}
        <div className="flex items-baseline gap-2 mb-4">
          <span
            data-testid="milestones-attended-count"
            className="text-3xl font-extrabold text-slate-900"
          >
            {data.attended_count}
          </span>
          <span className="text-sm text-slate-500">
            engagement{data.attended_count > 1 ? 's' : ''} tenu{data.attended_count > 1 ? 's' : ''}
          </span>
        </div>

        {/* Progress bar toward next milestone */}
        {next && (
          <div className="mb-4">
            <div className="flex justify-between text-xs text-slate-400 mb-1">
              <span>{data.attended_count}/{next.threshold}</span>
              <span>{next.label}</span>
            </div>
            <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
              <div
                data-testid="milestones-progress-bar"
                className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                style={{ width: `${Math.min(progress, 100)}%` }}
              />
            </div>
          </div>
        )}

        {/* Badges */}
        <div className="flex flex-wrap gap-2 mb-4">
          {data.milestones.map((m) => (
            <span
              key={m.threshold}
              data-testid={`milestone-badge-${m.threshold}`}
              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                m.reached
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : 'bg-slate-50 text-slate-400 border border-slate-100'
              }`}
            >
              {m.reached && <Check size={12} />}
              {m.threshold}
            </span>
          ))}
        </div>

        {/* CTA Organiser — only if user has participated but never organized */}
        {data.show_organizer_cta && (
          <div
            data-testid="organizer-cta"
            className="mt-3 pt-3 border-t border-slate-100"
          >
            <p className="text-sm text-slate-600 mb-2">
              Vous tenez vos engagements. Et si vous organisiez le vôtre ?
            </p>
            <Button
              data-testid="organizer-cta-btn"
              onClick={() => navigate('/dashboard')}
              className="w-full flex items-center justify-center gap-2"
              style={{ background: '#0A0A0B', color: '#fff' }}
            >
              Organiser un engagement
              <ArrowRight size={16} />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
