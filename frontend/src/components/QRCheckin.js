import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Camera, X, Keyboard } from 'lucide-react';
import { safeFetchJson } from '../utils/safeFetchJson';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function QRCheckin({ appointmentId, invitationToken, onSuccess, onClose }) {
  const [mode, setMode] = useState('choice'); // choice, camera, manual
  const [manualCode, setManualCode] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [cameraError, setCameraError] = useState(null);
  const scannerRef = useRef(null);
  const scannerInstanceRef = useRef(null);

  const stopCamera = useCallback(() => {
    if (scannerInstanceRef.current) {
      try {
        scannerInstanceRef.current.stop().catch(() => {});
      } catch (e) { /* ignore */ }
      scannerInstanceRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => stopCamera();
  }, [stopCamera]);

  const startCamera = async () => {
    setMode('camera');
    setCameraError(null);
    setError(null);

    try {
      const { Html5Qrcode } = await import('html5-qrcode');
      const scanner = new Html5Qrcode('qr-reader');
      scannerInstanceRef.current = scanner;

      await scanner.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 250, height: 250 } },
        (decodedText) => {
          stopCamera();
          handleVerify(decodedText);
        },
        () => {} // ignore scan failures
      );
    } catch (err) {
      setCameraError("Impossible d'accéder à la caméra. Utilisez la saisie manuelle.");
      setMode('manual');
    }
  };

  const handleVerify = async (code) => {
    if (!code.trim()) return;
    setSubmitting(true);
    setError(null);

    try {
      const { ok, data } = await safeFetchJson(`${API_URL}/api/checkin/qr/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          qr_code: code.trim(),
          invitation_token: invitationToken,
        }),
      });

      if (!ok) {
        setError(data.detail || 'Erreur de vérification');
        if (mode === 'camera') setMode('manual');
      } else {
        onSuccess && onSuccess(data);
      }
    } catch (err) {
      setError('Erreur réseau');
      if (mode === 'camera') setMode('manual');
    } finally {
      setSubmitting(false);
    }
  };

  const handleManualSubmit = (e) => {
    e.preventDefault();
    stopCamera();
    handleVerify(manualCode);
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" data-testid="qr-checkin-modal">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <h3 className="text-lg font-semibold text-slate-800">Scanner un QR code</h3>
          <button
            onClick={() => { stopCamera(); onClose && onClose(); }}
            className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600"
            data-testid="qr-modal-close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700" data-testid="qr-error">
              {error}
            </div>
          )}

          {mode === 'choice' && (
            <div className="space-y-3" data-testid="qr-choice">
              <button
                onClick={startCamera}
                className="w-full flex items-center gap-3 p-4 rounded-xl border-2 border-slate-200 hover:border-slate-400 hover:bg-slate-50 transition-colors"
                data-testid="qr-camera-btn"
              >
                <div className="p-2 bg-blue-100 rounded-lg">
                  <Camera className="w-5 h-5 text-blue-700" />
                </div>
                <div className="text-left">
                  <p className="font-medium text-slate-800">Scanner avec la caméra</p>
                  <p className="text-xs text-slate-500">Pointez vers le QR code affiché</p>
                </div>
              </button>

              <button
                onClick={() => { setMode('manual'); setError(null); }}
                className="w-full flex items-center gap-3 p-4 rounded-xl border-2 border-slate-200 hover:border-slate-400 hover:bg-slate-50 transition-colors"
                data-testid="qr-manual-btn"
              >
                <div className="p-2 bg-slate-100 rounded-lg">
                  <Keyboard className="w-5 h-5 text-slate-700" />
                </div>
                <div className="text-left">
                  <p className="font-medium text-slate-800">Saisie manuelle</p>
                  <p className="text-xs text-slate-500">Entrez le code affiché sous le QR</p>
                </div>
              </button>
            </div>
          )}

          {mode === 'camera' && (
            <div>
              <div id="qr-reader" ref={scannerRef} className="rounded-lg overflow-hidden mb-4" data-testid="qr-camera-view" />
              {cameraError && (
                <p className="text-sm text-red-600 mb-3">{cameraError}</p>
              )}
              <button
                onClick={() => { stopCamera(); setMode('manual'); }}
                className="w-full text-center text-sm text-slate-500 hover:text-slate-700 py-2"
                data-testid="switch-to-manual"
              >
                Saisir le code manuellement
              </button>
            </div>
          )}

          {mode === 'manual' && (
            <form onSubmit={handleManualSubmit} data-testid="qr-manual-form">
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Code QR (affiché sous l'image)
              </label>
              <input
                type="text"
                value={manualCode}
                onChange={(e) => setManualCode(e.target.value)}
                placeholder="NLYT:abc123..."
                className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm font-mono"
                autoFocus
                data-testid="qr-manual-input"
              />
              <div className="flex gap-3 mt-4">
                <button
                  type="button"
                  onClick={() => setMode('choice')}
                  className="flex-1 px-4 py-2.5 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 text-sm font-medium"
                >
                  Retour
                </button>
                <button
                  type="submit"
                  disabled={!manualCode.trim() || submitting}
                  className="flex-1 px-4 py-2.5 bg-slate-800 text-white rounded-lg hover:bg-slate-700 text-sm font-medium disabled:opacity-50"
                  data-testid="qr-manual-submit"
                >
                  {submitting ? 'Vérification...' : 'Vérifier'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
