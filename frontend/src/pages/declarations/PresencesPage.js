import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ClipboardCheck, Clock, CheckCircle2, ChevronRight, Users,
  Loader2, MapPin, Video, Calendar, ArrowRight, Eye
} from 'lucide-react';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';
import { attendanceAPI } from '../../services/api';
import { formatDateTimeCompactFr } from '../../utils/dateFormat';

export default function PresencesPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [sheets, setSheets] = useState([]);
  const [pendingCount, setPendingCount] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await attendanceAPI.pendingSheets();
      setSheets(res.data.pending_sheets || []);
      setPendingCount(res.data.count || 0);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="min-h-screen bg-slate-50" data-testid="presences-page">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Presences' },
      ]} />
      <div className="max-w-2xl mx-auto px-4 py-6 sm:py-8">
        <div className="flex items-center gap-2 mb-2">
          <ClipboardCheck className="w-5 h-5 text-slate-600" />
          <h1 className="text-xl font-semibold text-slate-800">Feuilles de presence</h1>
          {pendingCount > 0 && (
            <span className="ml-2 px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 text-xs font-medium" data-testid="presences-pending-count">
              {pendingCount} a remplir
            </span>
          )}
        </div>

        <p className="text-sm text-slate-500 mb-6 max-w-xl">
          Declarez la presence des participants pour les rendez-vous ou la verification technologique est insuffisante.
        </p>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
          </div>
        ) : sheets.length === 0 ? (
          <div className="bg-white rounded-xl border p-8 text-center" data-testid="presences-empty">
            <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-3" />
            <p className="text-sm text-slate-500">Aucune feuille de presence en attente</p>
          </div>
        ) : (
          <div className="space-y-3" data-testid="presences-list">
            {sheets.map((sheet) => (
              <SheetCard
                key={sheet.sheet_id || sheet.appointment_id}
                sheet={sheet}
                onNavigate={() => navigate(
                  `/appointments/${sheet.appointment_id}/attendance-sheet`,
                  { state: { from: 'presences' } }
                )}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SheetCard({ sheet, onNavigate }) {
  const submitted = sheet.already_submitted;
  const isPhysical = sheet.appointment_type === 'physical';
  const locationLabel = isPhysical
    ? (sheet.appointment_location || 'Physique')
    : (sheet.appointment_meeting_provider || 'Visioconference');

  return (
    <div
      className="bg-white rounded-xl border border-slate-200 overflow-hidden"
      data-testid={`sheet-card-${sheet.appointment_id}`}
    >
      {/* Header: RDV context */}
      <div className="px-4 pt-4 pb-3">
        <div className="flex items-start justify-between gap-3 mb-2">
          <h3 className="text-sm font-semibold text-slate-800 leading-tight truncate" data-testid={`sheet-title-${sheet.appointment_id}`}>
            {sheet.title}
          </h3>
          {submitted ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-600 border border-emerald-200 flex-shrink-0" data-testid={`sheet-submitted-${sheet.appointment_id}`}>
              <CheckCircle2 className="w-3 h-3" />
              Soumise
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-600 border border-blue-200 flex-shrink-0" data-testid={`sheet-pending-${sheet.appointment_id}`}>
              <Clock className="w-3 h-3" />
              A remplir
            </span>
          )}
        </div>

        {/* Metadata row */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
          {sheet.start_datetime && (
            <span className="flex items-center gap-1">
              <Calendar className="w-3 h-3 text-slate-400" />
              {formatDateTimeCompactFr(sheet.start_datetime)}
            </span>
          )}
          {sheet.duration_minutes > 0 && (
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3 text-slate-400" />
              {sheet.duration_minutes} min
            </span>
          )}
          <span className="flex items-center gap-1">
            {isPhysical
              ? <><MapPin className="w-3 h-3 text-slate-400" /> <span className="truncate max-w-[180px]">{locationLabel}</span></>
              : <><Video className="w-3 h-3 text-slate-400" /> {locationLabel}</>
            }
          </span>
        </div>

        {/* Participants + deadline */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <Users className="w-3 h-3 text-slate-400" />
            {submitted
              ? `${sheet.targets_count} declaration${sheet.targets_count > 1 ? 's' : ''} soumise${sheet.targets_count > 1 ? 's' : ''}`
              : `${sheet.targets_count} participant${sheet.targets_count > 1 ? 's' : ''} a declarer`
            }
          </span>
          {sheet.declarative_deadline && !submitted && (
            <span className="text-amber-600 font-medium">
              Limite : {formatDateTimeCompactFr(sheet.declarative_deadline)}
            </span>
          )}
        </div>
      </div>

      {/* CTA section */}
      <div className="px-4 py-2.5 bg-slate-50/60 border-t border-slate-100 flex items-center justify-between">
        <button
          onClick={onNavigate}
          className="flex items-center gap-1.5 text-xs font-medium transition-colors text-blue-600 hover:text-blue-800"
          data-testid={`sheet-cta-${sheet.appointment_id}`}
        >
          {submitted ? (
            <><Eye className="w-3.5 h-3.5" /> Voir ma declaration</>
          ) : (
            <><ChevronRight className="w-3.5 h-3.5" /> Remplir ma feuille</>
          )}
        </button>
        <Link
          to={`/appointments/${sheet.appointment_id}`}
          className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 font-medium transition-colors"
          data-testid={`sheet-view-apt-${sheet.appointment_id}`}
        >
          Voir le rendez-vous
          <ArrowRight className="w-3 h-3" />
        </Link>
      </div>
    </div>
  );
}
