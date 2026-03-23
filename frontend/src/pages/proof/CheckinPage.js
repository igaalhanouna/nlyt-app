import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { Video, Clock, CheckCircle, Loader2, LogOut, Wifi, WifiOff, Shield, User } from 'lucide-react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;
const HEARTBEAT_INTERVAL = 30000; // 30 seconds

export default function CheckinPage() {
  const { appointmentId } = useParams();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [sessionActive, setSessionActive] = useState(false);
  const [checkingIn, setCheckingIn] = useState(false);
  const [checkingOut, setCheckingOut] = useState(false);
  const [result, setResult] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [heartbeatOk, setHeartbeatOk] = useState(true);
  const [heartbeatCount, setHeartbeatCount] = useState(0);
  const heartbeatRef = useRef(null);
  const timerRef = useRef(null);
  const checkinTimeRef = useRef(null);

  // Load appointment info
  useEffect(() => {
    if (!token) {
      setError("Lien de check-in invalide. Vérifiez le lien reçu par email.");
      setLoading(false);
      return;
    }
    axios.get(`${API}/api/proof/${appointmentId}/info?token=${token}`)
      .then(res => {
        setInfo(res.data);
        if (res.data.active_session) {
          setSessionId(res.data.active_session.session_id);
          setSessionActive(true);
          checkinTimeRef.current = new Date(res.data.active_session.checked_in_at);
          setHeartbeatCount(res.data.active_session.heartbeat_count || 0);
        }
      })
      .catch(err => setError(err.response?.data?.detail || "Impossible de charger les informations du rendez-vous."))
      .finally(() => setLoading(false));
  }, [appointmentId, token]);

  // Heartbeat loop
  const sendHeartbeat = useCallback(async () => {
    if (!sessionId) return;
    try {
      const res = await axios.post(`${API}/api/proof/${appointmentId}/heartbeat`, { session_id: sessionId });
      setHeartbeatOk(true);
      setHeartbeatCount(res.data.heartbeat_count || 0);
    } catch {
      setHeartbeatOk(false);
    }
  }, [sessionId, appointmentId]);

  useEffect(() => {
    if (sessionActive && sessionId) {
      heartbeatRef.current = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);
      timerRef.current = setInterval(() => {
        if (checkinTimeRef.current) {
          setElapsed(Math.floor((Date.now() - checkinTimeRef.current.getTime()) / 1000));
        }
      }, 1000);
    }
    return () => {
      if (heartbeatRef.current) clearInterval(heartbeatRef.current);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [sessionActive, sessionId, sendHeartbeat]);

  // Check-in action
  const handleCheckin = async () => {
    setCheckingIn(true);
    try {
      const res = await axios.post(`${API}/api/proof/${appointmentId}/checkin`, { token });
      setSessionId(res.data.session_id);
      setSessionActive(true);
      checkinTimeRef.current = new Date(res.data.checked_in_at || Date.now());

      // Open visio in new tab
      const joinUrl = res.data.meeting_join_url || info?.appointment?.meeting_join_url;
      if (joinUrl) {
        window.open(joinUrl, '_blank');
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Erreur lors du check-in.");
    } finally {
      setCheckingIn(false);
    }
  };

  // Check-out action
  const handleCheckout = async () => {
    setCheckingOut(true);
    try {
      const res = await axios.post(`${API}/api/proof/${appointmentId}/checkout`, { session_id: sessionId });
      setSessionActive(false);
      setResult(res.data);
      if (heartbeatRef.current) clearInterval(heartbeatRef.current);
      if (timerRef.current) clearInterval(timerRef.current);
    } catch (err) {
      setError(err.response?.data?.detail || "Erreur lors de la fin de session.");
    } finally {
      setCheckingOut(false);
    }
  };

  // Elapsed time formatter
  const formatElapsed = (s) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (h > 0) return `${h}h ${m.toString().padStart(2, '0')}m`;
    return `${m}m ${sec.toString().padStart(2, '0')}s`;
  };

  const formatDate = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  // ── Loading ────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
      </div>
    );
  }

  // ── Error ──────────────────────────────────────────
  if (error && !info) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-xl border border-red-200 p-8 text-center">
          <Shield className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h1 className="text-lg font-bold text-slate-900 mb-2">Lien invalide</h1>
          <p className="text-sm text-slate-600">{error}</p>
        </div>
      </div>
    );
  }

  const apt = info?.appointment;
  const participant = info?.participant;

  // ── Result (post checkout) ─────────────────────────
  if (result) {
    const levelColors = { strong: 'text-emerald-700 bg-emerald-50 border-emerald-200', medium: 'text-amber-700 bg-amber-50 border-amber-200', weak: 'text-red-700 bg-red-50 border-red-200' };
    const levelLabels = { strong: 'Preuve forte', medium: 'Preuve moyenne', weak: 'Preuve faible' };
    const statusLabels = { present: 'Présent', partial: 'Présence partielle', absent: 'Absent' };

    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="bg-emerald-600 px-6 py-5 text-white text-center">
            <CheckCircle className="w-10 h-10 mx-auto mb-2" />
            <h1 className="text-lg font-bold">Session terminée</h1>
          </div>
          <div className="p-6 space-y-4">
            <div className="text-center">
              <p className="text-3xl font-bold text-slate-900">{result.score}<span className="text-lg text-slate-400">/100</span></p>
              <div className={`inline-flex items-center px-3 py-1 rounded-full border text-sm font-medium mt-2 ${levelColors[result.proof_level] || ''}`}>
                {levelLabels[result.proof_level] || result.proof_level}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="bg-slate-50 rounded-lg p-3">
                <p className="text-slate-500 text-xs">Durée active</p>
                <p className="font-semibold text-slate-900">{formatElapsed(result.active_duration_seconds || 0)}</p>
              </div>
              <div className="bg-slate-50 rounded-lg p-3">
                <p className="text-slate-500 text-xs">Statut suggéré</p>
                <p className="font-semibold text-slate-900">{statusLabels[result.suggested_status] || result.suggested_status}</p>
              </div>
            </div>
            <div className="text-center pt-2">
              <p className="text-xs text-slate-400">L'organisateur validera le statut final.</p>
              <p className="text-xs text-slate-400 mt-1">Vous pouvez fermer cette page.</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Active session ─────────────────────────────────
  if (sessionActive) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="bg-blue-600 px-6 py-5 text-white text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              {heartbeatOk ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4 text-red-300" />}
              <span className="text-xs font-medium uppercase tracking-wider">{heartbeatOk ? 'Session active' : 'Connexion perdue'}</span>
            </div>
            <p className="text-4xl font-mono font-bold mt-2" data-testid="session-timer">{formatElapsed(elapsed)}</p>
          </div>

          <div className="p-6 space-y-4">
            <div className="bg-slate-50 rounded-lg p-4">
              <p className="text-sm font-semibold text-slate-900">{apt?.title}</p>
              <p className="text-xs text-slate-500 mt-1">{participant?.first_name} {participant?.last_name}</p>
            </div>

            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500">Heartbeats enregistrés</span>
              <span className="font-mono font-semibold text-slate-900" data-testid="heartbeat-count">{heartbeatCount}</span>
            </div>

            <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
              <p className="text-xs text-blue-700">
                Gardez cet onglet ouvert pendant la réunion. Votre présence est enregistrée automatiquement toutes les 30 secondes.
              </p>
            </div>

            {apt?.meeting_join_url && (
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => window.open(apt.meeting_join_url, '_blank')}
                data-testid="reopen-visio-btn"
              >
                <Video className="w-4 h-4 mr-2" />
                Rouvrir la réunion
              </Button>
            )}

            <Button
              className="w-full bg-red-600 hover:bg-red-700 text-white"
              onClick={handleCheckout}
              disabled={checkingOut}
              data-testid="checkout-btn"
            >
              {checkingOut ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <LogOut className="w-4 h-4 mr-2" />}
              Terminer ma session
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // ── Check-in (initial state) ───────────────────────
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="bg-slate-900 px-6 py-5 text-white text-center">
          <Shield className="w-8 h-8 mx-auto mb-2 text-blue-400" />
          <h1 className="text-lg font-bold">Preuve de présence</h1>
          <p className="text-xs text-slate-300 mt-1">NLYT — Système de vérification</p>
        </div>

        <div className="p-6 space-y-4">
          {/* Appointment info */}
          <div className="bg-slate-50 rounded-lg p-4 space-y-2">
            <p className="text-sm font-semibold text-slate-900" data-testid="checkin-appointment-title">{apt?.title}</p>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Clock className="w-3.5 h-3.5" />
              <span>{formatDate(apt?.start_datetime)}</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Clock className="w-3.5 h-3.5" />
              <span>Durée : {apt?.duration_minutes} min</span>
            </div>
            {apt?.meeting_provider && (
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Video className="w-3.5 h-3.5" />
                <span>Via {apt.meeting_provider === 'zoom' ? 'Zoom' : apt.meeting_provider === 'teams' ? 'Microsoft Teams' : apt.meeting_provider === 'meet' ? 'Google Meet' : apt.meeting_provider}</span>
              </div>
            )}
          </div>

          {/* Participant info */}
          <div className="flex items-center gap-3 p-3 bg-blue-50 border border-blue-100 rounded-lg">
            <User className="w-5 h-5 text-blue-600 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-blue-900" data-testid="checkin-participant-name">{participant?.first_name} {participant?.last_name}</p>
              <p className="text-xs text-blue-600">{participant?.email}</p>
            </div>
          </div>

          {/* How it works */}
          <div className="border border-slate-200 rounded-lg p-3 space-y-2">
            <p className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Comment ça marche</p>
            <ol className="text-xs text-slate-600 space-y-1 list-decimal list-inside">
              <li>Cliquez "Je rejoins la réunion"</li>
              <li>La visio s'ouvre dans un nouvel onglet</li>
              <li>Gardez <strong>cet onglet</strong> ouvert pendant la réunion</li>
              <li>Cliquez "Terminer" quand la réunion est finie</li>
            </ol>
          </div>

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
          )}

          {/* Check-in button */}
          <Button
            className="w-full h-12 text-base bg-blue-600 hover:bg-blue-700 text-white font-semibold"
            onClick={handleCheckin}
            disabled={checkingIn}
            data-testid="checkin-btn"
          >
            {checkingIn ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <Video className="w-5 h-5 mr-2" />}
            Je rejoins la réunion
          </Button>
        </div>
      </div>
    </div>
  );
}
