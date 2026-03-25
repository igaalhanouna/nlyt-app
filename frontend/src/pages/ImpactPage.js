import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Heart, Shield, ArrowRight, Loader2, Info, Clock,
  Building2, ChevronDown, CalendarCheck, TrendingUp,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

function fmt(cents) {
  if (!cents) return '0 €';
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency', currency: 'EUR', minimumFractionDigits: 0, maximumFractionDigits: 0,
  }).format(cents / 100);
}

function fmtPrecise(cents) {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(cents / 100);
}

function fmtDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' });
}

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
    } catch { /* silent */ } finally { setLoadingMore(false); }
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
      {/* ── Nav (identique à Landing) ── */}
      <nav className="border-b border-white/5">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <Link to="/" data-testid="nav-logo" className="flex-shrink-0">
            <span className="block text-lg font-bold tracking-[0.35em] text-white">N<span className="text-white/60">·</span>L<span className="text-white/60">·</span>Y<span className="text-white/60">·</span>T</span>
            <span className="block text-[10px] font-medium tracking-[0.25em] text-slate-500 uppercase hidden sm:block">Never Lose Your Time</span>
          </Link>
          <div className="flex items-center gap-2 sm:gap-3">
            <Link to="/impact">
              <Button variant="ghost" className="text-white hover:bg-white/5 h-9 text-xs sm:text-sm px-2 sm:px-3">
                <Heart className="w-3.5 h-3.5 mr-1 text-rose-400" /><span className="hidden sm:inline">Gestes solidaires</span><span className="sm:hidden">Impact</span>
              </Button>
            </Link>
            <Link to="/signin">
              <Button variant="ghost" className="text-slate-400 hover:text-white hover:bg-white/5 h-9 text-xs sm:text-sm px-2 sm:px-3 hidden sm:inline-flex" data-testid="nav-signin-btn">Connexion</Button>
            </Link>
            <Link to="/signup">
              <Button className="bg-white text-[#0A0A0B] hover:bg-slate-200 h-9 text-xs sm:text-sm font-semibold px-3 sm:px-4" data-testid="nav-signup-btn">
                <span className="hidden sm:inline">Créer un engagement</span><span className="sm:hidden">S'inscrire</span>
              </Button>
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="pt-16 pb-20 px-6" data-testid="impact-hero-section">
        <div className="max-w-3xl mx-auto text-center">
          <h1
            className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.05] mb-8"
            data-testid="impact-hero-title"
          >
            Faites profiter de votre temps perdu
          </h1>
          <p className="text-lg sm:text-xl text-slate-400 leading-relaxed max-w-xl mx-auto mb-8">
            Chaque engagement non tenu sur NLYT génère des gestes solidaires
            reversés à des associations. Transparence totale.
          </p>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-medium text-slate-400">
            <Shield className="w-3.5 h-3.5" />
            Données auditables et traçables
          </div>
        </div>
      </section>

      {hasData ? (
        <>
          {/* ── KPIs ── */}
          <section className="py-20 px-6 border-t border-white/5" data-testid="charity-kpis">
            <div className="max-w-3xl mx-auto">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
                <div className="p-8 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-center" data-testid="kpi-total-charity">
                  <Heart className="w-5 h-5 text-rose-400 mx-auto mb-4" />
                  <p className="text-3xl font-bold tracking-tight text-rose-300" style={{ fontVariantNumeric: 'tabular-nums' }} data-testid="impact-hero-amount">{fmt(data.total_charity_cents)}</p>
                  <p className="text-sm text-rose-400/70 mt-1">Reversés à des associations</p>
                </div>
                <div className="p-8 rounded-2xl bg-white/[0.03] border border-white/5 text-center">
                  <Building2 className="w-5 h-5 text-slate-500 mx-auto mb-4" />
                  <p className="text-3xl font-bold tracking-tight text-white" style={{ fontVariantNumeric: 'tabular-nums' }}>{associations.length}</p>
                  <p className="text-sm text-slate-500 mt-1">{associations.length > 1 ? 'Associations soutenues' : 'Association soutenue'}</p>
                </div>
                <div className="p-8 rounded-2xl bg-white/[0.03] border border-white/5 text-center">
                  <CalendarCheck className="w-5 h-5 text-slate-500 mx-auto mb-4" />
                  <p className="text-3xl font-bold tracking-tight text-white" style={{ fontVariantNumeric: 'tabular-nums' }}>{data.total_appointments?.toLocaleString('fr-FR') || '0'}</p>
                  <p className="text-sm text-slate-500 mt-1">Engagements totaux</p>
                </div>
                <div className="p-8 rounded-2xl bg-white/[0.03] border border-white/5 text-center">
                  <TrendingUp className="w-5 h-5 text-slate-500 mx-auto mb-4" />
                  <p className="text-3xl font-bold tracking-tight text-white" style={{ fontVariantNumeric: 'tabular-nums' }}>{data.total_no_show_contributions?.toLocaleString('fr-FR') || '0'}</p>
                  <p className="text-sm text-slate-500 mt-1">Absences transformées</p>
                </div>
              </div>
            </div>
          </section>

          {/* ── Comment ça marche ── */}
          <section className="py-20 px-6 border-t border-white/5" data-testid="how-it-works">
            <div className="max-w-3xl mx-auto">
              <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-center mb-16">Comment ça fonctionne</h2>
              <div className="space-y-12">
                <div className="flex gap-6 items-start">
                  <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0">
                    <span className="text-sm font-bold text-white">1</span>
                  </div>
                  <div>
                    <p className="text-base font-semibold text-white mb-1">Garantie d'engagement</p>
                    <p className="text-sm text-slate-400">Chaque participant dépose une garantie lors de sa confirmation.</p>
                  </div>
                </div>
                <div className="flex gap-6 items-start">
                  <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0">
                    <span className="text-sm font-bold text-white">2</span>
                  </div>
                  <div>
                    <p className="text-base font-semibold text-white mb-1">Absence constatée</p>
                    <p className="text-sm text-slate-400">En cas d'absence, la garantie est capturée. Une part devient un geste solidaire.</p>
                  </div>
                </div>
                <div className="flex gap-6 items-start">
                  <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0">
                    <span className="text-sm font-bold text-white">3</span>
                  </div>
                  <div>
                    <p className="text-base font-semibold text-white mb-1">Gestes solidaires cumulés</p>
                    <p className="text-sm text-slate-400">Les montants reversés sont comptabilisés et traçables. Le reversement automatique sera bientôt disponible.</p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* ── CTA ── */}
          <section className="py-24 px-6 border-t border-white/5" data-testid="impact-cta-section">
            <div className="max-w-2xl mx-auto text-center">
              <p className="text-2xl sm:text-3xl font-bold tracking-tight text-white mb-4">
                Faites de chaque absence une possibilité de faire une bonne action.
              </p>
              <p className="text-sm text-slate-500 mb-10">
                Votre temps est garanti. Faites en profiter qui vous voulez.
              </p>
              <Link to="/signup">
                <Button size="lg" className="bg-white text-[#0A0A0B] hover:bg-slate-200 text-base px-8 h-13 font-semibold" data-testid="impact-cta-btn">
                  Créer un engagement solidaire <ArrowRight className="ml-2 w-4 h-4" />
                </Button>
              </Link>
            </div>
          </section>

          {/* ── Transparence ── */}
          <section className="py-20 px-6 border-t border-white/5" data-testid="transparency-section">
            <div className="max-w-3xl mx-auto">
              <div className="p-8 rounded-2xl bg-white/[0.03] border border-white/5">
                <div className="flex gap-4">
                  <Info className="w-5 h-5 text-slate-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="text-base font-semibold text-white mb-2">Transparence sur les montants</h3>
                    <p className="text-sm text-slate-400 leading-relaxed">
                      Les montants affichés sur cette page sont <strong className="text-white">reversés à des associations</strong> et accumulés
                      sur la plateforme NLYT. Le transfert vers les associations n'a pas encore eu lieu.
                    </p>
                    <p className="text-sm text-slate-400 leading-relaxed mt-2">
                      Le <strong className="text-white">reversement automatique</strong> vers les associations partenaires sera implémenté dans une
                      prochaine version de la plateforme. En attendant, chaque euro est comptabilisé et traçable.
                    </p>
                    <div className="flex items-center gap-1.5 mt-4">
                      <Clock className="w-3.5 h-3.5 text-slate-500" />
                      <span className="text-xs text-slate-500 font-medium">Reversement automatique — bientôt disponible</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* ── Associations bénéficiaires ── */}
          {associations.length > 0 && (
            <section className="py-20 px-6 border-t border-white/5" data-testid="associations-section">
              <div className="max-w-3xl mx-auto">
                <div className="flex items-center justify-between mb-8">
                  <h2 className="text-2xl sm:text-3xl font-bold tracking-tight" data-testid="associations-title">Associations bénéficiaires</h2>
                  <span className="text-sm text-slate-500">{associations.length} association{associations.length > 1 ? 's' : ''}</span>
                </div>
                <div className="space-y-3">
                  {associations.map((a, i) => (
                    <div
                      key={a.association_id}
                      className="flex items-center justify-between p-5 rounded-2xl bg-white/[0.03] border border-white/5"
                      data-testid={`assoc-row-${a.association_id}`}
                    >
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-full bg-rose-500/10 flex items-center justify-center flex-shrink-0">
                          <Heart className="w-4 h-4 text-rose-400" />
                        </div>
                        <div>
                          <p className="text-base font-semibold text-white">{a.name || `Association #${i + 1}`}</p>
                          <p className="text-sm text-slate-500">
                            {a.distributions_count} geste{a.distributions_count > 1 ? 's' : ''} solidaire{a.distributions_count > 1 ? 's' : ''}
                            {' · '}{a.events_count} engagement{a.events_count > 1 ? 's' : ''}
                          </p>
                        </div>
                      </div>
                      <p className="text-lg font-bold text-rose-400 tabular-nums">{fmtPrecise(a.total_cents)}</p>
                    </div>
                  ))}
                </div>
                <p className="text-sm text-slate-500 mt-6 text-center">
                  Total reversé : <span className="font-semibold text-rose-400">{fmtPrecise(data.total_charity_cents)}</span>
                </p>
              </div>
            </section>
          )}

          {/* ── Historique des gestes solidaires ── */}
          <section className="py-20 px-6 border-t border-white/5" data-testid="contributions-section">
            <div className="max-w-3xl mx-auto">
              <h2 className="text-2xl sm:text-3xl font-bold tracking-tight mb-8" data-testid="contributions-title">Historique des gestes solidaires</h2>
              {contributions.length > 0 ? (
                <div className="space-y-3">
                  {contributions.map((c) => (
                    <div
                      key={c.distribution_id}
                      className="flex items-center justify-between p-5 rounded-2xl bg-white/[0.03] border border-white/5"
                      data-testid={`contribution-${c.distribution_id}`}
                    >
                      <div className="flex items-center gap-4 min-w-0">
                        <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0">
                          <CalendarCheck className="w-4 h-4 text-slate-500" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-base font-medium text-white truncate">{c.appointment_title}</p>
                          <p className="text-sm text-slate-500">
                            {c.association_name && <span className="text-rose-400">{c.association_name} · </span>}
                            {fmtDate(c.created_at)}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 flex-shrink-0 ml-4">
                        <span className="text-base font-semibold text-white tabular-nums">{fmtPrecise(c.amount_cents)}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          c.status === 'completed' ? 'bg-rose-500/10 text-rose-400' : 'bg-amber-500/10 text-amber-400'
                        }`}>
                          {c.status === 'completed' ? 'confirmé' : 'en attente'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-500">Aucun geste solidaire enregistré pour le moment.</p>
              )}

              {data.contributions?.has_more && (
                <div className="mt-8 text-center">
                  <button
                    onClick={loadMore}
                    disabled={loadingMore}
                    className="inline-flex items-center gap-2 px-5 py-2.5 text-sm text-slate-400 bg-white/[0.03] border border-white/10 rounded-full hover:bg-white/[0.06] transition-colors disabled:opacity-50"
                    data-testid="load-more-contributions"
                  >
                    {loadingMore ? <Loader2 className="w-4 h-4 animate-spin" /> : <ChevronDown className="w-4 h-4" />}
                    Voir plus
                  </button>
                  <p className="text-xs text-slate-600 mt-2">{contributions.length} sur {data.contributions.total}</p>
                </div>
              )}
            </div>
          </section>
        </>
      ) : (
        /* ── Empty State ── */
        <section className="py-20 px-6 border-t border-white/5">
          <div className="max-w-3xl mx-auto space-y-8">
            <div className="p-12 rounded-2xl bg-white/[0.03] border border-white/5 text-center" data-testid="charity-empty">
              <Heart className="w-10 h-10 text-rose-400/30 mx-auto mb-6" />
              <p className="text-lg font-semibold text-white mb-2">Les gestes solidaires commencent ici</p>
              <p className="text-sm text-slate-400 max-w-md mx-auto">
                Dès que des garanties d'engagement seront traitées avec une part solidaire,
                les montants reversés aux associations apparaîtront ici.
              </p>
            </div>

            <div className="p-8 rounded-2xl bg-white/[0.03] border border-white/5">
              <div className="flex gap-4">
                <Info className="w-5 h-5 text-slate-500 flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-base font-semibold text-white mb-2">Transparence sur les montants</h3>
                  <p className="text-sm text-slate-400 leading-relaxed">
                    Les montants affichés sur cette page sont <strong className="text-white">reversés à des associations</strong> et accumulés
                    sur la plateforme NLYT. Le transfert vers les associations n'a pas encore eu lieu.
                  </p>
                  <p className="text-sm text-slate-400 leading-relaxed mt-2">
                    Le <strong className="text-white">reversement automatique</strong> vers les associations partenaires sera implémenté dans une
                    prochaine version de la plateforme. En attendant, chaque euro est comptabilisé et traçable.
                  </p>
                  <div className="flex items-center gap-1.5 mt-4">
                    <Clock className="w-3.5 h-3.5 text-slate-500" />
                    <span className="text-xs text-slate-500 font-medium">Reversement automatique — bientôt disponible</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ── Footer (identique à Landing) ── */}
      <footer className="border-t border-white/5 py-8 sm:py-10 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center sm:justify-between gap-2 text-center sm:text-left">
          <p className="text-xs text-slate-600">© 2026 NLYT — Never Lose Your Time.</p>
          <p className="text-xs text-slate-600">
            {data?.refreshed_at
              ? `Mis à jour : ${new Date(data.refreshed_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}`
              : 'Votre temps est compté. Ne le gaspillez pas.'}
          </p>
        </div>
      </footer>
    </div>
  );
}
