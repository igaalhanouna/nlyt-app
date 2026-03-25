import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Heart, Shield, ArrowRight, Loader2, Info, Clock,
  Building2, ChevronDown, CalendarCheck, TrendingUp,
} from 'lucide-react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

function fmt(cents, currency = 'eur') {
  if (!cents) return '0 €';
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency', currency, minimumFractionDigits: 0, maximumFractionDigits: 0,
  }).format(cents / 100);
}

function fmtPrecise(cents, currency = 'eur') {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency }).format(cents / 100);
}

function fmtDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: 'numeric', month: 'short', year: 'numeric',
  });
}

/* ─── KPI Card ── */
function StatCard({ icon: Icon, value, label, accent = false, testId }) {
  return (
    <div
      className={`rounded-xl p-6 text-center ${
        accent
          ? 'bg-rose-500/10 border border-rose-500/20'
          : 'bg-white/[0.03] border border-white/5'
      }`}
      data-testid={testId}
    >
      <Icon className={`w-5 h-5 mx-auto mb-3 ${accent ? 'text-rose-400' : 'text-slate-500'}`} />
      <p
        className={`text-3xl font-bold tracking-tight ${accent ? 'text-rose-300' : 'text-white'}`}
        style={{ fontVariantNumeric: 'tabular-nums' }}
      >
        {value}
      </p>
      <p className={`text-sm mt-1 ${accent ? 'text-rose-400/70' : 'text-slate-500'}`}>{label}</p>
    </div>
  );
}

/* ─── Association Row ── */
function AssociationRow({ association, rank }) {
  const name = association.name || `Association #${rank}`;
  return (
    <div
      className="flex items-center justify-between py-4 px-5 bg-white/[0.03] rounded-lg border border-white/5"
      data-testid={`assoc-row-${association.association_id}`}
    >
      <div className="flex items-center gap-4">
        <div className="w-9 h-9 rounded-full bg-rose-500/10 flex items-center justify-center flex-shrink-0">
          <Heart className="w-4 h-4 text-rose-400" />
        </div>
        <div>
          <p className="text-sm font-medium text-white">{name}</p>
          <p className="text-xs text-slate-500">
            {association.distributions_count} geste{association.distributions_count > 1 ? 's' : ''} solidaire{association.distributions_count > 1 ? 's' : ''}
            {' · '}
            {association.events_count} engagement{association.events_count > 1 ? 's' : ''}
          </p>
        </div>
      </div>
      <p className="text-sm font-bold text-rose-300 tabular-nums">{fmtPrecise(association.total_cents)}</p>
    </div>
  );
}

/* ─── Contribution Row ── */
function ContributionRow({ contribution }) {
  return (
    <div
      className="flex items-center justify-between py-3 px-4 bg-white/[0.03] rounded-lg border border-white/5"
      data-testid={`contribution-${contribution.distribution_id}`}
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center flex-shrink-0">
          <CalendarCheck className="w-3.5 h-3.5 text-slate-500" />
        </div>
        <div className="min-w-0">
          <p className="text-sm text-white truncate">{contribution.appointment_title}</p>
          <p className="text-xs text-slate-500">
            {contribution.association_name && (
              <span className="text-rose-400">{contribution.association_name} · </span>
            )}
            {fmtDate(contribution.created_at)}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0 ml-3">
        <span className="text-sm font-semibold text-white tabular-nums">
          {fmtPrecise(contribution.amount_cents)}
        </span>
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
          contribution.status === 'completed'
            ? 'bg-rose-500/10 text-rose-400'
            : 'bg-amber-500/10 text-amber-400'
        }`}>
          {contribution.status === 'completed' ? 'confirmé' : 'en attente'}
        </span>
      </div>
    </div>
  );
}

/* ─── Transparency Block ── */
function TransparencyBlock() {
  return (
    <div
      className="bg-white/[0.03] border border-white/10 rounded-xl p-6"
      data-testid="transparency-block"
    >
      <div className="flex gap-3">
        <Info className="w-5 h-5 text-slate-500 flex-shrink-0 mt-0.5" />
        <div>
          <h3 className="text-sm font-semibold text-white mb-2">
            Transparence sur les montants
          </h3>
          <p className="text-sm text-slate-400 leading-relaxed">
            Les montants affichés sur cette page sont <strong className="text-white">reversés à des associations</strong> et accumulés
            sur la plateforme NLYT. Le transfert vers les associations n'a pas encore eu lieu.
          </p>
          <p className="text-sm text-slate-400 leading-relaxed mt-2">
            Le <strong className="text-white">reversement automatique</strong> vers les associations partenaires sera implémenté dans une
            prochaine version de la plateforme. En attendant, chaque euro est comptabilisé et traçable.
          </p>
          <div className="flex items-center gap-1.5 mt-3">
            <Clock className="w-3.5 h-3.5 text-slate-500" />
            <span className="text-xs text-slate-500 font-medium">Reversement automatique — bientôt disponible</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Main Page ── */
export default function ImpactPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    axios.get(`${API}/api/impact/charity?limit=10`)
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const loadMore = useCallback(async () => {
    if (!data?.contributions?.has_more || loadingMore) return;
    setLoadingMore(true);
    try {
      const nextSkip = data.contributions.skip + data.contributions.limit;
      const res = await axios.get(`${API}/api/impact/charity?limit=10&skip=${nextSkip}`);
      setData(prev => ({
        ...prev,
        contributions: {
          ...res.data.contributions,
          items: [...prev.contributions.items, ...res.data.contributions.items],
        },
      }));
    } catch {
      // silently fail
    } finally {
      setLoadingMore(false);
    }
  }, [data, loadingMore]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0B] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-slate-500" />
      </div>
    );
  }

  const hasData = data && data.total_charity_cents > 0;
  const contributions = data?.contributions?.items || [];
  const associations = data?.associations || [];

  return (
    <div className="min-h-screen bg-[#0A0A0B] text-white">
      {/* ── Nav ── */}
      <nav className="border-b border-white/5">
        <div className="max-w-4xl mx-auto px-6 py-5 flex items-center justify-between">
          <Link to="/" className="text-xl font-bold tracking-tight text-white">NLYT</Link>
          <Link to="/signin" className="text-sm text-slate-400 hover:text-white transition-colors">Connexion</Link>
        </div>
      </nav>

      {/* ── Hero ── */}
      <div className="border-b border-white/5">
        <div className="max-w-4xl mx-auto px-6 py-16 sm:py-24 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-medium text-slate-400 mb-8">
            <Shield className="w-3.5 h-3.5" />
            Données auditables et traçables
          </div>
          <h1
            className="text-4xl sm:text-5xl font-bold tracking-tight mb-4"
            data-testid="impact-hero-title"
          >
            Quand le temps perdu fait du bien
          </h1>
          <p className="text-lg text-slate-400 max-w-xl mx-auto">
            Chaque engagement non tenu sur NLYT génère des gestes solidaires
            reversés à des associations. Transparence totale.
          </p>
        </div>
      </div>

      {/* ── Content ── */}
      <div className="max-w-4xl mx-auto px-6 py-12">
        {hasData ? (
          <>
            {/* KPIs */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4" data-testid="charity-kpis">
              <StatCard
                icon={Heart}
                value={fmt(data.total_charity_cents)}
                label="Reversés à des associations"
                accent
                testId="kpi-total-charity"
              />
              <StatCard
                icon={Building2}
                value={associations.length.toString()}
                label={associations.length > 1 ? 'Associations soutenues' : 'Association soutenue'}
                testId="kpi-associations-count"
              />
              <StatCard
                icon={CalendarCheck}
                value={data.total_appointments?.toLocaleString('fr-FR') || '0'}
                label="Engagements totaux"
                testId="kpi-total-appointments"
              />
              <StatCard
                icon={TrendingUp}
                value={data.total_no_show_contributions?.toLocaleString('fr-FR') || '0'}
                label="Absences transformées en gestes solidaires"
                testId="kpi-no-show-contributions"
              />
            </div>

            {/* Transparency Block */}
            <div className="mt-10">
              <TransparencyBlock />
            </div>

            {/* Associations */}
            {associations.length > 0 && (
              <div className="mt-12" data-testid="associations-section">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-base font-semibold text-white" data-testid="associations-title">
                    Associations bénéficiaires
                  </h2>
                  <span className="text-xs text-slate-500">
                    {associations.length} association{associations.length > 1 ? 's' : ''}
                  </span>
                </div>
                <div className="space-y-2" data-testid="associations-list">
                  {associations.map((a, i) => (
                    <AssociationRow key={a.association_id} association={a} rank={i + 1} />
                  ))}
                </div>
                <p className="text-xs text-slate-500 mt-3 text-center">
                  Total reversé aux associations : <span className="font-semibold text-rose-400">{fmtPrecise(data.total_charity_cents)}</span>
                </p>
              </div>
            )}

            {/* Contributions History */}
            <div className="mt-12 mb-6" data-testid="contributions-section">
              <h2 className="text-base font-semibold text-white mb-4" data-testid="contributions-title">
                Historique des gestes solidaires
              </h2>
              {contributions.length > 0 ? (
                <div className="space-y-2">
                  {contributions.map((c) => (
                    <ContributionRow key={c.distribution_id} contribution={c} />
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-500">Aucun geste solidaire enregistré pour le moment.</p>
              )}

              {data.contributions?.has_more && (
                <div className="mt-6 text-center">
                  <button
                    onClick={loadMore}
                    disabled={loadingMore}
                    className="inline-flex items-center gap-2 px-4 py-2 text-sm text-slate-400 bg-white/[0.03] border border-white/10 rounded-lg hover:bg-white/[0.06] transition-colors disabled:opacity-50"
                    data-testid="load-more-contributions"
                  >
                    {loadingMore ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <ChevronDown className="w-4 h-4" />
                    )}
                    Voir plus
                  </button>
                  <p className="text-xs text-slate-600 mt-1">
                    {contributions.length} sur {data.contributions.total}
                  </p>
                </div>
              )}
            </div>

            {/* How it works */}
            <div className="bg-white/[0.03] border border-white/5 rounded-xl p-8 mb-10" data-testid="how-it-works">
              <h2 className="text-base font-semibold text-white mb-8 text-center">Comment ça fonctionne</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
                <div className="text-center">
                  <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center mx-auto mb-3">
                    <span className="text-sm font-bold text-white">1</span>
                  </div>
                  <p className="text-sm font-medium text-white mb-1">Garantie d'engagement</p>
                  <p className="text-xs text-slate-500">
                    Chaque participant dépose une garantie lors de sa confirmation.
                  </p>
                </div>
                <div className="text-center">
                  <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center mx-auto mb-3">
                    <span className="text-sm font-bold text-white">2</span>
                  </div>
                  <p className="text-sm font-medium text-white mb-1">Absence constatée</p>
                  <p className="text-xs text-slate-500">
                    En cas d'absence, la garantie est capturée. Une part devient un geste solidaire.
                  </p>
                </div>
                <div className="text-center">
                  <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center mx-auto mb-3">
                    <span className="text-sm font-bold text-white">3</span>
                  </div>
                  <p className="text-sm font-medium text-white mb-1">Gestes solidaires cumulés</p>
                  <p className="text-xs text-slate-500">
                    Les montants reversés sont comptabilisés et traçables. Le reversement automatique sera bientôt disponible.
                  </p>
                </div>
              </div>
            </div>
          </>
        ) : (
          /* ── Empty State ── */
          <div className="bg-white/[0.03] border border-white/5 rounded-xl p-12 text-center" data-testid="charity-empty">
            <Heart className="w-10 h-10 text-rose-400/30 mx-auto mb-4" />
            <p className="text-lg font-medium text-white mb-2">Les gestes solidaires commencent ici</p>
            <p className="text-sm text-slate-500 max-w-md mx-auto mb-6">
              Dès que des garanties d'engagement seront traitées avec une part solidaire,
              les montants reversés aux associations apparaîtront ici.
            </p>
            <TransparencyBlock />
          </div>
        )}
      </div>

      {/* ── Footer ── */}
      <div className="border-t border-white/5 py-8">
        <div className="max-w-4xl mx-auto px-6 flex items-center justify-between">
          <p className="text-xs text-slate-600">
            {data?.refreshed_at
              ? `Dernière mise à jour : ${new Date(data.refreshed_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })}`
              : ''}
          </p>
          <Link to="/" className="text-xs text-slate-500 hover:text-white flex items-center gap-1 transition-colors">
            nlyt.app <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </div>
    </div>
  );
}
