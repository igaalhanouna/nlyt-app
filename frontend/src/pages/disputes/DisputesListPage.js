import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, AlertTriangle, CheckCircle, Clock, ChevronRight, Loader2, Scale } from 'lucide-react';
import api from '../../services/api';

const STATUS_LABELS = {
  opened: { label: 'Ouvert', color: 'bg-blue-100 text-blue-700' },
  awaiting_evidence: { label: 'En attente de preuves', color: 'bg-amber-100 text-amber-700' },
  escalated: { label: 'Escaladé', color: 'bg-red-100 text-red-700' },
  resolved: { label: 'Résolu', color: 'bg-emerald-100 text-emerald-700' },
};

export default function DisputesListPage() {
  const navigate = useNavigate();
  const [disputes, setDisputes] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchDisputes = useCallback(async () => {
    try {
      const res = await api.get('/api/disputes/mine');
      setDisputes(res.data.disputes || []);
    } catch (err) {
      console.error('Error fetching disputes:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDisputes(); }, [fetchDisputes]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
      </div>
    );
  }

  const open = disputes.filter(d => d.status !== 'resolved');
  const resolved = disputes.filter(d => d.status === 'resolved');

  return (
    <div className="min-h-screen bg-slate-50" data-testid="disputes-list-page">
      <div className="max-w-2xl mx-auto p-4 sm:p-6">
        <button
          onClick={() => navigate('/dashboard')}
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-6"
        >
          <ArrowLeft className="w-4 h-4" /> Retour au dashboard
        </button>

        <div className="flex items-center gap-2 mb-6">
          <Scale className="w-5 h-5 text-slate-600" />
          <h1 className="text-xl font-semibold text-slate-800">Litiges en cours</h1>
          {open.length > 0 && (
            <span className="ml-2 px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-xs font-medium">
              {open.length}
            </span>
          )}
        </div>

        {disputes.length === 0 ? (
          <div className="bg-white rounded-xl border p-8 text-center">
            <CheckCircle className="w-8 h-8 text-emerald-400 mx-auto mb-3" />
            <p className="text-sm text-slate-500">Aucun litige en cours</p>
          </div>
        ) : (
          <div className="space-y-3">
            {open.map(d => <DisputeCard key={d.dispute_id} dispute={d} />)}
            {resolved.length > 0 && (
              <>
                <h2 className="text-sm font-medium text-slate-400 mt-6 mb-2">Résolus</h2>
                {resolved.map(d => <DisputeCard key={d.dispute_id} dispute={d} />)}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function DisputeCard({ dispute }) {
  const s = STATUS_LABELS[dispute.status] || STATUS_LABELS.opened;
  const deadline = dispute.deadline ? new Date(dispute.deadline) : null;

  return (
    <Link
      to={`/disputes/${dispute.dispute_id}`}
      className="block bg-white rounded-xl border border-slate-200 hover:border-slate-300 transition-colors p-4"
      data-testid={`dispute-card-${dispute.dispute_id}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-slate-700 truncate">
            {dispute.appointment_title || 'Rendez-vous'}
          </p>
          {dispute.appointment_date && (
            <p className="text-xs text-slate-400 mt-0.5">
              {new Date(dispute.appointment_date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
            </p>
          )}
          <p className="text-xs text-slate-500 mt-1.5">
            Concerne : <span className="font-medium">{dispute.target_name || 'Participant'}</span>
          </p>
          {dispute.declaration_summary && (
            <p className="text-xs text-slate-400 mt-1">
              {dispute.declaration_summary.declared_absent_count} absent &middot; {dispute.declaration_summary.declared_present_count} présent
            </p>
          )}
        </div>
        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${s.color}`}>
            {s.label}
          </span>
          {deadline && dispute.status !== 'resolved' && (
            <span className="flex items-center gap-1 text-xs text-slate-400">
              <Clock className="w-3 h-3" />
              {deadline.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })}
            </span>
          )}
          <ChevronRight className="w-4 h-4 text-slate-300" />
        </div>
      </div>
    </Link>
  );
}
