import React from 'react';
import { X } from 'lucide-react';

export default function QRDisplayModal({ qrData, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" data-testid="qr-display-modal">
      <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <h3 className="text-lg font-semibold text-slate-800">Votre QR code</h3>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400" data-testid="qr-display-close">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-6 text-center">
          <div className="bg-white p-3 rounded-xl border border-slate-200 inline-block mb-4">
            <img src={`data:image/png;base64,${qrData.qr_image_base64}`} alt="QR Code" className="w-52 h-52" data-testid="qr-display-image" />
          </div>
          <p className="text-xs text-slate-500 mb-2">
            Montrez ce QR à un autre participant pour qu'il le scanne
          </p>
          <p className="text-xs font-mono bg-slate-50 px-3 py-2 rounded-lg text-slate-600 break-all select-all" data-testid="qr-display-token">
            {qrData.qr_token}
          </p>
          <p className="text-xs text-slate-400 mt-3">
            Renouvellement automatique toutes les {qrData.rotation_seconds}s
          </p>
        </div>
      </div>
    </div>
  );
}
