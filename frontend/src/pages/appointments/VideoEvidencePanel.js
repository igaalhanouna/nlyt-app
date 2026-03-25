import React from 'react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Monitor, Loader2, RefreshCw, Upload, PlayCircle, FileJson, FileUp, AlertTriangle, Check, X, Timer, UserCog } from 'lucide-react';
import { formatEvidenceDateFr } from '../../utils/dateFormat';

const getProviderIcon = (provider) => {
  const icons = {
    zoom: { label: 'Zoom', color: 'text-blue-600', bg: 'bg-blue-50' },
    teams: { label: 'Teams', color: 'text-purple-600', bg: 'bg-purple-50' },
    meet: { label: 'Google Meet', color: 'text-emerald-600', bg: 'bg-emerald-50' },
  };
  return icons[(provider || '').toLowerCase()] || { label: provider || 'Visio', color: 'text-slate-600', bg: 'bg-slate-50' };
};

const getVideoOutcomeBadge = (outcome) => {
  const badges = {
    joined_on_time: { bg: 'bg-emerald-100', text: 'text-emerald-800', label: 'Connecté à l\'heure' },
    joined_late: { bg: 'bg-amber-100', text: 'text-amber-800', label: 'Connecté en retard' },
    no_join_detected: { bg: 'bg-red-100', text: 'text-red-800', label: 'Aucune connexion' },
    manual_review: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'Revue manuelle' },
    partial_attendance: { bg: 'bg-orange-100', text: 'text-orange-800', label: 'Présence partielle' },
  };
  const b = badges[outcome] || badges.manual_review;
  return <span className={`inline-flex items-center gap-1 px-2 py-0.5 ${b.bg} ${b.text} rounded-full text-xs font-medium`}>{b.label}</span>;
};

const getIdentityConfidenceBadge = (confidence) => {
  const badges = {
    high: { bg: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-700', label: 'Identité forte' },
    medium: { bg: 'bg-amber-50 border-amber-200', text: 'text-amber-700', label: 'Identité moyenne' },
    low: { bg: 'bg-red-50 border-red-200', text: 'text-red-700', label: 'Identité faible' },
  };
  const b = badges[confidence] || badges.low;
  return <span className={`text-xs px-2 py-0.5 rounded-full border ${b.bg} ${b.text} font-medium`}>{b.label}</span>;
};

export default function VideoEvidencePanel({
  appointment,
  videoEvidence,
  videoIngestionLogs,
  showVideoIngest, setShowVideoIngest,
  videoIngestForm, setVideoIngestForm,
  ingestMode, setIngestMode,
  selectedFile, setSelectedFile,
  csvPreview, setCsvPreview,
  creatingMeeting, onCreateMeeting,
  fetchingAttendance, onFetchAttendance,
  fetchAttendanceError, setFetchAttendanceError,
  ingestingVideo, onVideoIngest,
  uploadingFile, onFileUpload,
  onFileSelect,
}) {
  const formatEvidenceDate = (ts) => formatEvidenceDateFr(ts);
  const provider = (appointment.meeting_provider || '').toLowerCase();
  const hasAutoFetch = provider === 'zoom' || provider === 'teams';
  const providerLabel = provider === 'zoom' ? 'Zoom' : provider === 'teams' ? 'Teams' : 'Google Meet';
  const meetingEnd = appointment.start_datetime && appointment.duration_minutes
    ? new Date(new Date(appointment.start_datetime).getTime() + appointment.duration_minutes * 60000)
    : null;
  const isMeetingEnded = meetingEnd && new Date() > meetingEnd;
  const hasEvidence = videoEvidence?.total_video_evidence > 0;

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-6 mt-6" data-testid="video-evidence-section">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-5">
        <div className="flex items-center gap-2 flex-wrap">
          <Monitor className="w-5 h-5 text-indigo-700" />
          <h2 className="text-base sm:text-lg font-semibold text-slate-900">Preuves de présence visio</h2>
          {appointment.meeting_provider && (
            <span className={`text-xs px-2 py-0.5 rounded-full ${getProviderIcon(appointment.meeting_provider).bg} ${getProviderIcon(appointment.meeting_provider).color} font-medium`}>
              {getProviderIcon(appointment.meeting_provider).label}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          {!appointment.meeting_join_url && appointment.meeting_provider && (
            <Button variant="default" size="sm" onClick={onCreateMeeting} disabled={creatingMeeting} className="whitespace-normal h-auto min-h-[36px]" data-testid="create-meeting-btn">
              {creatingMeeting ? <Loader2 className="w-4 h-4 animate-spin mr-1 flex-shrink-0" /> : <PlayCircle className="w-4 h-4 mr-1 flex-shrink-0" />}
              Créer la réunion
            </Button>
          )}
        </div>
      </div>

      {/* Provider-specific action bar */}
      <div className="mb-5" data-testid="video-evidence-action-bar">
        {hasAutoFetch ? (
          <div className={`rounded-lg border p-4 ${hasEvidence ? 'bg-emerald-50 border-emerald-200' : isMeetingEnded ? 'bg-blue-50 border-blue-200' : 'bg-slate-50 border-slate-200'}`}>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div className="min-w-0">
                {hasEvidence ? (
                  <p className="text-sm font-medium text-emerald-800" data-testid="evidence-status-fetched">Présences récupérées via {providerLabel}</p>
                ) : isMeetingEnded ? (
                  <>
                    <p className="text-sm font-medium text-blue-900" data-testid="evidence-status-ready">Réunion terminée — présences disponibles</p>
                    <p className="text-xs text-blue-700 mt-0.5">Récupérez les présences depuis {providerLabel}, ou attendez la récupération automatique.</p>
                  </>
                ) : (
                  <>
                    <p className="text-sm font-medium text-slate-700" data-testid="evidence-status-waiting">Réunion en cours ou à venir</p>
                    <p className="text-xs text-slate-500 mt-0.5">Les présences seront récupérées automatiquement depuis {providerLabel} après la fin de la réunion.</p>
                  </>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                {appointment.meeting_join_url && (
                  <Button variant={isMeetingEnded && !hasEvidence ? 'default' : 'outline'} size="sm" onClick={onFetchAttendance} disabled={fetchingAttendance} className="whitespace-normal text-left h-auto min-h-[36px]" data-testid="fetch-attendance-btn">
                    {fetchingAttendance ? <Loader2 className="w-4 h-4 animate-spin mr-1 flex-shrink-0" /> : <RefreshCw className="w-4 h-4 mr-1 flex-shrink-0" />}
                    Récupérer les présences
                  </Button>
                )}
                <Button variant="outline" size="sm" onClick={() => setShowVideoIngest(!showVideoIngest)} className="whitespace-normal text-left h-auto min-h-[36px]" data-testid="toggle-video-ingest-btn">
                  <Upload className="w-4 h-4 mr-1 flex-shrink-0" />
                  Import manuel
                </Button>
              </div>
            </div>

            {fetchAttendanceError && !hasEvidence && (
              <div className={`mt-3 p-3.5 rounded-lg border ${fetchAttendanceError.isPlanError ? 'bg-amber-50 border-amber-300' : 'bg-orange-50 border-orange-200'}`} data-testid="fetch-error-fallback-banner">
                <div className="flex items-start gap-3">
                  <AlertTriangle className={`w-5 h-5 mt-0.5 flex-shrink-0 ${fetchAttendanceError.isPlanError ? 'text-amber-600' : 'text-orange-600'}`} />
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-semibold ${fetchAttendanceError.isPlanError ? 'text-amber-900' : 'text-orange-900'}`}>
                      {fetchAttendanceError.isPlanError ? 'Plan Zoom Pro requis' : 'Récupération automatique indisponible'}
                    </p>
                    <p className={`text-sm mt-1 ${fetchAttendanceError.isPlanError ? 'text-amber-800' : 'text-orange-800'}`}>
                      {fetchAttendanceError.isPlanError
                        ? 'La récupération automatique nécessite un plan Zoom Pro. En attendant, utilisez l\'import manuel :'
                        : fetchAttendanceError.message}
                    </p>
                    {fetchAttendanceError.isPlanError && (
                      <div className="mt-2.5 flex items-center gap-2 flex-wrap">
                        <Button size="sm" className="h-8 text-sm bg-amber-600 hover:bg-amber-700 text-white"
                          onClick={() => { setShowVideoIngest(true); setFetchAttendanceError(null); }} data-testid="fallback-import-csv-btn">
                          <Upload className="w-4 h-4 mr-1.5" />
                          Importer le rapport CSV Zoom
                        </Button>
                        <span className="text-xs text-amber-600">
                          Zoom {'>'} Reports {'>'} Meeting {'>'} Participants {'>'} Export
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className={`rounded-lg border p-4 ${hasEvidence ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}`}>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div className="min-w-0">
                {hasEvidence ? (
                  <p className="text-sm font-medium text-emerald-800" data-testid="evidence-status-fetched">Présences importées pour {providerLabel}</p>
                ) : (
                  <>
                    <p className="text-sm font-medium text-amber-900" data-testid="evidence-status-meet-manual">Import requis — {providerLabel}</p>
                    <p className="text-xs text-amber-700 mt-0.5">Google Meet ne fournit pas de rapport automatique. Après la réunion, importez le rapport de présence (CSV ou JSON).</p>
                  </>
                )}
              </div>
              <div className="flex-shrink-0">
                <Button variant={!hasEvidence ? 'default' : 'outline'} size="sm"
                  onClick={() => setShowVideoIngest(!showVideoIngest)}
                  className={`whitespace-normal h-auto min-h-[36px] ${!hasEvidence ? 'bg-amber-600 hover:bg-amber-700' : ''}`}
                  data-testid="toggle-video-ingest-btn">
                  <Upload className="w-4 h-4 mr-1 flex-shrink-0" />
                  Importer le rapport de présence
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Ingestion Form */}
      {showVideoIngest && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-5 mb-5" data-testid="video-ingest-form">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <FileJson className="w-4 h-4 text-indigo-600" />
              <p className="text-sm font-semibold text-indigo-900">Importer un rapport de présence</p>
            </div>
            <div className="flex gap-1 bg-indigo-100 rounded-md p-0.5">
              <button onClick={() => setIngestMode('file')}
                className={`text-xs px-3 py-1 rounded ${ingestMode === 'file' ? 'bg-white text-indigo-700 shadow-sm font-medium' : 'text-indigo-500'}`}
                data-testid="ingest-mode-file">
                Fichier (CSV/JSON)
              </button>
              <button onClick={() => setIngestMode('json')}
                className={`text-xs px-3 py-1 rounded ${ingestMode === 'json' ? 'bg-white text-indigo-700 shadow-sm font-medium' : 'text-indigo-500'}`}
                data-testid="ingest-mode-json">
                JSON avancé
              </button>
            </div>
          </div>

          <div className="grid md:grid-cols-3 gap-3 mb-3">
            <div>
              <Label htmlFor="video-provider" className="text-xs text-slate-700">Provider</Label>
              <select id="video-provider" data-testid="video-provider-select"
                value={videoIngestForm.provider}
                onChange={(e) => setVideoIngestForm({ ...videoIngestForm, provider: e.target.value })}
                className="mt-1 w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm">
                <option value="zoom">Zoom</option>
                <option value="teams">Microsoft Teams</option>
                <option value="meet">Google Meet</option>
              </select>
            </div>
            <div>
              <Label htmlFor="video-meeting-id" className="text-xs text-slate-700">ID réunion externe (optionnel)</Label>
              <Input id="video-meeting-id" data-testid="video-meeting-id-input"
                value={videoIngestForm.external_meeting_id}
                onChange={(e) => setVideoIngestForm({ ...videoIngestForm, external_meeting_id: e.target.value })}
                placeholder="ex: 123456789" className="mt-1 h-9" />
            </div>
            <div>
              <Label htmlFor="video-join-url" className="text-xs text-slate-700">URL de la réunion (optionnel)</Label>
              <Input id="video-join-url" data-testid="video-join-url-input"
                value={videoIngestForm.meeting_join_url}
                onChange={(e) => setVideoIngestForm({ ...videoIngestForm, meeting_join_url: e.target.value })}
                placeholder="https://zoom.us/j/..." className="mt-1 h-9" />
            </div>
          </div>

          {ingestMode === 'file' && (
            <div>
              <p className="text-xs text-indigo-700 mb-3">
                Importez le rapport de présence {videoIngestForm.provider === 'zoom' ? 'Zoom' : videoIngestForm.provider === 'teams' ? 'Teams' : 'Google Meet'} (export CSV ou JSON).
                {videoIngestForm.provider === 'zoom' && ' Dans Zoom, allez dans Reports > Meeting > Participants pour exporter le CSV.'}
              </p>
              <div className="border-2 border-dashed border-indigo-300 rounded-lg p-6 text-center bg-white/50 hover:bg-white transition-colors">
                <input type="file" accept=".csv,.json" onChange={onFileSelect}
                  className="hidden" id="attendance-file-input" data-testid="attendance-file-input" />
                <label htmlFor="attendance-file-input" className="cursor-pointer">
                  <FileUp className="w-8 h-8 mx-auto mb-2 text-indigo-400" />
                  <p className="text-sm text-indigo-700 font-medium">Cliquez pour choisir un fichier</p>
                  <p className="text-xs text-indigo-500 mt-1">CSV ou JSON — max 5 Mo</p>
                </label>
              </div>

              {selectedFile && (
                <div className="mt-3 p-3 bg-white rounded-lg border border-indigo-200">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <FileJson className="w-4 h-4 text-indigo-500" />
                      <span className="text-sm font-medium text-slate-700">{selectedFile.name}</span>
                      <span className="text-xs text-slate-400">({(selectedFile.size / 1024).toFixed(1)} Ko)</span>
                    </div>
                    <button onClick={() => { setSelectedFile(null); setCsvPreview(null); }} className="text-xs text-red-500 hover:text-red-700">Supprimer</button>
                  </div>
                  {csvPreview && csvPreview.type === 'csv' && (
                    <div>
                      <p className="text-xs text-slate-500 mb-2">{csvPreview.total} participant(s) détecté(s) — aperçu :</p>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="bg-slate-50">
                              {csvPreview.headers?.slice(0, 5).map((h, i) => (
                                <th key={i} className="px-2 py-1 text-left font-medium text-slate-600 border-b">{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {csvPreview.rows?.map((row, i) => (
                              <tr key={i} className="border-b border-slate-100">
                                {csvPreview.headers?.slice(0, 5).map((h, j) => (
                                  <td key={j} className="px-2 py-1 text-slate-500">{row[h] || '—'}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      {csvPreview.total > 5 && <p className="text-xs text-slate-400 mt-1">...et {csvPreview.total - 5} autre(s)</p>}
                    </div>
                  )}
                  {csvPreview && csvPreview.type === 'json' && (
                    <div>
                      <p className="text-xs text-slate-500 mb-1">{csvPreview.total} participant(s) détecté(s)</p>
                      {csvPreview.participants?.map((p, i) => (
                        <div key={i} className="text-xs text-slate-500 py-0.5">
                          {p.user_email || p.emailAddress || p.email || p.name || 'Anonyme'}
                        </div>
                      ))}
                    </div>
                  )}
                  {csvPreview && csvPreview.type === 'error' && (
                    <p className="text-xs text-red-500">{csvPreview.message}</p>
                  )}
                </div>
              )}
            </div>
          )}

          {ingestMode === 'json' && (
            <div>
              <Label htmlFor="video-raw-json" className="text-xs text-slate-700">Rapport de présence (JSON)</Label>
              <textarea id="video-raw-json" data-testid="video-raw-json-input" rows={6}
                value={videoIngestForm.raw_json}
                onChange={(e) => setVideoIngestForm({ ...videoIngestForm, raw_json: e.target.value })}
                placeholder={videoIngestForm.provider === 'zoom'
                  ? '{\n  "meeting_id": "123456789",\n  "participants": [\n    {"user_email": "john@example.com", "name": "John Doe", "join_time": "2026-01-01T10:00:00Z", "leave_time": "2026-01-01T11:00:00Z", "duration": 3600}\n  ]\n}'
                  : videoIngestForm.provider === 'teams'
                  ? '{\n  "meeting_id": "AAMkAG...",\n  "attendanceRecords": [\n    {"emailAddress": "john@example.com", "identity": {"displayName": "John Doe"}, "totalAttendanceInSeconds": 3600, "attendanceIntervals": [{"joinDateTime": "2026-01-01T10:00:00Z", "leaveDateTime": "2026-01-01T11:00:00Z"}]}\n  ]\n}'
                  : '{\n  "meeting_id": "abc-defg-hij",\n  "participants": [\n    {"name": "John Doe", "email": "john@example.com", "join_time": "2026-01-01T10:00:00Z", "leave_time": "2026-01-01T11:00:00Z", "duration": 3600}\n  ]\n}'
                }
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono" />
            </div>
          )}

          {videoIngestForm.provider === 'meet' && (
            <div className="flex items-start gap-2 mt-3 p-2.5 bg-amber-50 border border-amber-200 rounded-md">
              <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-amber-800">
                <strong>Google Meet = preuve assistée uniquement.</strong> Les identités Meet ne sont pas vérifiées par Google.
                Toute preuve Meet sera marquée comme confiance faible et nécessitera une revue manuelle.
              </p>
            </div>
          )}
          <div className="flex gap-2 mt-4">
            {ingestMode === 'file' ? (
              <Button onClick={onFileUpload} disabled={uploadingFile || !selectedFile} size="sm" data-testid="submit-file-upload-btn">
                {uploadingFile ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Upload className="w-4 h-4 mr-1" />}
                Analyser et ingérer ({selectedFile?.name || 'aucun fichier'})
              </Button>
            ) : (
              <Button onClick={onVideoIngest} disabled={ingestingVideo || !videoIngestForm.raw_json.trim()} size="sm" data-testid="submit-video-ingest-btn">
                {ingestingVideo ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Upload className="w-4 h-4 mr-1" />}
                Analyser et ingérer
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={() => { setShowVideoIngest(false); setSelectedFile(null); setCsvPreview(null); }}>Annuler</Button>
          </div>
        </div>
      )}

      {/* Video Evidence Timeline */}
      {videoEvidence?.video_evidence?.length > 0 ? (
        <div className="space-y-4">
          {videoEvidence.video_evidence.map((ve) => {
            const facts = ve.derived_facts || {};
            const providerInfo = getProviderIcon(facts.provider);
            return (
              <div key={ve.evidence_id} className="border border-slate-200 rounded-xl overflow-hidden" data-testid={`video-evidence-${ve.evidence_id}`}>
                <div className="px-5 py-3 bg-indigo-50/50 border-b border-slate-200 flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-3">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${providerInfo.bg} ${providerInfo.color}`}>
                      <Monitor className="w-3 h-3" />
                      {providerInfo.label}
                    </span>
                    {facts.participant_email_from_provider && <span className="text-xs text-slate-500">{facts.participant_email_from_provider}</span>}
                    {facts.participant_name_from_provider && !facts.participant_email_from_provider && <span className="text-xs text-slate-500">{facts.participant_name_from_provider}</span>}
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    {getVideoOutcomeBadge(facts.video_attendance_outcome)}
                    {getIdentityConfidenceBadge(facts.identity_confidence)}
                    {facts.provider_evidence_ceiling === 'assisted' && (
                      <span className="text-xs px-2 py-0.5 rounded-full border bg-amber-50 border-amber-200 text-amber-700 font-medium flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" />
                        Preuve assistée
                      </span>
                    )}
                  </div>
                </div>
                <div className="px-5 py-3 space-y-2">
                  <div className="flex items-center gap-4 text-sm">
                    {facts.joined_at && (
                      <span className="flex items-center gap-1 text-emerald-700">
                        <Check className="w-3.5 h-3.5" />
                        Connecté : {formatEvidenceDate(facts.joined_at)}
                      </span>
                    )}
                    {facts.left_at && (
                      <span className="flex items-center gap-1 text-slate-500">
                        <X className="w-3.5 h-3.5" />
                        Déconnecté : {formatEvidenceDate(facts.left_at)}
                      </span>
                    )}
                    {facts.duration_seconds != null && (
                      <span className="text-xs text-slate-400">Durée : {Math.round(facts.duration_seconds / 60)} min</span>
                    )}
                  </div>
                  {facts.temporal_detail && (
                    <p className={`text-xs flex items-center gap-1 ${
                      facts.temporal_consistency === 'valid' ? 'text-emerald-600' :
                      facts.temporal_consistency === 'valid_late' ? 'text-amber-600' : 'text-red-600'
                    }`}>
                      <Timer className="w-3 h-3" />
                      {facts.temporal_detail}
                    </p>
                  )}
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <UserCog className="w-3 h-3" />
                    <span>{facts.identity_match_detail}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      ve.confidence_score === 'high' ? 'bg-emerald-100 text-emerald-700' :
                      ve.confidence_score === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'
                    }`}>
                      Confiance {ve.confidence_score === 'high' ? 'haute' : ve.confidence_score === 'medium' ? 'moyenne' : 'faible'}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-8 text-slate-400" data-testid="no-video-evidence">
          <Monitor className="w-10 h-10 mx-auto mb-2 text-slate-300" />
          {provider === 'meet' ? (
            <>
              <p className="text-sm text-slate-500">Aucune preuve de présence importée.</p>
              <p className="text-xs text-amber-600 mt-1 font-medium">Google Meet requiert un import manuel du rapport de présence.</p>
            </>
          ) : (provider === 'zoom' || provider === 'teams') ? (
            <>
              <p className="text-sm text-slate-500">Aucune preuve de présence récupérée.</p>
              <p className="text-xs text-slate-400 mt-1">Les présences seront récupérées automatiquement après la fin de la réunion, ou utilisez le bouton ci-dessus.</p>
            </>
          ) : (
            <p className="text-sm">Aucune preuve de présence visio pour le moment.</p>
          )}
        </div>
      )}

      {/* Ingestion Logs */}
      {videoIngestionLogs.length > 0 && (
        <div className="mt-5 pt-4 border-t border-slate-200">
          <p className="text-sm font-medium text-slate-600 mb-2">Historique d'ingestion</p>
          <div className="space-y-2">
            {videoIngestionLogs.map((log) => (
              <div key={log.ingestion_log_id} className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg text-xs" data-testid={`ingestion-log-${log.ingestion_log_id}`}>
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-0.5 rounded-full font-medium ${getProviderIcon(log.provider).bg} ${getProviderIcon(log.provider).color}`}>
                    {getProviderIcon(log.provider).label}
                  </span>
                  <span className="text-slate-500">{log.matched_count || 0} matché(s), {log.unmatched_count || 0} non-matché(s)</span>
                  {log.provider_evidence_ceiling === 'assisted' && <span className="text-amber-600 font-medium">Preuve assistée</span>}
                </div>
                <span className="text-slate-400">{formatEvidenceDate(log.ingested_at)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
