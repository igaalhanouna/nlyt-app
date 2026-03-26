import React from 'react';
import { ScanLine, QrCode, MapPinCheck, Timer, Navigation, Monitor, Check, X, UserCog, AlertTriangle, ShieldCheck } from 'lucide-react';
import { formatEvidenceDateFr } from '../../utils/dateFormat';

/**
 * EvidenceDashboard — Affiche "Check-ins & Preuves" dans la carte rendez-vous.
 *
 * !! ZONE PROTÉGÉE — Chaîne de preuves de présence !!
 * Voir /app/backend/docs/EVIDENCE_CHAIN.md pour la documentation complète.
 * Tests de non-régression : /app/backend/tests/test_evidence_chain.py
 * Toute modification doit être signalée dans le summary de livraison.
 *
 * INVARIANTS :
 * - Mapping : evidenceData.participants[].evidence (PAS evidenceData.evidence)
 * - Filtre : statut accepted / accepted_pending_guarantee / accepted_guaranteed
 * - L'organisateur N'EST PAS filtré (pas de !p.is_organizer)
 * - 1 bloc par participant, même si 0 preuve
 * - Supporte physique (GPS, QR, manual) ET visio (video_conference)
 */

const PROVIDER_INFO = {
  zoom: { label: 'Zoom', color: 'text-blue-600', bg: 'bg-blue-50' },
  teams: { label: 'Teams', color: 'text-purple-600', bg: 'bg-purple-50' },
  meet: { label: 'Meet', color: 'text-emerald-600', bg: 'bg-emerald-50' },
};

const OUTCOME_BADGES = {
  joined_on_time: { bg: 'bg-emerald-100', text: 'text-emerald-800', label: 'À l\'heure' },
  joined_late: { bg: 'bg-amber-100', text: 'text-amber-800', label: 'En retard' },
  no_join_detected: { bg: 'bg-red-100', text: 'text-red-800', label: 'Absent' },
  manual_review: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'Revue manuelle' },
};

function getSourceColor(source) {
  switch (source) {
    case 'qr': return 'border-indigo-400';
    case 'gps': return 'border-emerald-400';
    case 'manual_checkin': return 'border-amber-400';
    case 'video_conference': return 'border-violet-400';
    default: return 'border-slate-300';
  }
}

function getSourceIcon(source, provider) {
  switch (source) {
    case 'qr': return <QrCode className="w-3.5 h-3.5 text-indigo-500" />;
    case 'gps': return <Navigation className="w-3.5 h-3.5 text-emerald-500" />;
    case 'manual_checkin': return <MapPinCheck className="w-3.5 h-3.5 text-amber-500" />;
    case 'video_conference': return <Monitor className="w-3.5 h-3.5 text-violet-500" />;
    default: return <ScanLine className="w-3.5 h-3.5 text-slate-400" />;
  }
}

function getSourceLabel(source, facts) {
  if (source === 'video_conference') {
    const p = PROVIDER_INFO[(facts?.provider || '').toLowerCase()];
    return p ? `Visio ${p.label}` : 'Visio';
  }
  switch (source) {
    case 'qr': return 'QR Code';
    case 'gps': return 'GPS';
    case 'manual_checkin': return 'Check-in manuel';
    default: return source;
  }
}

function getConfidenceColor(score) {
  switch (score) {
    case 'high': return 'text-emerald-700 bg-emerald-50';
    case 'medium': return 'text-amber-700 bg-amber-50';
    case 'low': return 'text-red-700 bg-red-50';
    default: return 'text-slate-500 bg-slate-50';
  }
}

function PhysicalEvidenceDetails({ facts }) {
  if (!facts) return null;
  return (
    <div className="text-xs text-slate-500 space-y-0.5 ml-5">
      {facts.latitude && (
        <div className="flex items-center gap-1">
          <Navigation className="w-3 h-3" />
          {Number(facts.latitude).toFixed(5)}, {Number(facts.longitude).toFixed(5)}
        </div>
      )}
      {facts.distance_km != null && (
        <div className="flex items-center gap-1 text-slate-400">
          Distance : {facts.distance_km < 1
            ? `${Math.round(facts.distance_km * 1000)} m`
            : `${facts.distance_km.toFixed(2)} km`
          }
        </div>
      )}
      {facts.temporal_detail && (
        <div className="flex items-center gap-1">
          <Timer className="w-3 h-3" />
          {facts.temporal_detail}
        </div>
      )}
      {facts.address_label && (
        <div className="text-slate-400 truncate max-w-sm">{facts.address_label}</div>
      )}
    </div>
  );
}

function VideoEvidenceDetails({ facts }) {
  if (!facts) return null;
  const providerInfo = PROVIDER_INFO[(facts.provider || '').toLowerCase()];
  const outcomeBadge = OUTCOME_BADGES[facts.video_attendance_outcome] || OUTCOME_BADGES.manual_review;

  return (
    <div className="text-xs text-slate-500 space-y-1 ml-5">
      <div className="flex items-center gap-2 flex-wrap">
        {providerInfo && (
          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full ${providerInfo.bg} ${providerInfo.color} font-medium`}>
            <Monitor className="w-3 h-3" />
            {providerInfo.label}
          </span>
        )}
        <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full ${outcomeBadge.bg} ${outcomeBadge.text} font-medium`}>
          {outcomeBadge.label}
        </span>
        {facts.provider_role && (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-600 font-medium">
            <ShieldCheck className="w-3 h-3" />
            {facts.provider_role === 'host' || facts.provider_role === 'organizer'
              ? 'Organisateur visio' : facts.provider_role === 'presenter' ? 'Présentateur' : 'Participant'}
          </span>
        )}
        {facts.provider_evidence_ceiling === 'assisted' && (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-amber-700 font-medium">
            <AlertTriangle className="w-3 h-3" />
            Preuve assistée
          </span>
        )}
      </div>
      <div className="flex items-center gap-4">
        {facts.joined_at && (
          <span className="flex items-center gap-1 text-emerald-700">
            <Check className="w-3 h-3" />
            Connecté : {formatEvidenceDateFr(facts.joined_at)}
          </span>
        )}
        {facts.left_at && (
          <span className="flex items-center gap-1 text-slate-400">
            <X className="w-3 h-3" />
            Déconnecté : {formatEvidenceDateFr(facts.left_at)}
          </span>
        )}
      </div>
      {facts.duration_seconds != null && (
        <div className="flex items-center gap-1">
          <Timer className="w-3 h-3" />
          Durée : {Math.round(facts.duration_seconds / 60)} min
        </div>
      )}
      {facts.temporal_detail && (
        <div className={`flex items-center gap-1 ${
          facts.temporal_consistency === 'valid' ? 'text-emerald-600' :
          facts.temporal_consistency === 'valid_late' ? 'text-amber-600' : 'text-slate-500'
        }`}>
          <Timer className="w-3 h-3" />
          {facts.temporal_detail}
        </div>
      )}
      {facts.identity_match_detail && (
        <div className="flex items-center gap-1 text-slate-400">
          <UserCog className="w-3 h-3" />
          {facts.identity_match_detail}
        </div>
      )}
    </div>
  );
}

export default function EvidenceDashboard({ participants, evidenceData, appointment }) {
  // INVARIANT: Mapper via evidenceData.participants (PAS evidenceData.evidence)
  // Voir EVIDENCE_CHAIN.md — ne pas modifier sans signaler
  const getParticipantEvidence = (participantId) => {
    if (!evidenceData?.participants) return [];
    const pData = evidenceData.participants.find(p => p.participant_id === participantId);
    return pData?.evidence || [];
  };

  const isVideo = appointment?.appointment_type === 'video';

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-6 mt-6" data-testid="evidence-dashboard">
      <div className="flex items-center gap-2 mb-4">
        {isVideo ? <Monitor className="w-5 h-5 text-violet-700" /> : <ScanLine className="w-5 h-5 text-slate-700" />}
        <h2 className="text-base font-semibold text-slate-900">
          {isVideo ? 'Preuves de présence par participant' : 'Check-ins & Preuves'}
        </h2>
      </div>

      <div className="space-y-3">
        {/* INVARIANT: Inclure TOUS les statuts acceptés, y compris organisateur (pas de !p.is_organizer) */}
        {participants.filter(p => ['accepted', 'accepted_pending_guarantee', 'accepted_guaranteed'].includes(p.status)).map(p => {
          const evidence = getParticipantEvidence(p.participant_id);
          return (
            <div key={p.participant_id} className="border border-slate-200 rounded-xl overflow-hidden" data-testid={`evidence-participant-${p.participant_id}`}>
              <div className="flex items-center justify-between px-4 py-3 bg-slate-50">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm text-slate-900">{p.first_name} {p.last_name}</span>
                  {p.is_organizer && (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-slate-200 text-slate-600 font-medium">Organisateur</span>
                  )}
                  <span className="text-xs text-slate-400">{p.email}</span>
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
                        {getSourceIcon(e.source, e.derived_facts?.provider)}
                        <span className="text-xs font-semibold text-slate-700">{getSourceLabel(e.source, e.derived_facts)}</span>
                        <span className={`text-xs px-1.5 py-0.5 rounded ${getConfidenceColor(e.confidence_score)}`}>
                          {e.confidence_score}
                        </span>
                        <span className="text-xs text-slate-400 ml-auto">
                          {formatEvidenceDateFr(e.source_timestamp)}
                        </span>
                      </div>
                      {e.source === 'video_conference' ? (
                        <VideoEvidenceDetails facts={e.derived_facts} />
                      ) : (
                        <PhysicalEvidenceDetails facts={e.derived_facts} />
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
