import React from 'react';
import { ScanLine, QrCode, MapPinCheck, Timer, Navigation } from 'lucide-react';
import { formatEvidenceDateFr } from '../../utils/dateFormat';

export default function EvidenceDashboard({ participants, evidenceData, appointment }) {
  const getSourceColor = (source) => {
    switch (source) {
      case 'qr': return 'border-indigo-400';
      case 'gps': return 'border-emerald-400';
      case 'manual_checkin': return 'border-amber-400';
      default: return 'border-slate-300';
    }
  };

  const getSourceIcon = (source) => {
    switch (source) {
      case 'qr': return <QrCode className="w-3.5 h-3.5 text-indigo-500" />;
      case 'gps': return <Navigation className="w-3.5 h-3.5 text-emerald-500" />;
      case 'manual_checkin': return <MapPinCheck className="w-3.5 h-3.5 text-amber-500" />;
      default: return <ScanLine className="w-3.5 h-3.5 text-slate-400" />;
    }
  };

  const getSourceLabel = (source) => {
    switch (source) {
      case 'qr': return 'QR Code';
      case 'gps': return 'GPS';
      case 'manual_checkin': return 'Check-in manuel';
      default: return source;
    }
  };

  const getConfidenceColor = (score) => {
    switch (score) {
      case 'high': return 'text-emerald-700 bg-emerald-50';
      case 'medium': return 'text-amber-700 bg-amber-50';
      case 'low': return 'text-red-700 bg-red-50';
      default: return 'text-slate-500 bg-slate-50';
    }
  };

  const getParticipantEvidence = (participantId) => {
    if (!evidenceData?.evidence) return [];
    return evidenceData.evidence.filter(e => e.participant_id === participantId);
  };

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-6 mt-6" data-testid="evidence-dashboard">
      <div className="flex items-center gap-2 mb-4">
        <ScanLine className="w-5 h-5 text-slate-700" />
        <h2 className="text-lg font-semibold text-slate-900">Check-ins & Preuves</h2>
      </div>

      <div className="space-y-3">
        {participants.filter(p => !p.is_organizer).map(p => {
          const evidence = getParticipantEvidence(p.participant_id);
          return (
            <div key={p.participant_id} className="border border-slate-200 rounded-xl overflow-hidden" data-testid={`evidence-participant-${p.participant_id}`}>
              <div className="flex items-center justify-between px-4 py-3 bg-slate-50">
                <div>
                  <span className="font-medium text-sm text-slate-900">{p.first_name} {p.last_name}</span>
                  <span className="text-xs text-slate-400 ml-2">{p.email}</span>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${evidence.length > 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                  {evidence.length > 0 ? `${evidence.length} preuve(s)` : 'Aucune preuve'}
                </span>
              </div>
              {evidence.length > 0 && (
                <div className="px-4 py-3 space-y-2">
                  {evidence.map(e => (
                    <div key={e.evidence_id} className={`pl-4 border-l-[3px] ${getSourceColor(e.source)}`} data-testid={`evidence-item-${e.evidence_id}`}>
                      <div className="flex items-center gap-2 mb-1">
                        {getSourceIcon(e.source)}
                        <span className="text-xs font-semibold text-slate-700">{getSourceLabel(e.source)}</span>
                        <span className={`text-xs px-1.5 py-0.5 rounded ${getConfidenceColor(e.confidence_score)}`}>
                          {e.confidence_score}
                        </span>
                        <span className="text-xs text-slate-400 ml-auto">
                          {formatEvidenceDateFr(e.source_timestamp)}
                        </span>
                      </div>
                      {e.derived_facts && (
                        <div className="text-xs text-slate-500 space-y-0.5 ml-5">
                          {e.derived_facts.temporal_detail && (
                            <div className="flex items-center gap-1">
                              <Timer className="w-3 h-3" />
                              {e.derived_facts.temporal_detail}
                            </div>
                          )}
                          {e.derived_facts.geographic_detail && (
                            <div className="flex items-center gap-1">
                              <Navigation className="w-3 h-3" />
                              {e.derived_facts.geographic_detail}
                            </div>
                          )}
                          {e.derived_facts.address_label && (
                            <div className="text-slate-400 truncate max-w-sm">{e.derived_facts.address_label}</div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
