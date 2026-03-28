import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight, CalendarDays, Clock, MapPin, Video, Users, User, Loader2 } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { appointmentAPI, externalEventsAPI } from '../../services/api';
import AppNavbar from '../../components/AppNavbar';
import CalendarSyncPanel from '../dashboard/CalendarSyncPanel';

const DAYS_FR = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];
const DAYS_FR_FULL = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'];
const MONTHS_FR = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'];

const SOURCE_STYLES = {
  nlyt: { dot: 'bg-slate-900', pill: 'bg-slate-900 text-white', bar: 'bg-slate-900', label: 'NLYT' },
  google: { dot: 'bg-[#4285F4]', pill: 'border border-[#4285F4] text-[#4285F4] bg-white', bar: 'bg-[#4285F4]', label: 'Google' },
  outlook: { dot: 'bg-[#0078D4]', pill: 'border border-[#0078D4] text-[#0078D4] bg-white', bar: 'bg-[#0078D4]', label: 'Microsoft' },
};

const START_HOUR = 7;
const END_HOUR = 22;
const HOUR_HEIGHT = 56; // px per hour

function getDaysInMonth(year, month) { return new Date(year, month + 1, 0).getDate(); }
function getFirstDayOfWeek(year, month) { const d = new Date(year, month, 1).getDay(); return d === 0 ? 6 : d - 1; }
function dateKey(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }
function formatTime(isoStr) { if (!isoStr) return ''; return new Date(isoStr).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }); }
function formatDuration(mins) { if (!mins) return ''; if (mins < 60) return `${mins} min`; const h = Math.floor(mins / 60); const m = mins % 60; return m > 0 ? `${h}h${String(m).padStart(2, '0')}` : `${h}h`; }

function getMonday(d) {
  const dt = new Date(d);
  const day = dt.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  dt.setDate(dt.getDate() + diff);
  dt.setHours(0, 0, 0, 0);
  return dt;
}

function getWeekDays(refDate) {
  const mon = getMonday(refDate);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(mon);
    d.setDate(d.getDate() + i);
    return d;
  });
}

// ── Shared event row (used in month detail + day view) ──
function EventRow({ ev, onEventClick }) {
  const style = SOURCE_STYLES[ev.source] || SOURCE_STYLES.google;
  const isNlyt = ev.source === 'nlyt';
  const isCancelled = ev.status === 'cancelled';
  return (
    <div
      onClick={() => onEventClick(ev)}
      data-testid={`agenda-event-${ev.id}`}
      className={`px-4 py-3 flex items-start gap-3 transition-colors ${isNlyt ? 'cursor-pointer hover:bg-slate-50' : 'cursor-default'} ${isCancelled ? 'opacity-50' : ''}`}
    >
      <div className="w-12 flex-shrink-0 pt-0.5">
        <span className="text-sm font-mono font-medium text-slate-700">{formatTime(ev.start)}</span>
      </div>
      <div className={`w-1 self-stretch rounded-full flex-shrink-0 ${style.dot}`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className={`text-sm font-medium ${isCancelled ? 'line-through text-slate-400' : 'text-slate-900'}`}>{ev.title}</span>
          <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold tracking-wide ${style.pill}`}>{style.label}</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{formatDuration(ev.duration)}</span>
          {isNlyt && ev.type && <span className="flex items-center gap-1">{ev.type === 'video' ? <Video className="w-3 h-3" /> : <MapPin className="w-3 h-3" />}{ev.type === 'video' ? 'Visio' : 'Physique'}</span>}
          {isNlyt && ev.role && <span className="flex items-center gap-1">{ev.role === 'organizer' ? <Users className="w-3 h-3" /> : <User className="w-3 h-3" />}{ev.role === 'organizer' ? 'Organisateur' : 'Participant'}</span>}
        </div>
      </div>
      {isNlyt && !isCancelled && <ChevronRight className="w-4 h-4 text-slate-300 flex-shrink-0 mt-1" />}
    </div>
  );
}

// ── Time grid event block (week + day views) ──
function TimeGridEvent({ ev, onEventClick, slim = false }) {
  const style = SOURCE_STYLES[ev.source] || SOURCE_STYLES.google;
  const isNlyt = ev.source === 'nlyt';
  const isCancelled = ev.status === 'cancelled';
  const d = new Date(ev.start);
  const startMin = d.getHours() * 60 + d.getMinutes();
  const topMin = startMin - START_HOUR * 60;
  const top = Math.max(0, (topMin / 60) * HOUR_HEIGHT);
  const height = Math.max(20, (Math.min(ev.duration || 60, (END_HOUR - START_HOUR) * 60 - topMin) / 60) * HOUR_HEIGHT);

  return (
    <div
      onClick={() => onEventClick(ev)}
      data-testid={`agenda-event-${ev.id}`}
      className={`absolute left-0.5 right-0.5 rounded-md px-1.5 py-1 overflow-hidden border transition-opacity
        ${isNlyt ? 'cursor-pointer hover:opacity-90' : 'cursor-default'}
        ${isCancelled ? 'opacity-40' : ''}
        ${isNlyt ? 'bg-slate-900 border-slate-800 text-white' : ev.source === 'google' ? 'bg-blue-50 border-[#4285F4]/30 text-[#1a56db]' : 'bg-sky-50 border-[#0078D4]/30 text-[#0056a3]'}
      `}
      style={{ top: `${top}px`, height: `${height}px`, zIndex: isNlyt ? 10 : 5 }}
    >
      <p className={`text-[10px] font-semibold truncate leading-tight ${slim ? '' : 'mb-0.5'}`}>{ev.title}</p>
      {!slim && height > 30 && (
        <p className={`text-[9px] truncate ${isNlyt ? 'text-white/70' : 'opacity-60'}`}>
          {formatTime(ev.start)} · {formatDuration(ev.duration)}
        </p>
      )}
    </div>
  );
}


export default function AgendaPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [events, setEvents] = useState([]);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDay, setSelectedDay] = useState(null);
  const [viewMode, setViewMode] = useState('month');

  const [importSettings, setImportSettings] = useState(null);
  const [syncing, setSyncing] = useState(false);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const loadImportSettings = useCallback(async () => {
    try { const res = await externalEventsAPI.getImportSettings(); setImportSettings(res.data); } catch { /* silent */ }
  }, []);
  const handleImportSettingChange = async (provider, enabled) => {
    await externalEventsAPI.updateImportSetting(provider, enabled);
    await loadImportSettings();
    if (enabled) await fetchEvents();
    if (!enabled) setEvents(prev => prev.filter(e => e.source === 'nlyt' || e.source !== provider));
  };
  const handleSync = async (force = false) => {
    setSyncing(true);
    try { await externalEventsAPI.sync(force); await loadImportSettings(); await fetchEvents(); } catch { /* silent */ }
    finally { setSyncing(false); }
  };

  const enabledProviders = useMemo(() => {
    const providers = importSettings?.providers || {};
    return new Set(Object.entries(providers).filter(([, cfg]) => cfg?.import_enabled).map(([key]) => key));
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
        for (const item of (timeline[bucket] || [])) {
          nlytItems.push({
            id: item.appointment_id, title: item.title || 'Sans titre',
            start: item.starts_at || item.start_datetime, duration: item.duration_minutes || 60,
            source: 'nlyt', type: item.appointment_type || 'physical', role: item.role || '',
            status: item.status || 'active', appointmentId: item.appointment_id,
          });
        }
      }
      const extItems = ((externalRes.data || {}).events || []).map(ev => ({
        id: ev.event_id || ev.external_event_id || Math.random().toString(36),
        title: ev.title || '(Sans titre)', start: ev.start_datetime || ev.start,
        duration: ev.duration_minutes || (ev.end_datetime && ev.start_datetime ? Math.max(1, Math.round((new Date(ev.end_datetime) - new Date(ev.start_datetime)) / 60000)) : 60),
        source: ev.provider || 'google', type: null, role: null, status: null, appointmentId: null,
      }));
      setEvents([...nlytItems, ...extItems]);
    } catch (err) { console.error('Agenda fetch error:', err); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadImportSettings().then(() => fetchEvents()); }, [loadImportSettings, fetchEvents]);

  const eventsByDay = useMemo(() => {
    const map = {};
    for (const ev of events) {
      if (!ev.start) continue;
      if (ev.source !== 'nlyt' && !enabledProviders.has(ev.source)) continue;
      const dk = dateKey(new Date(ev.start));
      if (!map[dk]) map[dk] = [];
      map[dk].push(ev);
    }
    for (const dk of Object.keys(map)) {
      map[dk].sort((a, b) => {
        const ta = new Date(a.start).getTime(); const tb = new Date(b.start).getTime();
        if (ta !== tb) return ta - tb;
        if (a.source === 'nlyt' && b.source !== 'nlyt') return -1;
        if (a.source !== 'nlyt' && b.source === 'nlyt') return 1;
        return 0;
      });
    }
    return map;
  }, [events, enabledProviders]);

  const today = dateKey(new Date());
  const handleEventClick = (ev) => { if (ev.source === 'nlyt' && ev.appointmentId) navigate(`/appointments/${ev.appointmentId}`); };

  // ── Navigation (view-aware) ──
  const goPrev = () => {
    setSelectedDay(null);
    if (viewMode === 'month') setCurrentDate(new Date(year, month - 1, 1));
    else if (viewMode === 'week') setCurrentDate(prev => { const d = new Date(prev); d.setDate(d.getDate() - 7); return d; });
    else setCurrentDate(prev => { const d = new Date(prev); d.setDate(d.getDate() - 1); return d; });
  };
  const goNext = () => {
    setSelectedDay(null);
    if (viewMode === 'month') setCurrentDate(new Date(year, month + 1, 1));
    else if (viewMode === 'week') setCurrentDate(prev => { const d = new Date(prev); d.setDate(d.getDate() + 7); return d; });
    else setCurrentDate(prev => { const d = new Date(prev); d.setDate(d.getDate() + 1); return d; });
  };
  const goToday = () => { setCurrentDate(new Date()); setSelectedDay(today); };

  // ── Title (view-aware) ──
  const weekDays = useMemo(() => getWeekDays(currentDate), [currentDate]);
  const navTitle = useMemo(() => {
    if (viewMode === 'month') return `${MONTHS_FR[month]} ${year}`;
    if (viewMode === 'week') {
      const mon = weekDays[0]; const sun = weekDays[6];
      if (mon.getMonth() === sun.getMonth()) return `${mon.getDate()} – ${sun.getDate()} ${MONTHS_FR[mon.getMonth()]} ${mon.getFullYear()}`;
      return `${mon.getDate()} ${MONTHS_FR[mon.getMonth()].slice(0, 3)} – ${sun.getDate()} ${MONTHS_FR[sun.getMonth()].slice(0, 3)} ${sun.getFullYear()}`;
    }
    const dayIdx = currentDate.getDay() === 0 ? 6 : currentDate.getDay() - 1;
    return `${DAYS_FR_FULL[dayIdx]} ${currentDate.getDate()} ${MONTHS_FR[currentDate.getMonth()]} ${currentDate.getFullYear()}`;
  }, [viewMode, month, year, currentDate, weekDays]);

  // ── Month grid cells ──
  const monthCells = useMemo(() => {
    const daysInMonth = getDaysInMonth(year, month);
    const firstDay = getFirstDayOfWeek(year, month);
    const prevDays = getDaysInMonth(year, month - 1);
    const cells = [];
    for (let i = firstDay - 1; i >= 0; i--) { const d = prevDays - i; cells.push({ day: d, key: dateKey(new Date(year, month - 1, d)), outside: true }); }
    for (let d = 1; d <= daysInMonth; d++) { cells.push({ day: d, key: dateKey(new Date(year, month, d)), outside: false }); }
    const remaining = 42 - cells.length;
    for (let d = 1; d <= remaining; d++) { cells.push({ day: d, key: dateKey(new Date(year, month + 1, d)), outside: true }); }
    return cells;
  }, [year, month]);

  const selectedEvents = selectedDay ? (eventsByDay[selectedDay] || []) : [];
  const dayViewEvents = viewMode === 'day' ? (eventsByDay[dateKey(currentDate)] || []) : [];

  // ── Time grid hours ──
  const hours = useMemo(() => Array.from({ length: END_HOUR - START_HOUR }, (_, i) => START_HOUR + i), []);

  return (
    <div className="min-h-screen bg-slate-50" data-testid="agenda-page">
      <AppNavbar />
      <div className="max-w-5xl mx-auto px-4 md:px-6 pt-6 pb-12">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <CalendarDays className="w-5 h-5 text-slate-400" />
            <h1 className="text-lg font-bold text-slate-900" data-testid="agenda-title">Agenda</h1>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={goToday} className="h-8 text-xs" data-testid="agenda-today-btn">Aujourd'hui</Button>
          </div>
        </div>

        {/* View mode selector + Navigation */}
        <div className="flex items-center justify-between mb-4">
          <button onClick={goPrev} className="p-2 rounded-lg hover:bg-slate-100 transition-colors" data-testid="agenda-prev"><ChevronLeft className="w-5 h-5 text-slate-600" /></button>
          <div className="flex flex-col items-center gap-2">
            <h2 className="text-base font-semibold text-slate-800" data-testid="agenda-nav-title">{navTitle}</h2>
            <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5" data-testid="agenda-view-selector">
              {[['month', 'Mois'], ['week', 'Semaine'], ['day', 'Jour']].map(([mode, label]) => (
                <button key={mode} onClick={() => setViewMode(mode)} data-testid={`agenda-view-${mode}`}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${viewMode === mode ? 'bg-slate-900 text-white' : 'text-slate-500 hover:text-slate-700'}`}
                >{label}</button>
              ))}
            </div>
          </div>
          <button onClick={goNext} className="p-2 rounded-lg hover:bg-slate-100 transition-colors" data-testid="agenda-next"><ChevronRight className="w-5 h-5 text-slate-600" /></button>
        </div>

        {/* Calendar sync toggles */}
        {importSettings && (
          <div className="mb-4">
            <CalendarSyncPanel importSettings={importSettings} onSettingChange={handleImportSettingChange} onSync={handleSync} syncing={syncing} />
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-slate-400" /></div>
        ) : (
          <>
            {/* ════════ MONTH VIEW ════════ */}
            {viewMode === 'month' && (
              <>
                <div className="bg-white border border-slate-200 rounded-xl overflow-hidden mb-6" data-testid="agenda-grid">
                  <div className="grid grid-cols-7 border-b border-slate-100">
                    {DAYS_FR.map(d => (<div key={d} className="py-2.5 text-center text-xs font-semibold text-slate-500 uppercase tracking-wider">{d}</div>))}
                  </div>
                  <div className="grid grid-cols-7">
                    {monthCells.map((cell, i) => {
                      const dayEvents = eventsByDay[cell.key] || [];
                      const isToday = cell.key === today;
                      const isSelected = cell.key === selectedDay;
                      const nlytCount = dayEvents.filter(e => e.source === 'nlyt').length;
                      const extCount = dayEvents.filter(e => e.source !== 'nlyt').length;
                      return (
                        <button key={i} onClick={() => setSelectedDay(isSelected ? null : cell.key)} data-testid={`agenda-day-${cell.key}`}
                          className={`relative min-h-[72px] md:min-h-[80px] p-1.5 border-b border-r border-slate-50 text-left transition-colors ${cell.outside ? 'bg-slate-25 text-slate-300' : 'hover:bg-slate-50'} ${isSelected ? 'bg-slate-100 ring-1 ring-inset ring-slate-300' : ''}`}
                        >
                          <span className={`inline-flex items-center justify-center w-6 h-6 text-xs font-medium rounded-full ${isToday ? 'bg-slate-900 text-white' : cell.outside ? 'text-slate-300' : 'text-slate-700'}`}>{cell.day}</span>
                          {dayEvents.length > 0 && (
                            <div className="flex items-center gap-0.5 mt-1 flex-wrap">
                              {nlytCount > 0 && <div className="flex items-center gap-px">{Array.from({ length: Math.min(nlytCount, 3) }).map((_, j) => <span key={`n${j}`} className="w-1.5 h-1.5 rounded-full bg-slate-900" />)}{nlytCount > 3 && <span className="text-[9px] text-slate-500 ml-0.5">+{nlytCount - 3}</span>}</div>}
                              {extCount > 0 && <div className="flex items-center gap-px ml-0.5">{Array.from({ length: Math.min(extCount, 2) }).map((_, j) => <span key={`e${j}`} className="w-1.5 h-1.5 rounded-full border border-blue-400 bg-transparent" />)}{extCount > 2 && <span className="text-[9px] text-blue-400 ml-0.5">+{extCount - 2}</span>}</div>}
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
                {selectedDay && (
                  <div className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid="agenda-day-detail">
                    <div className="px-4 py-3 border-b border-slate-100 bg-slate-50">
                      <h3 className="text-sm font-semibold text-slate-800" data-testid="agenda-detail-date">
                        {new Date(selectedDay + 'T00:00:00').toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
                      </h3>
                    </div>
                    {selectedEvents.length === 0 ? (
                      <div className="px-4 py-8 text-center"><p className="text-sm text-slate-400">Aucun événement ce jour</p></div>
                    ) : (
                      <div className="divide-y divide-slate-50">{selectedEvents.map(ev => <EventRow key={ev.id} ev={ev} onEventClick={handleEventClick} />)}</div>
                    )}
                  </div>
                )}
              </>
            )}

            {/* ════════ WEEK VIEW ════════ */}
            {viewMode === 'week' && (
              <div className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid="agenda-week-grid">
                {/* Day headers */}
                <div className="grid grid-cols-[56px_repeat(7,1fr)] border-b border-slate-100">
                  <div className="border-r border-slate-100" />
                  {weekDays.map(d => {
                    const dk = dateKey(d);
                    const isToday = dk === today;
                    const dayIdx = d.getDay() === 0 ? 6 : d.getDay() - 1;
                    return (
                      <div key={dk} className={`py-2.5 text-center border-r border-slate-50 ${isToday ? 'bg-slate-50' : ''}`}>
                        <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">{DAYS_FR[dayIdx]}</span>
                        <span className={`block text-sm font-bold mt-0.5 ${isToday ? 'text-white bg-slate-900 w-7 h-7 rounded-full inline-flex items-center justify-center mx-auto' : 'text-slate-700'}`}>{d.getDate()}</span>
                      </div>
                    );
                  })}
                </div>
                {/* Time grid */}
                <div className="grid grid-cols-[56px_repeat(7,1fr)] overflow-y-auto max-h-[600px]">
                  {/* Hour labels */}
                  <div className="border-r border-slate-100">
                    {hours.map(h => (
                      <div key={h} style={{ height: HOUR_HEIGHT }} className="flex items-start justify-end pr-2 pt-0 border-b border-slate-50">
                        <span className="text-[10px] text-slate-400 font-mono -mt-1.5">{String(h).padStart(2, '0')}:00</span>
                      </div>
                    ))}
                  </div>
                  {/* Day columns */}
                  {weekDays.map(d => {
                    const dk = dateKey(d);
                    const dayEvs = eventsByDay[dk] || [];
                    const isToday = dk === today;
                    return (
                      <div key={dk} className={`relative border-r border-slate-50 ${isToday ? 'bg-slate-50/50' : ''}`}
                        onClick={() => { setViewMode('day'); setCurrentDate(new Date(d)); }}
                        style={{ cursor: 'pointer' }}
                      >
                        {hours.map(h => <div key={h} style={{ height: HOUR_HEIGHT }} className="border-b border-slate-50" />)}
                        {dayEvs.map(ev => <TimeGridEvent key={ev.id} ev={ev} onEventClick={handleEventClick} slim />)}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ════════ DAY VIEW ════════ */}
            {viewMode === 'day' && (
              <div className="grid grid-cols-1 md:grid-cols-[1fr_320px] gap-4">
                {/* Time grid */}
                <div className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid="agenda-day-grid">
                  <div className="grid grid-cols-[56px_1fr] overflow-y-auto max-h-[600px]">
                    <div className="border-r border-slate-100">
                      {hours.map(h => (
                        <div key={h} style={{ height: HOUR_HEIGHT }} className="flex items-start justify-end pr-2 pt-0 border-b border-slate-50">
                          <span className="text-[10px] text-slate-400 font-mono -mt-1.5">{String(h).padStart(2, '0')}:00</span>
                        </div>
                      ))}
                    </div>
                    <div className="relative">
                      {hours.map(h => <div key={h} style={{ height: HOUR_HEIGHT }} className="border-b border-slate-50" />)}
                      {dayViewEvents.map(ev => <TimeGridEvent key={ev.id} ev={ev} onEventClick={handleEventClick} />)}
                    </div>
                  </div>
                </div>
                {/* Event list sidebar */}
                <div className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid="agenda-day-list">
                  <div className="px-4 py-3 border-b border-slate-100 bg-slate-50">
                    <h3 className="text-sm font-semibold text-slate-800">
                      {dayViewEvents.length} événement{dayViewEvents.length !== 1 ? 's' : ''}
                    </h3>
                  </div>
                  {dayViewEvents.length === 0 ? (
                    <div className="px-4 py-8 text-center"><p className="text-sm text-slate-400">Aucun événement ce jour</p></div>
                  ) : (
                    <div className="divide-y divide-slate-50">{dayViewEvents.map(ev => <EventRow key={ev.id} ev={ev} onEventClick={handleEventClick} />)}</div>
                  )}
                </div>
              </div>
            )}

            {/* Legend */}
            <div className="flex items-center gap-4 mt-4 px-1">
              <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-slate-900" /><span className="text-[11px] text-slate-500">NLYT</span></div>
              <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full border border-blue-400 bg-transparent" /><span className="text-[11px] text-slate-500">Google / Microsoft</span></div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
