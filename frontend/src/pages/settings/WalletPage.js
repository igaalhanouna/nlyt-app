import React, { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { walletAPI, connectAPI } from '../../services/api';
import { Button } from '../../components/ui/button';
import {
  Wallet, Loader2, ExternalLink, AlertTriangle,
  CheckCircle, Clock, XCircle, RefreshCw, ArrowUpRight, ArrowDownLeft,
  Banknote, ShieldAlert, ChevronDown, ChevronUp, Flag, Lock,
  Info, Scale, CircleDot, Heart
} from 'lucide-react';
import { toast } from 'sonner';
import SettingsPageLayout from '../../components/SettingsPageLayout';

/* ─── Config & Helpers ──────────────────────────────────────── */

const CONNECT_STATUS_CONFIG = {
  not_started: { label: 'Compte bancaire non configuré', description: 'Vous devez lier votre compte bancaire pour retirer vos fonds.', icon: AlertTriangle, color: 'text-amber-600', bg: 'bg-amber-50 border-amber-200', actionLabel: 'Lier mon compte bancaire' },
  onboarding: { label: 'Vérification en cours', description: 'Votre compte bancaire est en cours de vérification.', icon: Clock, color: 'text-blue-600', bg: 'bg-blue-50 border-blue-200', actionLabel: 'Reprendre la vérification' },
  restricted: { label: 'Informations requises', description: 'Des informations complémentaires sont nécessaires pour finaliser la liaison.', icon: ShieldAlert, color: 'text-orange-600', bg: 'bg-orange-50 border-orange-200', actionLabel: 'Compléter la vérification' },
  active: { label: 'Votre compte bancaire', description: 'Votre compte bancaire est lié. Vous pouvez retirer vos fonds à tout moment.', icon: CheckCircle, color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-200', actionLabel: 'Modifier mon compte bancaire' },
  disabled: { label: 'Compte bancaire désactivé', description: 'Contactez le support pour plus d\'informations.', icon: XCircle, color: 'text-red-600', bg: 'bg-red-50 border-red-200', actionLabel: 'Reconfigurer' },
};

const DIST_STATUS = {
  pending_hold: { label: 'En attente', color: 'bg-blue-100 text-blue-700', hint: 'Période de vérification de 15 jours en cours' },
  distributing: { label: 'En cours', color: 'bg-indigo-100 text-indigo-700', hint: 'Distribution en cours de finalisation' },
  completed: { label: 'Finalisée', color: 'bg-emerald-100 text-emerald-700', hint: 'Les fonds sont disponibles dans les wallets' },
  contested: { label: 'Contestée', color: 'bg-orange-100 text-orange-700', hint: 'Un signalement a été déposé — en attente de résolution' },
  cancelled: { label: 'Annulée', color: 'bg-red-100 text-red-700', hint: 'La distribution a été annulée et les fonds remboursés' },
};

const ROLE_LABELS = {
  platform: 'NLYT (commission)',
  charity: 'Association',
  organizer: 'Organisateur (dédommagement)',
  participant: 'Participant (compensation)',
};

function fmt(cents, currency = 'eur') {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency }).format(cents / 100);
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
}

function fmtDateShort(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
}

/* ─── Balance Cards ─────────────────────────────────────────── */

function BalanceCards({ wallet, onPayout, payoutLoading }) {
  if (!wallet) return null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-8" data-testid="wallet-balances">
      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-1">
          <Lock className="w-3.5 h-3.5 text-blue-500" />
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">En attente</p>
        </div>
        <p className="text-xl font-bold text-slate-700" data-testid="pending-balance">
          {fmt(wallet.pending_balance, wallet.currency)}
        </p>
        <p className="text-[11px] text-slate-400 mt-1">Fonds en période de vérification (15j)</p>
      </div>
      <div className="bg-white border border-emerald-200 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-1">
          <Wallet className="w-3.5 h-3.5 text-emerald-500" />
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Disponible</p>
        </div>
        <p className="text-xl font-bold text-slate-900" data-testid="available-balance">
          {fmt(wallet.available_balance, wallet.currency)}
        </p>
        <p className="text-[11px] text-slate-400 mt-1">Dans votre wallet, non encore retiré</p>
      </div>
      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-1">
          <Banknote className="w-3.5 h-3.5 text-slate-400" />
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Retirable vers votre banque</p>
        </div>
        <p className="text-xl font-bold text-slate-500" data-testid="withdrawable-balance">
          {wallet.can_payout ? fmt(wallet.available_balance, wallet.currency) : fmt(0, wallet.currency)}
        </p>
        {wallet.can_payout ? (
          <Button
            size="sm"
            className="mt-2 w-full bg-emerald-600 hover:bg-emerald-700 text-white text-xs"
            onClick={onPayout}
            disabled={payoutLoading}
            data-testid="payout-btn"
          >
            {payoutLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <ArrowUpRight className="w-3.5 h-3.5 mr-1.5" />}
            Retirer vers mon compte
          </Button>
        ) : (
          <p className="text-[11px] text-slate-400 mt-1">
            {wallet.stripe_connect_status !== 'active'
              ? 'Liez votre compte bancaire pour retirer'
              : wallet.available_balance < wallet.minimum_payout
                ? `Min. ${fmt(wallet.minimum_payout, wallet.currency)} pour retirer`
                : 'Aucun fonds retirable'}
          </p>
        )}
      </div>
    </div>
  );
}

/* ─── Distribution Card ─────────────────────────────────────── */

function DistributionCard({ dist, currentUserId, onContest, onRefresh }) {
  const [expanded, setExpanded] = useState(false);
  const [contesting, setContesting] = useState(false);
  const [contestReason, setContestReason] = useState('');
  const [showContestForm, setShowContestForm] = useState(false);

  const statusCfg = DIST_STATUS[dist.status] || DIST_STATUS.pending_hold;
  const isNoShow = dist.no_show_user_id === currentUserId;
  const userBeneficiary = dist.beneficiaries?.find(b => b.user_id === currentUserId);
  const isBeneficiary = !!userBeneficiary;

  const handleContest = async () => {
    if (!contestReason.trim()) { toast.error('Veuillez indiquer un motif'); return; }
    setContesting(true);
    try {
      await onContest(dist.distribution_id, contestReason);
      setShowContestForm(false);
      setContestReason('');
    } finally {
      setContesting(false);
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-lg overflow-hidden" data-testid={`dist-${dist.distribution_id}`}>
      {/* Summary row */}
      <button
        className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-50 transition-colors"
        onClick={() => setExpanded(!expanded)}
        data-testid={`dist-toggle-${dist.distribution_id}`}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${isNoShow ? 'bg-red-50' : 'bg-emerald-50'}`}>
            {isNoShow
              ? <ArrowUpRight className="w-4 h-4 text-red-500" />
              : <ArrowDownLeft className="w-4 h-4 text-emerald-500" />}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-slate-900 truncate">
              {isNoShow ? 'Compensation capturée' : `Crédit reçu`}
            </p>
            <p className="text-xs text-slate-500 truncate">
              {dist.appointment_title || 'Rendez-vous'} — {fmtDateShort(dist.captured_at)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="text-right">
            <p className={`text-sm font-semibold ${isNoShow ? 'text-red-600' : 'text-emerald-600'}`}>
              {isNoShow ? `-${fmt(dist.capture_amount_cents, dist.capture_currency)}` : `+${fmt(userBeneficiary?.amount_cents || 0, dist.capture_currency)}`}
            </p>
            <span className={`inline-block text-[10px] font-medium px-1.5 py-0.5 rounded ${statusCfg.color}`}>
              {statusCfg.label}
            </span>
          </div>
          {expanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-slate-100 px-4 pb-4">
          {/* Status explanation */}
          <div className="flex items-start gap-2 mt-3 mb-4 p-3 bg-slate-50 rounded-lg">
            <Info className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-slate-600 leading-relaxed">{_buildExplanation(dist, isNoShow, isBeneficiary, userBeneficiary)}</p>
          </div>

          {/* Breakdown */}
          <p className="text-xs font-semibold text-slate-700 uppercase tracking-wide mb-2">Répartition</p>
          <div className="space-y-1.5 mb-4">
            {dist.beneficiaries?.map((b, i) => (
              <div key={b.beneficiary_id || i} className="flex items-center justify-between py-1.5 px-3 bg-slate-50 rounded" data-testid={`dist-benef-${b.role}-${i}`}>
                <div className="flex items-center gap-2">
                  <CircleDot className={`w-3 h-3 flex-shrink-0 ${b.user_id === currentUserId ? 'text-emerald-500' : 'text-slate-400'}`} />
                  <span className="text-xs text-slate-700">
                    {ROLE_LABELS[b.role] || b.role}
                    {b.user_id === currentUserId && <span className="text-emerald-600 font-medium ml-1">(vous)</span>}
                  </span>
                </div>
                <span className="text-xs font-semibold text-slate-900">{fmt(b.amount_cents, dist.capture_currency)}</span>
              </div>
            ))}
            <div className="flex items-center justify-between py-1.5 px-3 border border-slate-200 rounded font-medium">
              <span className="text-xs text-slate-700">Total capturé</span>
              <span className="text-xs font-bold text-slate-900">{fmt(dist.capture_amount_cents, dist.capture_currency)}</span>
            </div>
          </div>

          {/* Hold info */}
          {dist.status === 'pending_hold' && dist.hold_expires_at && (
            <div className="flex items-center gap-2 text-xs text-blue-600 mb-4 p-2 bg-blue-50 rounded">
              <Clock className="w-3.5 h-3.5 flex-shrink-0" />
              <span>Disponible le {fmtDate(dist.hold_expires_at)}</span>
            </div>
          )}

          {/* Contestation info */}
          {dist.contested && (
            <div className="flex items-start gap-2 text-xs text-orange-700 mb-4 p-2 bg-orange-50 rounded">
              <Flag className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">Signalement déposé le {fmtDate(dist.contested_at)}</p>
                {dist.contest_reason && <p className="mt-0.5 opacity-80">{dist.contest_reason}</p>}
                <p className="mt-1 opacity-70">La finalisation est suspendue en attente de résolution.</p>
              </div>
            </div>
          )}

          {/* Cancelled info */}
          {dist.status === 'cancelled' && (
            <div className="flex items-start gap-2 text-xs text-red-600 mb-4 p-2 bg-red-50 rounded">
              <XCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">Distribution annulée</p>
                {dist.cancel_reason && <p className="mt-0.5 opacity-80">{dist.cancel_reason}</p>}
              </div>
            </div>
          )}

          {/* Contest button (MVP) — only for no_show user, only during pending_hold */}
          {isNoShow && dist.status === 'pending_hold' && !dist.contested && (
            <div>
              {!showContestForm ? (
                <Button
                  size="sm"
                  variant="outline"
                  className="text-orange-600 border-orange-300 hover:bg-orange-50"
                  onClick={() => setShowContestForm(true)}
                  data-testid={`dist-contest-btn-${dist.distribution_id}`}
                >
                  <Flag className="w-3.5 h-3.5 mr-1.5" />
                  Signaler / Contester
                </Button>
              ) : (
                <div className="p-3 bg-orange-50 border border-orange-200 rounded-lg space-y-3" data-testid="contest-form">
                  <p className="text-xs text-orange-800 font-medium">
                    Votre signalement sera transmis pour examen. La finalisation sera suspendue le temps de la résolution.
                  </p>
                  <textarea
                    className="w-full text-sm border border-orange-300 rounded-md p-2 bg-white focus:outline-none focus:ring-2 focus:ring-orange-300"
                    rows={3}
                    placeholder="Décrivez le motif de votre contestation..."
                    value={contestReason}
                    onChange={e => setContestReason(e.target.value)}
                    data-testid="contest-reason-input"
                  />
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-orange-700 border-orange-300"
                      onClick={handleContest}
                      disabled={contesting || !contestReason.trim()}
                      data-testid="contest-submit-btn"
                    >
                      {contesting ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Flag className="w-3.5 h-3.5 mr-1.5" />}
                      Confirmer le signalement
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => { setShowContestForm(false); setContestReason(''); }}>
                      Annuler
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function _buildExplanation(dist, isNoShow, isBeneficiary, userBeneficiary) {
  const amount = fmt(dist.capture_amount_cents, dist.capture_currency);

  if (dist.status === 'cancelled') {
    return `Cette distribution de ${amount} a été annulée. Les fonds crédités ont été remboursés.`;
  }
  if (dist.status === 'contested') {
    if (isNoShow) return `Votre compensation de ${amount} a fait l'objet d'un signalement. La distribution est suspendue en attente de résolution par l'équipe NLYT.`;
    return `Cette distribution est suspendue suite à un signalement. Les fonds restent en attente dans votre wallet.`;
  }
  if (dist.status === 'completed') {
    if (isNoShow) return `Votre compensation de ${amount} a été distribuée aux bénéficiaires. La période de vérification est terminée.`;
    return `Les fonds de ${fmt(userBeneficiary?.amount_cents || 0, dist.capture_currency)} sont maintenant disponibles dans votre wallet.`;
  }
  if (dist.status === 'pending_hold') {
    if (isNoShow) return `Votre compensation de ${amount} a été capturée. Les fonds sont en période de vérification (15 jours) avant distribution définitive. Vous pouvez contester pendant cette période.`;
    return `Vous avez reçu un crédit de ${fmt(userBeneficiary?.amount_cents || 0, dist.capture_currency)} suite à une absence. Ce montant passera en disponible après la période de vérification de 15 jours.`;
  }
  return `Distribution de ${amount} en cours de traitement.`;
}

/* ─── Distributions Section ─────────────────────────────────── */

function DistributionsSection({ distributions, currentUserId, onContest, onRefresh }) {
  if (!distributions || distributions.length === 0) return null;

  const active = distributions.filter(d => d.status === 'pending_hold' || d.status === 'contested');
  const past = distributions.filter(d => d.status === 'completed' || d.status === 'cancelled' || d.status === 'distributing');

  return (
    <div className="mb-8" data-testid="distributions-section">
      {active.length > 0 && (
        <>
          <h2 className="text-base font-semibold text-slate-900 mb-3 flex items-center gap-2">
            <Scale className="w-4 h-4 text-blue-500" />
            Distributions en cours
          </h2>
          <div className="space-y-2 mb-6">
            {active.map(d => (
              <DistributionCard key={d.distribution_id} dist={d} currentUserId={currentUserId} onContest={onContest} onRefresh={onRefresh} />
            ))}
          </div>
        </>
      )}
      {past.length > 0 && (
        <>
          <h2 className="text-base font-semibold text-slate-900 mb-3">Distributions passées</h2>
          <div className="space-y-2">
            {past.map(d => (
              <DistributionCard key={d.distribution_id} dist={d} currentUserId={currentUserId} onContest={onContest} onRefresh={onRefresh} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/* ─── Impact Section ────────────────────────────────────────── */

function ImpactSection({ impact }) {
  const [showDetail, setShowDetail] = useState(false);

  if (!impact || impact.total_charity_cents === 0) return null;

  return (
    <div className="mb-8" data-testid="impact-section">
      <div className="bg-gradient-to-br from-rose-50 to-amber-50 border border-rose-200 rounded-lg p-5">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-9 h-9 rounded-full bg-rose-100 flex items-center justify-center flex-shrink-0">
            <Heart className="w-4.5 h-4.5 text-rose-500" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-900">Vos gestes solidaires</p>
            <p className="text-xs text-slate-500">Contributions aux associations via NLYT</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="bg-white/70 rounded-lg p-3 text-center">
            <p className="text-lg font-bold text-rose-600" data-testid="impact-total">
              {fmt(impact.total_charity_cents, impact.currency)}
            </p>
            <p className="text-[10px] text-slate-500 uppercase tracking-wide">Total contribué</p>
          </div>
          <div className="bg-white/70 rounded-lg p-3 text-center">
            <p className="text-lg font-bold text-slate-800" data-testid="impact-distributions">
              {impact.distributions_count}
            </p>
            <p className="text-[10px] text-slate-500 uppercase tracking-wide">Distribution{impact.distributions_count > 1 ? 's' : ''}</p>
          </div>
          <div className="bg-white/70 rounded-lg p-3 text-center">
            <p className="text-lg font-bold text-slate-800" data-testid="impact-events">
              {impact.events_count}
            </p>
            <p className="text-[10px] text-slate-500 uppercase tracking-wide">Evénement{impact.events_count > 1 ? 's' : ''}</p>
          </div>
        </div>

        {/* By association */}
        {impact.by_association?.length > 0 && (
          <div className="space-y-1.5 mb-3">
            {impact.by_association.map((a) => (
              <div key={a.association_id} className="flex items-center justify-between bg-white/50 rounded px-3 py-2" data-testid={`impact-assoc-${a.association_id}`}>
                <div className="flex items-center gap-2">
                  <Heart className="w-3 h-3 text-rose-400 flex-shrink-0" />
                  <span className="text-xs text-slate-700">{a.name || `Association ${a.association_id.slice(0, 8)}`}</span>
                </div>
                <span className="text-xs font-semibold text-slate-900">{fmt(a.total_cents, impact.currency)}</span>
              </div>
            ))}
          </div>
        )}

        {/* Detail toggle */}
        {impact.contributions?.length > 0 && (
          <>
            <button
              className="text-xs text-rose-600 hover:text-rose-700 font-medium flex items-center gap-1"
              onClick={() => setShowDetail(!showDetail)}
              data-testid="impact-detail-toggle"
            >
              {showDetail ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              {showDetail ? 'Masquer le détail' : 'Voir le détail par événement'}
            </button>
            {showDetail && (
              <div className="mt-3 space-y-1.5" data-testid="impact-contributions">
                {impact.contributions.map((c, i) => (
                  <div key={c.distribution_id + i} className="flex items-center justify-between bg-white/60 rounded px-3 py-2">
                    <div className="min-w-0">
                      <p className="text-xs text-slate-700 truncate">{c.appointment_title || 'RDV'}</p>
                      <p className="text-[10px] text-slate-400">{fmtDateShort(c.created_at)}</p>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="text-xs font-semibold text-rose-600">{fmt(c.amount_cents, c.currency)}</span>
                      {c.status === 'pending_hold' && (
                        <span className="text-[9px] px-1 py-0.5 rounded bg-blue-100 text-blue-600">en attente</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/* ─── Business Type Labels ───────────────────────────────────── */

const BUSINESS_TYPE_LABELS = {
  individual: 'Particulier / Indépendant',
  company: 'Société / Organisation',
};

/* ─── Profile Type Selector ─────────────────────────────────── */

function ProfileTypeSelector({ onSelect, loading }) {
  return (
    <div className="border border-slate-200 rounded-lg p-5 mb-8 bg-white" data-testid="profile-type-selector">
      <div className="flex items-center gap-2 mb-1">
        <Banknote className="w-4.5 h-4.5 text-slate-700" />
        <h3 className="text-sm font-semibold text-slate-900">Lier votre compte bancaire</h3>
      </div>
      <p className="text-xs text-slate-500 mb-5">Quel type de profil correspond à votre situation ?</p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <button
          onClick={() => onSelect('individual')}
          disabled={loading}
          className="group relative border-2 border-slate-200 hover:border-slate-900 rounded-lg p-4 text-left transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-slate-900 focus:ring-offset-2"
          data-testid="select-individual-btn"
        >
          <div className="flex items-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0 group-hover:bg-blue-100 transition-colors">
              <svg className="w-4.5 h-4.5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">Particulier / Indépendant</p>
              <p className="text-[11px] text-slate-500">Personne physique, auto-entrepreneur, freelance</p>
            </div>
          </div>
        </button>

        <button
          onClick={() => onSelect('company')}
          disabled={loading}
          className="group relative border-2 border-slate-200 hover:border-slate-900 rounded-lg p-4 text-left transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-slate-900 focus:ring-offset-2"
          data-testid="select-company-btn"
        >
          <div className="flex items-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-full bg-violet-50 flex items-center justify-center flex-shrink-0 group-hover:bg-violet-100 transition-colors">
              <svg className="w-4.5 h-4.5 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">Société / Organisation</p>
              <p className="text-[11px] text-slate-500">SARL, SAS, association, fondation</p>
            </div>
          </div>
        </button>
      </div>
    </div>
  );
}

/* ─── Connect Status Card ───────────────────────────────────── */

function ConnectStatusCard({ connectStatus, onOnboard, onDashboard, onRefresh, onboarding, onPayout, canPayout, onChangeType }) {
  const status = connectStatus?.connect_status || 'not_started';
  const businessType = connectStatus?.business_type;
  const cfg = CONNECT_STATUS_CONFIG[status] || CONNECT_STATUS_CONFIG.not_started;
  const StatusIcon = cfg.icon;

  return (
    <div className={`border rounded-lg p-4 mb-8 ${cfg.bg}`} data-testid="connect-status-card">
      <div className="flex items-start gap-3">
        <StatusIcon className={`w-5 h-5 mt-0.5 flex-shrink-0 ${cfg.color}`} />
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className={`text-sm font-semibold ${cfg.color}`} data-testid="connect-status-label">{cfg.label}</h3>
            {businessType && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-100 text-slate-600" data-testid="connect-business-type-badge">
                {BUSINESS_TYPE_LABELS[businessType] || businessType}
              </span>
            )}
          </div>
          <p className="text-xs mt-1 opacity-80">{cfg.description}</p>
          {status === 'active' && (
            <p className="text-[11px] text-slate-400 mt-1">Votre argent est stocké dans votre wallet NLYT. Ce compte vous permet de le transférer vers votre banque.</p>
          )}
          <div className="mt-3 flex items-center gap-3 flex-wrap">
            {status === 'active' ? (
              <>
                <Button
                  size="sm"
                  className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs"
                  onClick={canPayout ? onPayout : undefined}
                  disabled={!canPayout}
                  data-testid="connect-payout-btn"
                >
                  <ArrowUpRight className="w-3.5 h-3.5 mr-1.5" />
                  Retirer mes fonds
                </Button>
                <button
                  onClick={onDashboard}
                  className="text-xs text-slate-500 hover:text-slate-700 underline underline-offset-2 transition-colors"
                  data-testid="stripe-dashboard-btn"
                >
                  {cfg.actionLabel} →
                </button>
              </>
            ) : (
              <Button size="sm" onClick={onOnboard} disabled={onboarding} data-testid="connect-onboard-btn">
                {onboarding ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Banknote className="w-3.5 h-3.5 mr-1.5" />}
                {cfg.actionLabel}
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={onRefresh} data-testid="refresh-wallet-btn"><RefreshCw className="w-3.5 h-3.5" /></Button>
          </div>
          {/* Change profile type link */}
          {businessType && (
            <button
              onClick={onChangeType}
              className="mt-3 text-[11px] text-slate-400 hover:text-slate-600 underline underline-offset-2 transition-colors"
              data-testid="change-profile-type-btn"
            >
              Modifier mon type de profil
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Change Profile Type Modal ────────────────────────────── */

function ChangeProfileTypeModal({ currentType, onConfirm, onCancel, loading, connectStatus }) {
  const isActive = connectStatus === 'active';
  const otherType = currentType === 'individual' ? 'company' : 'individual';

  return (
    <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-lg" data-testid="change-type-modal">
      <div className="flex items-start gap-2 mb-3">
        <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
        <div>
          <p className="text-sm font-medium text-amber-900">Modifier votre type de profil</p>
          <p className="text-xs text-amber-700 mt-1">
            Profil actuel : <span className="font-semibold">{BUSINESS_TYPE_LABELS[currentType]}</span>
          </p>
        </div>
      </div>

      {isActive && (
        <div className="flex items-start gap-2 p-3 bg-white/70 rounded-lg mb-3">
          <Info className="w-3.5 h-3.5 text-amber-600 mt-0.5 flex-shrink-0" />
          <p className="text-[11px] text-amber-800 leading-relaxed">
            Votre compte bancaire est actuellement actif. Le changement de profil nécessitera de <strong>relancer la vérification Stripe</strong> avec le nouveau type. Votre historique de transactions dans NLYT sera conservé.
          </p>
        </div>
      )}

      <p className="text-xs text-amber-700 mb-3">
        Nouveau profil : <span className="font-semibold">{BUSINESS_TYPE_LABELS[otherType]}</span>
      </p>

      <div className="flex flex-col sm:flex-row gap-2">
        <Button
          size="sm"
          className="bg-amber-600 hover:bg-amber-700 text-white min-h-[44px] sm:min-h-0"
          onClick={() => onConfirm(otherType)}
          disabled={loading}
          data-testid="confirm-type-change-btn"
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
          Confirmer le changement
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel} className="min-h-[44px] sm:min-h-0" data-testid="cancel-type-change-btn">
          Annuler
        </Button>
      </div>
    </div>
  );
}

/* ─── Payout Section ────────────────────────────────────────── */

const PAYOUT_STATUS = {
  pending: { label: 'En attente', color: 'bg-yellow-100 text-yellow-700' },
  processing: { label: 'En cours', color: 'bg-blue-100 text-blue-700' },
  completed: { label: 'Effectué', color: 'bg-emerald-100 text-emerald-700' },
  failed: { label: 'Échoué', color: 'bg-red-100 text-red-700' },
};

function PayoutHistory({ payouts }) {
  if (!payouts || payouts.length === 0) return null;

  return (
    <div className="mb-8" data-testid="payout-history">
      <h2 className="text-base font-semibold text-slate-900 mb-3">Retraits</h2>
      <div className="bg-white border border-slate-200 rounded-lg divide-y divide-slate-100">
        {payouts.map((p) => {
          const sCfg = PAYOUT_STATUS[p.status] || PAYOUT_STATUS.pending;
          return (
            <div key={p.payout_id} className="p-3 flex items-center justify-between" data-testid={`payout-${p.payout_id}`}>
              <div className="flex items-center gap-3">
                <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center flex-shrink-0">
                  <ArrowUpRight className="w-3.5 h-3.5 text-slate-500" />
                </div>
                <div>
                  <p className="text-xs font-medium text-slate-900">Retrait vers compte bancaire</p>
                  <p className="text-[10px] text-slate-400">{fmtDateShort(p.requested_at)}{p.dev_mode ? ' · DEV' : ''}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <p className="text-xs font-semibold text-slate-900">{fmt(p.amount_cents, p.currency)}</p>
                <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded ${sCfg.color}`}>{sCfg.label}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Transaction History ───────────────────────────────────── */

const TX_TYPE_LABELS = {
  credit_pending: { label: 'Crédit en attente', icon: ArrowDownLeft, color: 'text-blue-600' },
  credit_available: { label: 'Crédit disponible', icon: ArrowDownLeft, color: 'text-emerald-600' },
  debit_payout: { label: 'Retrait', icon: ArrowUpRight, color: 'text-red-600' },
  debit_refund: { label: 'Remboursement', icon: ArrowUpRight, color: 'text-orange-600' },
};

function TransactionHistory({ transactions, txTotal }) {
  return (
    <div data-testid="transaction-history">
      <h2 className="text-base font-semibold text-slate-900 mb-3">Historique des transactions</h2>
      {transactions.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-lg p-8 text-center" data-testid="no-transactions">
          <Clock className="w-7 h-7 text-slate-300 mx-auto mb-2" />
          <p className="text-sm text-slate-500">Aucune transaction pour le moment</p>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-lg divide-y divide-slate-100">
          {transactions.map((tx) => {
            const txCfg = TX_TYPE_LABELS[tx.type] || TX_TYPE_LABELS.credit_available;
            const TxIcon = txCfg.icon;
            const isCredit = tx.type?.startsWith('credit');
            return (
              <div key={tx.transaction_id} className="p-3 flex items-center justify-between" data-testid={`tx-${tx.transaction_id}`}>
                <div className="flex items-center gap-3">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${isCredit ? 'bg-emerald-50' : 'bg-red-50'}`}>
                    <TxIcon className={`w-3.5 h-3.5 ${txCfg.color}`} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-slate-900">{txCfg.label}</p>
                    <p className="text-[11px] text-slate-500 truncate">{tx.description || '—'}</p>
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className={`text-xs font-semibold ${isCredit ? 'text-emerald-600' : 'text-red-600'}`}>
                    {isCredit ? '+' : '-'}{fmt(tx.amount, tx.currency)}
                  </p>
                  <p className="text-[10px] text-slate-400">{fmtDateShort(tx.created_at)}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
      {txTotal > 20 && (
        <p className="text-[11px] text-slate-400 text-center mt-2">{txTotal} transactions au total</p>
      )}
    </div>
  );
}

/* ─── Main Page ─────────────────────────────────────────────── */

export default function WalletPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [wallet, setWallet] = useState(null);
  const [connectStatus, setConnectStatus] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [txTotal, setTxTotal] = useState(0);
  const [distributions, setDistributions] = useState([]);
  const [impact, setImpact] = useState(null);
  const [payouts, setPayouts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [onboarding, setOnboarding] = useState(false);
  const [currentUserId, setCurrentUserId] = useState(null);
  const [payoutLoading, setPayoutLoading] = useState(false);
  const [showPayoutConfirm, setShowPayoutConfirm] = useState(false);
  const [showChangeType, setShowChangeType] = useState(false);
  const [changeTypeLoading, setChangeTypeLoading] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [walletRes, connectRes, txRes, distRes, impactRes, payoutsRes] = await Promise.all([
        walletAPI.get(),
        connectAPI.getStatus(),
        walletAPI.getTransactions(20, 0),
        walletAPI.getDistributions(50, 0),
        walletAPI.getImpact(),
        walletAPI.getPayouts(20, 0),
      ]);
      setWallet(walletRes.data);
      setConnectStatus(connectRes.data);
      setTransactions(txRes.data.transactions || []);
      setTxTotal(txRes.data.total || 0);
      setDistributions(distRes.data.distributions || []);
      setImpact(impactRes.data);
      setPayouts(payoutsRes.data.payouts || []);

      if (connectRes.data?.user_id) setCurrentUserId(connectRes.data.user_id);
    } catch {
      toast.error("Erreur lors du chargement du wallet");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const connectParam = searchParams.get('connect');
    if (connectParam === 'complete') {
      toast.success("Vérification soumise — en attente de confirmation Stripe");
      setSearchParams({}, { replace: true });
    } else if (connectParam === 'refresh') {
      toast.info("Le lien a expiré, génération d'un nouveau lien...");
      setSearchParams({}, { replace: true });
      handleOnboard();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleOnboard = async (businessType) => {
    const typeToUse = businessType || connectStatus?.business_type || 'individual';
    setOnboarding(true);
    try {
      const res = await connectAPI.onboard(typeToUse);
      if (res.data.onboarding_url) { window.location.href = res.data.onboarding_url; return; }
      toast.success(res.data.message || "Compte déjà actif");
      await fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur lors de l'onboarding");
    } finally { setOnboarding(false); }
  };

  const handleProfileSelect = (businessType) => {
    handleOnboard(businessType);
  };

  const handleChangeType = async (newType) => {
    setChangeTypeLoading(true);
    try {
      await connectAPI.reset(newType);
      toast.success("Profil modifié. Relancez la liaison de votre compte.");
      setShowChangeType(false);
      await fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur lors du changement de profil");
    } finally { setChangeTypeLoading(false); }
  };

  const handleDashboard = async () => {
    try {
      const res = await connectAPI.getDashboard();
      const url = res.data.dashboard_url;
      if (url && url.includes('dev_dashboard=true')) {
        toast.info("Gestion du compte bancaire non disponible en mode développement");
        return;
      }
      if (url) window.open(url, '_blank');
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur lors de l'accès à la gestion du compte");
    }
  };

  const handleContest = async (distributionId, reason) => {
    try {
      await walletAPI.contestDistribution(distributionId, reason);
      toast.success("Signalement enregistré. La distribution est suspendue.");
      await fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur lors du signalement");
    }
  };

  const handlePayout = async () => {
    setPayoutLoading(true);
    setShowPayoutConfirm(false);
    try {
      const res = await walletAPI.requestPayout(null); // Full withdrawal
      const msg = res.data.dev_mode
        ? `[DEV] Retrait simulé : ${fmt(res.data.amount_cents)}`
        : `Retrait de ${fmt(res.data.amount_cents)} en cours`;
      toast.success(msg);
      await fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erreur lors du retrait");
    } finally {
      setPayoutLoading(false);
    }
  };

  if (loading) {
    return (
      <SettingsPageLayout title="Wallet" description="Vos fonds internes, distributions reçues et compte de paiement">
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
          <span className="ml-3 text-slate-500">Chargement...</span>
        </div>
      </SettingsPageLayout>
    );
  }

  return (
    <SettingsPageLayout
      title="Wallet"
      description="Vos fonds internes, distributions reçues et compte de paiement"
    >

        <BalanceCards wallet={wallet} onPayout={() => setShowPayoutConfirm(true)} payoutLoading={payoutLoading} />

        {/* Profile type selector — shown when no business_type chosen yet AND no account exists */}
        {connectStatus?.connect_status === 'not_started' && !connectStatus?.business_type ? (
          <ProfileTypeSelector onSelect={handleProfileSelect} loading={onboarding} />
        ) : (
          <>
            {/* Change profile type modal */}
            {showChangeType && connectStatus?.business_type && (
              <ChangeProfileTypeModal
                currentType={connectStatus.business_type}
                onConfirm={handleChangeType}
                onCancel={() => setShowChangeType(false)}
                loading={changeTypeLoading}
                connectStatus={connectStatus?.connect_status}
              />
            )}

            <ConnectStatusCard
              connectStatus={connectStatus}
              onOnboard={() => handleOnboard()}
              onDashboard={handleDashboard}
              onRefresh={fetchData}
              onboarding={onboarding}
              onPayout={() => setShowPayoutConfirm(true)}
              canPayout={wallet?.can_payout}
              onChangeType={() => setShowChangeType(true)}
            />
          </>
        )}

        {/* Payout Confirmation Modal */}
        {showPayoutConfirm && wallet && (
          <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-lg" data-testid="payout-confirm-modal">
            <p className="text-sm font-medium text-emerald-900 mb-2">Confirmer le retrait</p>
            <p className="text-xs text-emerald-700 mb-3">
              Vous allez retirer <span className="font-bold">{fmt(wallet.available_balance, wallet.currency)}</span> vers votre compte bancaire.
              Ce transfert est irréversible.
            </p>
            <div className="flex flex-col sm:flex-row gap-2">
              <Button
                size="sm"
                className="bg-emerald-600 hover:bg-emerald-700 text-white min-h-[44px] sm:min-h-0"
                onClick={handlePayout}
                disabled={payoutLoading}
                data-testid="payout-confirm-btn"
              >
                {payoutLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <ArrowUpRight className="w-3.5 h-3.5 mr-1.5" />}
                Confirmer le retrait
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setShowPayoutConfirm(false)} className="min-h-[44px] sm:min-h-0">Annuler</Button>
            </div>
          </div>
        )}

        <DistributionsSection
          distributions={distributions}
          currentUserId={currentUserId}
          onContest={handleContest}
          onRefresh={fetchData}
        />

        <ImpactSection impact={impact} />

        <PayoutHistory payouts={payouts} />

        <TransactionHistory transactions={transactions} txTotal={txTotal} />
    </SettingsPageLayout>
  );
}
