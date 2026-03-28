import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight, CalendarDays, Clock, MapPin, Video, Users, User, Loader2 } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { appointmentAPI, externalEventsAPI } from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import CalendarSyncPanel from '../dashboard/CalendarSyncPanel';

const DAYS_FR = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];
const MONTHS_FR = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'];

const SOURCE_STYLES = {
  nlyt: { dot: 'bg-slate-900', pill: 'bg-slate-900 text-white', label: 'NLYT' },
  google: { dot: 'bg-[#4285F4]', pill: 'border border-[#4285F4] text-[#4285F4] bg-white', label: 'Google' },
  outlook: { dot: 'bg-[#0078D4]', pill: 'border border-[#0078D4] text-[#0078D4] bg-white', label: 'Microsoft' },
};

function getDaysInMonth(year, month) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfWeek(year, month) {
  const d = new Date(year, month, 1).getDay();
  return d === 0 ? 6 : d - 1; // Monday = 0
}

function dateKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function formatTime(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

function formatDuration(mins) {
  if (!mins) return '';
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m > 0 ? `${h}h${String(m).padStart(2, '0')}` : `${h}h`;
}

export default function AgendaPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [events, setEvents] = useState([]);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDay, setSelectedDay] = useState(null);

  // Calendar sync toggles (same logic as Dashboard)
  const [importSettings, setImportSettings] = useState(null);
  const [syncing, setSyncing] = useState(false);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const loadImportSettings = useCallback(async () => {
    try {
      const res = await externalEventsAPI.getImportSettings();
      setImportSettings(res.data);
    } catch { /* silent */ }
  }, []);

  const handleImportSettingChange = async (provider, enabled) => {
    await externalEventsAPI.updateImportSetting(provider, enabled);
    await loadImportSettings();
    if (enabled) await fetchEvents();
    if (!enabled) setEvents(prev => prev.filter(e => e.source === 'nlyt' || e.source !== provider));
  };

  const handleSync = async (force = false) => {
    setSyncing(true);
    try {
      await externalEventsAPI.sync(force);
      await loadImportSettings();
      await fetchEvents();
    } catch { /* silent */ }
    finally { setSyncing(false); }
  };

  // Enabled providers for filtering
  const enabledProviders = useMemo(() => {
    const providers = importSettings?.providers || {};
    return new Set(
      Object.entries(providers)
        .filter(([, cfg]) => cfg?.import_enabled)
        .map(([key]) => key)
    );
  }, [importSettings]);

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    try {
      const [timelineRes, externalRes] = await Promise.all([
        appointmentAPI.myTimeline(),
        externalEventsAPI.list().catch(() => ({ data: { events: [] } })),
      ]);

      const nlytItems = [];
      const timeline = timelineRes.data || {};
      for (const bucket of ['action_required', 'upcoming', 'past']) {
        const items = timeline[bucket] || [];
        for (const item of items) {
          nlytItems.push({
            id: item.appointment_id,
            title: item.title || 'Sans titre',
            start: item.starts_at || item.start_datetime,
            duration: item.duration_minutes || 60,
            source: 'nlyt',
            type: item.appointment_type || 'physical',
            role: item.role || '',
            status: item.status || 'active',
            appointmentId: item.appointment_id,
          });
        }
      }

      const extItems = ((externalRes.data || {}).events || []).map(ev => ({
        id: ev.event_id || ev.external_event_id || Math.random().toString(36),
        title: ev.title || '(Sans titre)',
        start: ev.start_datetime || ev.start,
        duration: ev.duration_minutes || (ev.end_datetime && ev.start_datetime
          ? Math.max(1, Math.round((new Date(ev.end_datetime) - new Date(ev.start_datetime)) / 60000))
          : 60),
        source: ev.provider || 'google',
        type: null,
        role: null,
        status: null,
        appointmentId: null,
      }));

      setEvents([...nlytItems, ...extItems]);
    } catch (err) {
      console.error('Agenda fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadImportSettings().then(() => fetchEvents());
  }, [loadImportSettings, fetchEvents]);

  // Group events by day key — filtered by enabled providers
  const eventsByDay = useMemo(() => {
    const map = {};
    for (const ev of events) {
      if (!ev.start) continue;
      // Filter: NLYT always visible, externals only if provider toggle is ON
      if (ev.source !== 'nlyt' && !enabledProviders.has(ev.source)) continue;
      const dk = dateKey(new Date(ev.start));
      if (!map[dk]) map[dk] = [];
      map[dk].push(ev);
    }
    // Sort each day: by time ascending, NLYT first at same time
    for (const dk of Object.keys(map)) {
      map[dk].sort((a, b) => {
        const ta = new Date(a.start).getTime();
        const tb = new Date(b.start).getTime();
        if (ta !== tb) return ta - tb;
        if (a.source === 'nlyt' && b.source !== 'nlyt') return -1;
        if (a.source !== 'nlyt' && b.source === 'nlyt') return 1;
        return 0;
      });
    }
    return map;
  }, [events, enabledProviders]);

  const today = dateKey(new Date());

  const prevMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
    setSelectedDay(null);
  };
  const nextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
    setSelectedDay(null);
  };
  const goToday = () => {
    setCurrentDate(new Date());
    setSelectedDay(today);
  };

  // Build calendar grid
  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfWeek(year, month);
  const prevMonthDays = getDaysInMonth(year, month - 1);

  const cells = [];
  // Leading days from previous month
  for (let i = firstDay - 1; i >= 0; i--) {
    const d = prevMonthDays - i;
    const dt = new Date(year, month - 1, d);
    cells.push({ day: d, key: dateKey(dt), outside: true });
  }
  // Current month
  for (let d = 1; d <= daysInMonth; d++) {
    const dt = new Date(year, month, d);
    cells.push({ day: d, key: dateKey(dt), outside: false });
  }
  // Trailing days
  const remaining = 42 - cells.length;
  for (let d = 1; d <= remaining; d++) {
    const dt = new Date(year, month + 1, d);
    cells.push({ day: d, key: dateKey(dt), outside: true });
  }

  const selectedEvents = selectedDay ? (eventsByDay[selectedDay] || []) : [];

  const handleEventClick = (ev) => {
    if (ev.source === 'nlyt' && ev.appointmentId) {
      navigate(`/appointments/${ev.appointmentId}`);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50" data-testid="agenda-page">
      <AppNavbar />

      <div className="max-w-5xl mx-auto px-4 md:px-6 pt-6 pb-12">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <CalendarDays className="w-5 h-5 text-slate-400" />
            <h1 className="text-lg font-bold text-slate-900" data-testid="agenda-title">Agenda</h1>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={goToday} className="h-8 text-xs" data-testid="agenda-today-btn">
              Aujourd'hui
            </Button>
          </div>
        </div>

        {/* Month navigation */}
        <div className="flex items-center justify-between mb-4">
          <button onClick={prevMonth} className="p-2 rounded-lg hover:bg-slate-100 transition-colors" data-testid="agenda-prev-month">
            <ChevronLeft className="w-5 h-5 text-slate-600" />
          </button>
          <h2 className="text-base font-semibold text-slate-800" data-testid="agenda-current-month">
            {MONTHS_FR[month]} {year}
          </h2>
          <button onClick={nextMonth} className="p-2 rounded-lg hover:bg-slate-100 transition-colors" data-testid="agenda-next-month">
            <ChevronRight className="w-5 h-5 text-slate-600" />
          </button>
        </div>

        {/* Calendar sync toggles — same component as Dashboard */}
        {importSettings && (
          <div className="mb-4">
            <CalendarSyncPanel
              importSettings={importSettings}
              onSettingChange={handleImportSettingChange}
              onSync={handleSync}
              syncing={syncing}
            />
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
          </div>
        ) : (
          <>
            {/* Calendar grid */}
            <div className="bg-white border border-slate-200 rounded-xl overflow-hidden mb-6" data-testid="agenda-grid">
              {/* Day headers */}
              <div className="grid grid-cols-7 border-b border-slate-100">
                {DAYS_FR.map(d => (
                  <div key={d} className="py-2.5 text-center text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    {d}
                  </div>
                ))}
              </div>

              {/* Day cells */}
              <div className="grid grid-cols-7">
                {cells.map((cell, i) => {
                  const dayEvents = eventsByDay[cell.key] || [];
                  const isToday = cell.key === today;
                  const isSelected = cell.key === selectedDay;
                  const nlytCount = dayEvents.filter(e => e.source === 'nlyt').length;
                  const extCount = dayEvents.filter(e => e.source !== 'nlyt').length;

                  return (
                    <button
                      key={i}
                      onClick={() => setSelectedDay(isSelected ? null : cell.key)}
                      data-testid={`agenda-day-${cell.key}`}
                      className={`
                        relative min-h-[72px] md:min-h-[80px] p-1.5 border-b border-r border-slate-50
                        text-left transition-colors
                        ${cell.outside ? 'bg-slate-25 text-slate-300' : 'hover:bg-slate-50'}
                        ${isSelected ? 'bg-slate-100 ring-1 ring-inset ring-slate-300' : ''}
                      `}
                    >
                      <span className={`
                        inline-flex items-center justify-center w-6 h-6 text-xs font-medium rounded-full
                        ${isToday ? 'bg-slate-900 text-white' : cell.outside ? 'text-slate-300' : 'text-slate-700'}
                      `}>
                        {cell.day}
                      </span>

                      {/* Event dots */}
                      {dayEvents.length > 0 && (
                        <div className="flex items-center gap-0.5 mt-1 flex-wrap">
                          {nlytCount > 0 && (
                            <div className="flex items-center gap-px">
                              {Array.from({ length: Math.min(nlytCount, 3) }).map((_, j) => (
                                <span key={`n${j}`} className="w-1.5 h-1.5 rounded-full bg-slate-900" />
                              ))}
                              {nlytCount > 3 && <span className="text-[9px] text-slate-500 ml-0.5">+{nlytCount - 3}</span>}
                            </div>
                          )}
                          {extCount > 0 && (
                            <div className="flex items-center gap-px ml-0.5">
                              {Array.from({ length: Math.min(extCount, 2) }).map((_, j) => (
                                <span key={`e${j}`} className="w-1.5 h-1.5 rounded-full border border-blue-400 bg-transparent" />
                              ))}
                              {extCount > 2 && <span className="text-[9px] text-blue-400 ml-0.5">+{extCount - 2}</span>}
                            </div>
                          )}
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Legend */}
            <div className="flex items-center gap-4 mb-4 px-1">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-slate-900" />
                <span className="text-[11px] text-slate-500">NLYT</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full border border-blue-400 bg-transparent" />
                <span className="text-[11px] text-slate-500">Google / Microsoft</span>
              </div>
            </div>

            {/* Day detail panel */}
            {selectedDay && (
              <div className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid="agenda-day-detail">
                <div className="px-4 py-3 border-b border-slate-100 bg-slate-50">
                  <h3 className="text-sm font-semibold text-slate-800" data-testid="agenda-detail-date">
                    {new Date(selectedDay + 'T00:00:00').toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
                  </h3>
                </div>

                {selectedEvents.length === 0 ? (
                  <div className="px-4 py-8 text-center">
                    <p className="text-sm text-slate-400">Aucun événement ce jour</p>
                  </div>
                ) : (
                  <div className="divide-y divide-slate-50">
                    {selectedEvents.map(ev => {
                      const style = SOURCE_STYLES[ev.source] || SOURCE_STYLES.google;
                      const isNlyt = ev.source === 'nlyt';
                      const isCancelled = ev.status === 'cancelled';

                      return (
                        <div
                          key={ev.id}
                          onClick={() => handleEventClick(ev)}
                          data-testid={`agenda-event-${ev.id}`}
                          className={`
                            px-4 py-3 flex items-start gap-3 transition-colors
                            ${isNlyt ? 'cursor-pointer hover:bg-slate-50' : 'cursor-default'}
                            ${isCancelled ? 'opacity-50' : ''}
                          `}
                        >
                          {/* Time column */}
                          <div className="w-12 flex-shrink-0 pt-0.5">
                            <span className="text-sm font-mono font-medium text-slate-700">{formatTime(ev.start)}</span>
                          </div>

                          {/* Color bar */}
                          <div className={`w-1 self-stretch rounded-full flex-shrink-0 ${style.dot}`} />

                          {/* Content */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-0.5">
                              <span className={`text-sm font-medium ${isCancelled ? 'line-through text-slate-400' : 'text-slate-900'}`}>
                                {ev.title}
                              </span>
                              <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold tracking-wide ${style.pill}`}>
                                {style.label}
                              </span>
                            </div>

                            <div className="flex items-center gap-3 text-xs text-slate-500">
                              <span className="flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {formatDuration(ev.duration)}
                              </span>
                              {isNlyt && ev.type && (
                                <span className="flex items-center gap-1">
                                  {ev.type === 'video' ? <Video className="w-3 h-3" /> : <MapPin className="w-3 h-3" />}
                                  {ev.type === 'video' ? 'Visio' : 'Physique'}
                                </span>
                              )}
                              {isNlyt && ev.role && (
                                <span className="flex items-center gap-1">
                                  {ev.role === 'organizer' ? <Users className="w-3 h-3" /> : <User className="w-3 h-3" />}
                                  {ev.role === 'organizer' ? 'Organisateur' : 'Participant'}
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Arrow for NLYT */}
                          {isNlyt && !isCancelled && (
                            <ChevronRight className="w-4 h-4 text-slate-300 flex-shrink-0 mt-1" />
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
