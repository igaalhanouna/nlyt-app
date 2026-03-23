import React, { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { walletAPI, connectAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import {
  ArrowLeft, Wallet, Loader2, ExternalLink, AlertTriangle,
  CheckCircle, Clock, XCircle, RefreshCw, ArrowUpRight, ArrowDownLeft,
  Banknote, ShieldAlert
} from 'lucide-react';
import { toast } from 'sonner';

const STATUS_CONFIG = {
  not_started: {
    label: 'Non configuré',
    description: 'Configurez votre compte de paiement pour pouvoir retirer vos fonds.',
    icon: AlertTriangle,
    color: 'text-amber-600',
    bg: 'bg-amber-50 border-amber-200',
    actionLabel: 'Configurer mon compte',
    actionEnabled: true,
  },
  onboarding: {
    label: 'Vérification en cours',
    description: 'Votre compte est en cours de vérification par Stripe. Vous serez notifié une fois la vérification terminée.',
    icon: Clock,
    color: 'text-blue-600',
    bg: 'bg-blue-50 border-blue-200',
    actionLabel: 'Reprendre la vérification',
    actionEnabled: true,
  },
  restricted: {
    label: 'Informations complémentaires requises',
    description: 'Stripe nécessite des informations complémentaires pour activer votre compte.',
    icon: ShieldAlert,
    color: 'text-orange-600',
    bg: 'bg-orange-50 border-orange-200',
    actionLabel: 'Compléter la vérification',
    actionEnabled: true,
  },
  active: {
    label: 'Compte vérifié',
    description: 'Votre compte de paiement est actif. Vous pouvez recevoir des retraits.',
    icon: CheckCircle,
    color: 'text-emerald-600',
    bg: 'bg-emerald-50 border-emerald-200',
    actionLabel: 'Accéder à mon dashboard Stripe',
    actionEnabled: true,
  },
  disabled: {
    label: 'Compte désactivé',
    description: 'Votre compte de paiement a été désactivé. Contactez le support pour plus d\'informations.',
    icon: XCircle,
    color: 'text-red-600',
    bg: 'bg-red-50 border-red-200',
    actionLabel: 'Reconfigurer mon compte',
    actionEnabled: true,
  },
};

const TX_TYPE_LABELS = {
  credit_pending: { label: 'Crédit en attente', icon: ArrowDownLeft, color: 'text-blue-600' },
  credit_available: { label: 'Crédit disponible', icon: ArrowDownLeft, color: 'text-emerald-600' },
  debit_payout: { label: 'Retrait', icon: ArrowUpRight, color: 'text-red-600' },
  debit_refund: { label: 'Remboursement', icon: ArrowUpRight, color: 'text-orange-600' },
};

function formatCents(cents, currency = 'eur') {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency }).format(cents / 100);
}

export default function WalletPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [wallet, setWallet] = useState(null);
  const [connectStatus, setConnectStatus] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [txTotal, setTxTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [onboarding, setOnboarding] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [walletRes, connectRes, txRes] = await Promise.all([
        walletAPI.get(),
        connectAPI.getStatus(),
        walletAPI.getTransactions(20, 0),
      ]);
      setWallet(walletRes.data);
      setConnectStatus(connectRes.data);
      setTransactions(txRes.data.transactions || []);
      setTxTotal(txRes.data.total || 0);
    } catch {
      toast.error("Erreur lors du chargement du wallet");
    } finally {
      setLoading(false);
    }
  }, []);

  // Handle return from Stripe Connect onboarding
  useEffect(() => {
    const connectParam = searchParams.get('connect');
    if (connectParam === 'complete') {
      toast.success("Vérification soumise — en attente de confirmation Stripe");
      setSearchParams({}, { replace: true });
    } else if (connectParam === 'refresh') {
      // Auto-retry onboarding (link expired)
      toast.info("Le lien a expiré, génération d'un nouveau lien...");
      setSearchParams({}, { replace: true });
      handleOnboard();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleOnboard = async () => {
    setOnboarding(true);
    try {
      const res = await connectAPI.onboard();
      if (res.data.onboarding_url) {
        window.location.href = res.data.onboarding_url;
        return;
      }
      // No URL = already active or dev mode
      toast.success(res.data.message || "Compte déjà actif");
      await fetchData();
    } catch (err) {
      const msg = err.response?.data?.detail || "Erreur lors de l'onboarding";
      toast.error(msg);
    } finally {
      setOnboarding(false);
    }
  };

  const handleDashboard = async () => {
    try {
      const res = await connectAPI.getDashboard();
      if (res.data.dashboard_url) {
        window.open(res.data.dashboard_url, '_blank');
      }
    } catch (err) {
      const msg = err.response?.data?.detail || "Erreur lors de l'accès au dashboard";
      toast.error(msg);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="max-w-2xl mx-auto">
          <Link to="/settings"><Button variant="ghost" className="mb-6"><ArrowLeft className="w-4 h-4 mr-2" />Retour</Button></Link>
          <div className="flex items-center justify-center py-24">
            <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
            <span className="ml-3 text-slate-500">Chargement...</span>
          </div>
        </div>
      </div>
    );
  }

  const status = connectStatus?.connect_status || 'not_started';
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.not_started;
  const StatusIcon = cfg.icon;

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-2xl mx-auto">
        <Link to="/settings"><Button variant="ghost" className="mb-6" data-testid="back-to-settings"><ArrowLeft className="w-4 h-4 mr-2" />Retour aux paramètres</Button></Link>

        <div className="flex items-center gap-3 mb-2">
          <Wallet className="w-7 h-7 text-slate-700" />
          <h1 className="text-2xl font-bold text-slate-900">Mon Wallet NLYT</h1>
        </div>
        <p className="text-sm text-slate-500 mb-8">Gérez vos fonds et votre compte de paiement</p>

        {/* Balance Cards */}
        {wallet && (
          <div className="grid grid-cols-2 gap-4 mb-8" data-testid="wallet-balances">
            <div className="bg-white border border-slate-200 rounded-lg p-5">
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">Disponible</p>
              <p className="text-2xl font-bold text-slate-900" data-testid="available-balance">
                {formatCents(wallet.available_balance, wallet.currency)}
              </p>
            </div>
            <div className="bg-white border border-slate-200 rounded-lg p-5">
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">En attente</p>
              <p className="text-2xl font-bold text-slate-500" data-testid="pending-balance">
                {formatCents(wallet.pending_balance, wallet.currency)}
              </p>
            </div>
          </div>
        )}

        {/* Connect Status Card */}
        <div className={`border rounded-lg p-5 mb-8 ${cfg.bg}`} data-testid="connect-status-card">
          <div className="flex items-start gap-3">
            <StatusIcon className={`w-5 h-5 mt-0.5 flex-shrink-0 ${cfg.color}`} />
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <h3 className={`font-semibold ${cfg.color}`} data-testid="connect-status-label">{cfg.label}</h3>
                <span className="text-xs px-2 py-0.5 rounded-full bg-white/60 font-mono" data-testid="connect-status-badge">{status}</span>
              </div>
              <p className="text-sm mt-1 opacity-80">{cfg.description}</p>

              <div className="mt-4 flex gap-3">
                {status === 'active' ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleDashboard}
                    data-testid="stripe-dashboard-btn"
                  >
                    <ExternalLink className="w-4 h-4 mr-2" />
                    {cfg.actionLabel}
                  </Button>
                ) : cfg.actionEnabled ? (
                  <Button
                    size="sm"
                    onClick={handleOnboard}
                    disabled={onboarding}
                    data-testid="connect-onboard-btn"
                  >
                    {onboarding ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Banknote className="w-4 h-4 mr-2" />}
                    {cfg.actionLabel}
                  </Button>
                ) : null}

                <Button size="sm" variant="ghost" onClick={fetchData} data-testid="refresh-wallet-btn">
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Payout Eligibility */}
        {wallet && status === 'active' && (
          <div className="mb-8">
            {wallet.can_payout ? (
              <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 flex items-center gap-3" data-testid="payout-eligible">
                <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-emerald-800">
                    Vous pouvez retirer {formatCents(wallet.available_balance, wallet.currency)}
                  </p>
                  <p className="text-xs text-emerald-600 mt-0.5">Le bouton de retrait sera disponible dans une prochaine mise à jour (Phase 4)</p>
                </div>
              </div>
            ) : (
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 flex items-center gap-3" data-testid="payout-not-eligible">
                <AlertTriangle className="w-5 h-5 text-slate-400 flex-shrink-0" />
                <p className="text-sm text-slate-600">
                  Montant minimum de retrait : {formatCents(wallet.minimum_payout, wallet.currency)}
                </p>
              </div>
            )}
          </div>
        )}

        {/* Transaction History */}
        <div data-testid="transaction-history">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Historique des transactions</h2>

          {transactions.length === 0 ? (
            <div className="bg-white border border-slate-200 rounded-lg p-8 text-center" data-testid="no-transactions">
              <Clock className="w-8 h-8 text-slate-300 mx-auto mb-3" />
              <p className="text-sm text-slate-500">Aucune transaction pour le moment</p>
            </div>
          ) : (
            <div className="bg-white border border-slate-200 rounded-lg divide-y divide-slate-100">
              {transactions.map((tx) => {
                const txCfg = TX_TYPE_LABELS[tx.type] || TX_TYPE_LABELS.credit_available;
                const TxIcon = txCfg.icon;
                const isCredit = tx.type?.startsWith('credit');

                return (
                  <div key={tx.transaction_id} className="p-4 flex items-center justify-between" data-testid={`tx-${tx.transaction_id}`}>
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${isCredit ? 'bg-emerald-50' : 'bg-red-50'}`}>
                        <TxIcon className={`w-4 h-4 ${txCfg.color}`} />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-slate-900">{txCfg.label}</p>
                        <p className="text-xs text-slate-500">{tx.description || '—'}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className={`text-sm font-semibold ${isCredit ? 'text-emerald-600' : 'text-red-600'}`}>
                        {isCredit ? '+' : '-'}{formatCents(tx.amount, tx.currency)}
                      </p>
                      <p className="text-xs text-slate-400">
                        {tx.created_at ? new Date(tx.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' }) : ''}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {txTotal > 20 && (
            <p className="text-xs text-slate-400 text-center mt-3">
              {txTotal} transactions au total — pagination à venir
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
