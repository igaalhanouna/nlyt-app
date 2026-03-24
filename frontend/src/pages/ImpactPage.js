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

/* ─── KPI Card ────────────────────────────────────────── */
function StatCard({ icon: Icon, value, label, accent = false, testId }) {
  return (
    <div
      className={`rounded-xl p-6 text-center ${accent ? 'bg-emerald-700 text-white' : 'bg-white border border-slate-200'}`}
      data-testid={testId}
    >
      <Icon className={`w-5 h-5 mx-auto mb-3 ${accent ? 'text-emerald-200' : 'text-slate-400'}`} />
      <p
        className={`text-3xl font-bold tracking-tight ${accent ? 'text-white' : 'text-slate-900'}`}
        style={{ fontVariantNumeric: 'tabular-nums' }}
      >
        {value}
      </p>
      <p className={`text-sm mt-1 ${accent ? 'text-emerald-200' : 'text-slate-500'}`}>{label}</p>
    </div>
  );
}

/* ─── Association Row ─────────────────────────────────── */
function AssociationRow({ association, rank }) {
  const name = association.name || `Association #${rank}`;
  return (
    <div
      className="flex items-center justify-between py-4 px-5 bg-white rounded-lg border border-slate-100"
      data-testid={`assoc-row-${association.association_id}`}
    >
      <div className="flex items-center gap-4">
        <div className="w-9 h-9 rounded-full bg-emerald-50 flex items-center justify-center flex-shrink-0">
          <Heart className="w-4 h-4 text-emerald-600" />
        </div>
        <div>
          <p className="text-sm font-medium text-slate-900">{name}</p>
          <p className="text-xs text-slate-500">
            {association.distributions_count} contribution{association.distributions_count > 1 ? 's' : ''}
            {' · '}
            {association.events_count} engagement{association.events_count > 1 ? 's' : ''}
          </p>
        </div>
      </div>
      <p className="text-sm font-bold text-slate-900 tabular-nums">{fmtPrecise(association.total_cents)}</p>
    </div>
  );
}

/* ─── Contribution Row ────────────────────────────────── */
function ContributionRow({ contribution }) {
  return (
    <div
      className="flex items-center justify-between py-3 px-4 bg-white rounded-lg border border-slate-100"
      data-testid={`contribution-${contribution.distribution_id}`}
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-8 h-8 rounded-full bg-slate-50 flex items-center justify-center flex-shrink-0">
          <CalendarCheck className="w-3.5 h-3.5 text-slate-400" />
        </div>
        <div className="min-w-0">
          <p className="text-sm text-slate-900 truncate">{contribution.appointment_title}</p>
          <p className="text-xs text-slate-400">
            {contribution.association_name && (
              <span className="text-emerald-600">{contribution.association_name} · </span>
            )}
            {fmtDate(contribution.created_at)}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0 ml-3">
        <span className="text-sm font-semibold text-slate-900 tabular-nums">
          {fmtPrecise(contribution.amount_cents)}
        </span>
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
          contribution.status === 'completed'
            ? 'bg-emerald-50 text-emerald-600'
            : 'bg-amber-50 text-amber-600'
        }`}>
          {contribution.status === 'completed' ? 'confirmé' : 'en attente'}
        </span>
      </div>
    </div>
  );
}

/* ─── Transparency Block ──────────────────────────────── */
function TransparencyBlock() {
  return (
    <div
      className="bg-amber-50 border border-amber-200 rounded-xl p-6"
      data-testid="transparency-block"
    >
      <div className="flex gap-3">
        <Info className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <h3 className="text-sm font-semibold text-amber-800 mb-2">
            Transparence sur les montants
          </h3>
          <p className="text-sm text-amber-700 leading-relaxed">
            Les montants affichés sur cette page sont <strong>fléchés pour des associations</strong> et accumulés
            sur la plateforme NLYT. Le transfert vers les associations n'a pas encore eu lieu.
          </p>
          <p className="text-sm text-amber-700 leading-relaxed mt-2">
            Le <strong>reversement automatique</strong> vers les associations partenaires sera implémenté dans une
            prochaine version de la plateforme. En attendant, chaque euro est comptabilisé et traçable.
          </p>
          <div className="flex items-center gap-1.5 mt-3">
            <Clock className="w-3.5 h-3.5 text-amber-500" />
            <span className="text-xs text-amber-600 font-medium">Reversement automatique — bientôt disponible</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Main Page ────────────────────────────────────────── */
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
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
      </div>
    );
  }

  const hasData = data && data.total_charity_cents > 0;
  const contributions = data?.contributions?.items || [];
  const associations = data?.associations || [];

  return (
    <div className="min-h-screen bg-slate-50">
      {/* ── Hero ── */}
      <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
        <div className="max-w-4xl mx-auto px-6 py-16 sm:py-24 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 text-xs font-medium text-slate-300 mb-6">
            <Shield className="w-3.5 h-3.5" />
            Données auditables et traçables
          </div>
          <h1
            className="text-4xl sm:text-5xl font-bold tracking-tight mb-4"
            data-testid="impact-hero-title"
          >
            Impact caritatif
          </h1>
          <p className="text-lg text-slate-400 max-w-xl mx-auto">
            Chaque engagement non honoré sur NLYT génère des montants fléchés pour des associations.
            Transparence totale sur les sommes accumulées.
          </p>
        </div>
      </div>

      {/* ── Content ── */}
      <div className="max-w-4xl mx-auto px-6">
        {hasData ? (
          <>
            {/* KPIs */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 -mt-8" data-testid="charity-kpis">
              <StatCard
                icon={Heart}
                value={fmt(data.total_charity_cents)}
                label="Fléchés pour des associations"
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
                label="Non tenus avec contribution caritative"
                testId="kpi-no-show-contributions"
              />
            </div>

            {/* Transparency Block */}
            <div className="mt-8">
              <TransparencyBlock />
            </div>

            {/* Associations */}
            {associations.length > 0 && (
              <div className="mt-10" data-testid="associations-section">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-base font-semibold text-slate-900" data-testid="associations-title">
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
                <p className="text-xs text-slate-400 mt-3 text-center">
                  Total fléché pour les associations : <span className="font-semibold text-slate-600">{fmtPrecise(data.total_charity_cents)}</span>
                </p>
              </div>
            )}

            {/* Contributions History */}
            <div className="mt-10 mb-6" data-testid="contributions-section">
              <h2 className="text-base font-semibold text-slate-900 mb-4" data-testid="contributions-title">
                Historique des contributions
              </h2>
              {contributions.length > 0 ? (
                <div className="space-y-2">
                  {contributions.map((c) => (
                    <ContributionRow key={c.distribution_id} contribution={c} />
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-500">Aucune contribution enregistrée pour le moment.</p>
              )}

              {data.contributions?.has_more && (
                <div className="mt-4 text-center">
                  <button
                    onClick={loadMore}
                    disabled={loadingMore}
                    className="inline-flex items-center gap-2 px-4 py-2 text-sm text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
                    data-testid="load-more-contributions"
                  >
                    {loadingMore ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <ChevronDown className="w-4 h-4" />
                    )}
                    Voir plus de contributions
                  </button>
                  <p className="text-xs text-slate-400 mt-1">
                    {contributions.length} sur {data.contributions.total} contributions
                  </p>
                </div>
              )}
            </div>
          </>
        ) : (
          /* ── Empty State ── */
          <div className="bg-white border border-slate-200 rounded-xl p-12 text-center -mt-8" data-testid="charity-empty">
            <Heart className="w-10 h-10 text-slate-300 mx-auto mb-4" />
            <p className="text-lg font-medium text-slate-700 mb-2">L'impact caritatif commence ici</p>
            <p className="text-sm text-slate-500 max-w-md mx-auto mb-6">
              Dès que des garanties de présence seront traitées avec une part caritative,
              les montants fléchés pour les associations apparaîtront ici.
            </p>
            <TransparencyBlock />
          </div>
        )}

        {/* ── How it works ── */}
        {hasData && (
          <div className="bg-white border border-slate-200 rounded-xl p-8 mb-10" data-testid="how-it-works">
            <h2 className="text-base font-semibold text-slate-900 mb-6 text-center">Comment ça fonctionne</h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              <div className="text-center">
                <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
                  <span className="text-sm font-bold text-slate-600">1</span>
                </div>
                <p className="text-sm font-medium text-slate-900 mb-1">Garantie de présence</p>
                <p className="text-xs text-slate-500">
                  Chaque participant dépose une garantie financière lors de son inscription.
                </p>
              </div>
              <div className="text-center">
                <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
                  <span className="text-sm font-bold text-slate-600">2</span>
                </div>
                <p className="text-sm font-medium text-slate-900 mb-1">Absence détectée</p>
                <p className="text-xs text-slate-500">
                  En cas d'absence, la garantie est capturée. Une part est fléchée pour une association.
                </p>
              </div>
              <div className="text-center">
                <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
                  <span className="text-sm font-bold text-slate-600">3</span>
                </div>
                <p className="text-sm font-medium text-slate-900 mb-1">Montants accumulés</p>
                <p className="text-xs text-slate-500">
                  Les montants fléchés sont comptabilisés et traçables. Le reversement automatique sera bientôt disponible.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Footer ── */}
      <div className="bg-slate-50 border-t border-slate-200 py-8">
        <div className="max-w-4xl mx-auto px-6 flex items-center justify-between">
          <p className="text-xs text-slate-400">
            {data?.refreshed_at
              ? `Dernière mise à jour : ${new Date(data.refreshed_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })}`
              : ''}
          </p>
          <Link to="/" className="text-xs text-slate-500 hover:text-slate-700 flex items-center gap-1">
            nlyt.app <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </div>
    </div>
  );
}
