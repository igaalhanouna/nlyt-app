import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ClipboardCheck, Clock, CheckCircle2, ChevronRight, Users, Loader2 } from 'lucide-react';
import AppNavbar from '../../components/AppNavbar';
import { attendanceAPI } from '../../services/api';
import { formatDateTimeFr } from '../../utils/dateFormat';

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
      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="flex items-center gap-3 mb-6">
          <ClipboardCheck className="w-6 h-6 text-slate-700" />
          <h1 className="text-2xl font-bold text-slate-900">Feuilles de presence</h1>
        </div>

        <p className="text-sm text-slate-500 mb-8 max-w-xl">
          Declarez la presence des participants pour les rendez-vous ou la verification technologique est insuffisante.
          Vos declarations seront croisees avec celles des autres participants.
        </p>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
          </div>
        ) : sheets.length === 0 ? (
          <div className="text-center py-16" data-testid="presences-empty">
            <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
            <p className="text-slate-500 font-medium">Aucune feuille de presence en attente</p>
            <p className="text-sm text-slate-400 mt-1">Vous serez notifie lorsqu'un rendez-vous necessite votre declaration.</p>
          </div>
        ) : (
          <div className="space-y-3" data-testid="presences-list">
            {pendingCount > 0 && (
              <p className="text-sm font-medium text-slate-600 mb-4" data-testid="presences-pending-count">
                {pendingCount} declaration{pendingCount > 1 ? 's' : ''} en attente
              </p>
            )}

            {sheets.map((sheet) => (
              <SheetCard
                key={sheet.sheet_id || sheet.appointment_id}
                sheet={sheet}
                onNavigate={() => navigate(`/appointments/${sheet.appointment_id}/attendance-sheet`, { state: { from: 'presences' } })}
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

  return (
    <button
      onClick={submitted ? undefined : onNavigate}
      className={`w-full text-left rounded-lg border p-4 transition-colors ${
        submitted
          ? 'bg-white border-slate-200 opacity-70 cursor-default'
          : 'bg-white border-slate-200 hover:border-blue-300 hover:bg-blue-50/30 cursor-pointer'
      }`}
      disabled={submitted}
      data-testid={`sheet-card-${sheet.appointment_id}`}
    >
      <div className="flex items-center gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-semibold text-slate-800 truncate">{sheet.title}</span>
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

          <div className="flex items-center gap-3 text-xs text-slate-500">
            {sheet.start_datetime && (
              <span>{formatDateTimeFr(sheet.start_datetime)}</span>
            )}
            <span className="flex items-center gap-1">
              <Users className="w-3 h-3" />
              {sheet.targets_count} participant{sheet.targets_count > 1 ? 's' : ''} a declarer
            </span>
          </div>

          {sheet.declarative_deadline && !submitted && (
            <p className="text-xs text-amber-600 mt-1.5">
              Date limite : {formatDateTimeFr(sheet.declarative_deadline)}
            </p>
          )}
        </div>

        {!submitted && (
          <ChevronRight className="w-5 h-5 text-slate-400 flex-shrink-0" />
        )}
      </div>
    </button>
  );
}
