import React, { useState, useEffect, useCallback } from 'react';
import AppNavbar from '../../components/AppNavbar';
import AppBreadcrumb from '../../components/AppBreadcrumb';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { ArrowDownCircle, Building2, Clock, ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import { safeFetchJson } from '../../utils/safeFetchJson';

const API_URL = process.env.REACT_APP_BACKEND_URL;

function maskIban(iban) {
  if (!iban || iban.length < 8) return iban || '—';
  return `${iban.slice(0, 4)} **** **** ${iban.slice(-4)}`;
}

function formatCents(cents) {
  return (cents / 100).toFixed(2).replace('.', ',') + ' EUR';
}

function PayoutForm({ assoc, onSubmit, onCancel, saving }) {
  const [amount, setAmount] = useState('');
  const [bankRef, setBankRef] = useState('');
  const [transferDate, setTransferDate] = useState(new Date().toISOString().slice(0, 10));

  const amountCents = Math.round(parseFloat(amount || '0') * 100);
  const isValid = amountCents > 0 && amountCents <= assoc.available_balance && bankRef.trim().length > 0 && transferDate;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!isValid) return;
    onSubmit({
      association_id: assoc.association_id,
      amount_cents: amountCents,
      bank_reference: bankRef.trim(),
      transfer_date: transferDate,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4" data-testid="payout-form">
      <div className="bg-slate-50 rounded-lg p-3 text-sm">
        <p className="font-medium text-slate-700">{assoc.name}</p>
        <p className="text-slate-500 font-mono text-xs mt-1">IBAN : {maskIban(assoc.iban)}</p>
        {assoc.account_holder && <p className="text-slate-500 text-xs">Titulaire : {assoc.account_holder}</p>}
        <p className="text-slate-600 mt-1">Solde disponible : <span className="font-semibold">{formatCents(assoc.available_balance)}</span></p>
      </div>
      <div>
        <Label htmlFor="payout-amount">Montant du virement (EUR)</Label>
        <Input
          id="payout-amount"
          type="number"
          step="0.01"
          min="0.01"
          max={(assoc.available_balance / 100).toFixed(2)}
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="0,00"
          className="mt-1"
          data-testid="payout-amount-input"
          required
        />
        {amountCents > assoc.available_balance && amount && (
          <p className="text-xs text-red-500 mt-1 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> Depasse le solde disponible
          </p>
        )}
      </div>
      <div>
        <Label htmlFor="payout-ref">Reference bancaire du virement</Label>
        <Input
          id="payout-ref"
          value={bankRef}
          onChange={(e) => setBankRef(e.target.value)}
          placeholder="Ex: VIR-20260225-CROIXROUGE"
          className="mt-1"
          data-testid="payout-bank-reference-input"
          required
        />
      </div>
      <div>
        <Label htmlFor="payout-date">Date du virement</Label>
        <Input
          id="payout-date"
          type="date"
          value={transferDate}
          onChange={(e) => setTransferDate(e.target.value)}
          className="mt-1"
          data-testid="payout-transfer-date-input"
          required
        />
      </div>
      <div className="flex justify-end gap-3 pt-2">
        <Button type="button" variant="outline" onClick={onCancel} data-testid="payout-cancel-btn">Annuler</Button>
        <Button type="submit" disabled={!isValid || saving} data-testid="payout-submit-btn">
          {saving ? 'Enregistrement...' : 'Confirmer le reversement'}
        </Button>
      </div>
    </form>
  );
}

function PayoutHistoryRow({ payout }) {
  return (
    <div className="flex items-center justify-between py-2 px-3 text-sm border-b border-slate-50 last:border-0" data-testid={`payout-row-${payout.payout_id}`}>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-slate-700">{formatCents(payout.amount_cents)}</span>
          <span className="text-xs text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded font-medium">effectue</span>
        </div>
        <p className="text-xs text-slate-400 mt-0.5 truncate">
          Ref : {payout.bank_reference} | Vire le {payout.transfer_date}
        </p>
      </div>
      <div className="text-right flex-shrink-0 ml-3">
        <p className="text-xs text-slate-400">{payout.admin_name || '—'}</p>
        <p className="text-[11px] text-slate-300">{new Date(payout.created_at).toLocaleDateString('fr-FR')}</p>
      </div>
    </div>
  );
}

function AssociationPayoutCard({ assoc, onPayout, payouts, loadingPayouts }) {
  const [expanded, setExpanded] = useState(false);
  const assocPayouts = payouts.filter(p => p.association_id === assoc.association_id);
  const hasBalance = assoc.available_balance > 0;
  const hasIban = !!assoc.iban;

  return (
    <div className={`bg-white rounded-lg border ${hasBalance ? 'border-slate-200' : 'border-slate-100'} overflow-hidden`} data-testid={`payout-card-${assoc.association_id}`}>
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-slate-900 truncate">{assoc.name}</h3>
            <div className="flex items-center gap-4 mt-1.5 flex-wrap">
              <span className="text-sm">
                <span className="text-slate-500">Disponible : </span>
                <span className={`font-semibold ${assoc.available_balance > 0 ? 'text-emerald-600' : 'text-slate-400'}`}>
                  {formatCents(assoc.available_balance)}
                </span>
              </span>
              {assoc.pending_balance > 0 && (
                <span className="text-sm">
                  <span className="text-slate-400">En attente : </span>
                  <span className="text-amber-500 font-medium">{formatCents(assoc.pending_balance)}</span>
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 mt-1.5 flex-wrap">
              {hasIban ? (
                <span className="text-xs text-slate-400 font-mono inline-flex items-center gap-1">
                  <Building2 className="w-3 h-3" /> {maskIban(assoc.iban)}
                  {assoc.account_holder && <span className="font-sans ml-1">| {assoc.account_holder}</span>}
                </span>
              ) : (
                <span className="text-xs text-amber-500 inline-flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" /> IBAN non renseigne
                </span>
              )}
            </div>
            {assoc.last_payout && (
              <p className="text-xs text-slate-400 mt-1 inline-flex items-center gap-1">
                <Clock className="w-3 h-3" />
                Dernier reversement : {formatCents(assoc.last_payout.amount_cents)} le {assoc.last_payout.transfer_date}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <Button
              size="sm"
              disabled={!hasBalance || !hasIban}
              onClick={() => onPayout(assoc)}
              data-testid={`payout-btn-${assoc.association_id}`}
            >
              <ArrowDownCircle className="w-4 h-4 mr-1.5" />
              Enregistrer un virement
            </Button>
          </div>
        </div>
      </div>

      {/* Expandable history */}
      {assocPayouts.length > 0 && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full flex items-center justify-between px-4 py-2 bg-slate-50 border-t border-slate-100 text-xs text-slate-500 hover:bg-slate-100 transition-colors"
            data-testid={`toggle-history-${assoc.association_id}`}
          >
            <span>{assocPayouts.length} reversement{assocPayouts.length > 1 ? 's' : ''} effectue{assocPayouts.length > 1 ? 's' : ''}</span>
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {expanded && (
            <div className="border-t border-slate-100" data-testid={`history-${assoc.association_id}`}>
              {assocPayouts.map(p => <PayoutHistoryRow key={p.payout_id} payout={p} />)}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function AdminPayouts() {
  const [dashboard, setDashboard] = useState([]);
  const [payouts, setPayouts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [payoutTarget, setPayoutTarget] = useState(null);
  const [saving, setSaving] = useState(false);

  const token = localStorage.getItem('nlyt_token');
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };

  const fetchData = useCallback(async () => {
    try {
      const [dashResult, payoutsResult] = await Promise.all([
        safeFetchJson(`${API_URL}/api/admin/payouts/dashboard`, { headers }),
        safeFetchJson(`${API_URL}/api/admin/payouts?limit=100`, { headers }),
      ]);
      if (dashResult.ok) setDashboard(dashResult.data.associations || []);
      if (payoutsResult.ok) setPayouts(payoutsResult.data.payouts || []);
    } catch {
      toast.error('Erreur de chargement');
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleCreatePayout = async (body) => {
    setSaving(true);
    try {
      const { ok, data } = await safeFetchJson(`${API_URL}/api/admin/payouts`, {
        method: 'POST', headers, body: JSON.stringify(body),
      });
      if (!ok) throw new Error(data.detail || 'Erreur');
      toast.success(`Reversement de ${formatCents(body.amount_cents)} enregistre`);
      setPayoutTarget(null);
      fetchData();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  const totalAvailable = dashboard.reduce((s, a) => s + a.available_balance, 0);
  const totalPending = dashboard.reduce((s, a) => s + a.pending_balance, 0);
  const totalPaid = payouts.reduce((s, p) => s + p.amount_cents, 0);

  return (
    <div className="min-h-screen bg-background">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Administration', href: '/admin' },
        { label: 'Reversements' },
      ]} />
      <div className="max-w-5xl mx-auto px-6 pb-12">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900" data-testid="admin-payouts-title">Reversements associations</h1>
          <p className="text-sm text-slate-500 mt-1">Enregistrement des virements bancaires manuels vers les associations caritatives</p>
        </div>

        {/* KPI summary */}
        <div className="grid grid-cols-3 gap-4 mb-8" data-testid="payouts-kpi">
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <p className="text-xs text-slate-400 uppercase tracking-wider">A reverser</p>
            <p className={`text-xl font-bold mt-1 ${totalAvailable > 0 ? 'text-emerald-600' : 'text-slate-300'}`}>{formatCents(totalAvailable)}</p>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <p className="text-xs text-slate-400 uppercase tracking-wider">En attente (contestation)</p>
            <p className={`text-xl font-bold mt-1 ${totalPending > 0 ? 'text-amber-500' : 'text-slate-300'}`}>{formatCents(totalPending)}</p>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <p className="text-xs text-slate-400 uppercase tracking-wider">Total reverse</p>
            <p className="text-xl font-bold mt-1 text-slate-700">{formatCents(totalPaid)}</p>
          </div>
        </div>

        {/* Payout form modal */}
        {payoutTarget && (
          <div className="bg-white p-6 rounded-lg border border-blue-200 mb-6" data-testid="payout-form-container">
            <h2 className="text-lg font-semibold text-slate-800 mb-4">Enregistrer un reversement</h2>
            <PayoutForm
              assoc={payoutTarget}
              onSubmit={handleCreatePayout}
              onCancel={() => setPayoutTarget(null)}
              saving={saving}
            />
          </div>
        )}

        {/* Association cards */}
        {loading ? (
          <div className="text-center py-12 text-slate-500">Chargement...</div>
        ) : dashboard.length === 0 ? (
          <div className="text-center py-12 text-slate-500">Aucune association active</div>
        ) : (
          <div className="space-y-3" data-testid="payouts-associations-list">
            {dashboard.map(assoc => (
              <AssociationPayoutCard
                key={assoc.association_id}
                assoc={assoc}
                onPayout={(a) => { setPayoutTarget(a); }}
                payouts={payouts}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
