import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, ArrowDownRight, Wallet, Heart, Loader2, CalendarCheck, ChevronRight, TrendingUp } from 'lucide-react';
import { financialAPI } from '../services/api';
import AppNavbar from '../components/AppNavbar';
import AppBreadcrumb from '../components/AppBreadcrumb';

function fmt(cents, currency = 'eur') {
  if (cents == null) return '0 €';
  const symbol = (currency || 'eur').toUpperCase() === 'EUR' ? '€' : currency;
  return `${(Math.abs(cents) / 100).toFixed(2).replace('.', ',')} ${symbol}`;
}

function fmtDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
}

export default function FinancialResultsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    financialAPI.getMyResults()
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <AppNavbar />
        <div className="flex items-center justify-center py-32">
          <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
        </div>
      </div>
    );
  }

  const synthesis = data?.synthesis || {};
  const engagements = data?.engagements || [];
  const solidarity = data?.solidarity || {};
  const associations = solidarity.associations || [];

  const hasData = engagements.length > 0;
  const netPositive = synthesis.net_balance_cents >= 0;

  return (
    <div className="min-h-screen bg-slate-50" data-testid="financial-results-page">
      <AppNavbar />
      <AppBreadcrumb items={[
        { label: 'Tableau de bord', href: '/dashboard' },
        { label: 'Mes resultats' },
      ]} />

      <div className="max-w-5xl mx-auto px-4 md:px-6 pb-12">

        {/* Page title */}
        <div className="pt-2 pb-6">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900" data-testid="page-title">
            Vos resultats d'engagement
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Vue d'ensemble de vos participations et de leur impact.
          </p>
        </div>

        {/* ── Synthesis cards ── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10" data-testid="synthesis-cards">

          {/* Total received */}
          <div className="bg-white border border-slate-200 rounded-xl p-5" data-testid="total-received-card">
            <div className="flex items-center gap-2.5 mb-3">
              <div className="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center">
                <ArrowUpRight className="w-4.5 h-4.5 text-emerald-600" />
              </div>
              <span className="text-sm font-medium text-slate-500">Total recu</span>
            </div>
            <p className="text-3xl font-bold tracking-tight text-emerald-600" style={{ fontVariantNumeric: 'tabular-nums' }} data-testid="total-received-value">
              +{fmt(synthesis.total_received_cents)}
            </p>
          </div>

          {/* Total paid */}
          <div className="bg-white border border-slate-200 rounded-xl p-5" data-testid="total-paid-card">
            <div className="flex items-center gap-2.5 mb-3">
              <div className="w-9 h-9 rounded-lg bg-red-50 flex items-center justify-center">
                <ArrowDownRight className="w-4.5 h-4.5 text-red-600" />
              </div>
              <span className="text-sm font-medium text-slate-500">Total paye</span>
            </div>
            <p className="text-3xl font-bold tracking-tight text-red-600" style={{ fontVariantNumeric: 'tabular-nums' }} data-testid="total-paid-value">
              -{fmt(synthesis.total_paid_cents)}
            </p>
          </div>

          {/* Net balance */}
          <div className="bg-white border border-slate-200 rounded-xl p-5" data-testid="net-balance-card">
            <div className="flex items-center gap-2.5 mb-3">
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${netPositive ? 'bg-slate-100' : 'bg-red-50'}`}>
                <Wallet className={`w-4.5 h-4.5 ${netPositive ? 'text-slate-700' : 'text-red-600'}`} />
              </div>
              <span className="text-sm font-medium text-slate-500">Solde net</span>
            </div>
            <p className={`text-3xl font-bold tracking-tight ${netPositive ? 'text-slate-900' : 'text-red-600'}`} style={{ fontVariantNumeric: 'tabular-nums' }} data-testid="net-balance-value">
              {synthesis.net_balance_cents >= 0 ? '+' : '-'}{fmt(synthesis.net_balance_cents)}
            </p>
          </div>
        </div>

        {/* ── Engagement list ── */}
        <section className="mb-10" data-testid="engagement-list">
          <h2 className="text-lg font-semibold text-slate-900 mb-1">Detail de vos engagements</h2>
          <p className="text-sm text-slate-500 mb-4">Historique de vos rendez-vous ayant eu un impact financier.</p>

          {!hasData ? (
            <div className="bg-white border border-slate-200 rounded-xl p-8 text-center">
              <CalendarCheck className="w-8 h-8 text-slate-300 mx-auto mb-3" />
              <p className="text-sm text-slate-500">Aucun engagement avec impact financier pour le moment.</p>
              <Link to="/dashboard" className="text-sm text-slate-900 font-medium hover:underline mt-2 inline-block" data-testid="back-to-dashboard-link">
                Retour au tableau de bord
              </Link>
            </div>
          ) : (
            <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100 overflow-hidden">
              {engagements.map((eng) => {
                const isPaid = eng.paid_cents > 0;
                const isReceived = eng.received_cents > 0;
                const hasCharity = eng.charity_cents > 0;

                return (
                  <Link
                    key={eng.appointment_id}
                    to={`/appointments/${eng.appointment_id}`}
                    className="flex items-center justify-between px-4 py-3.5 hover:bg-slate-50 transition-colors group"
                    data-testid="engagement-item"
                  >
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
                        isPaid && !isReceived ? 'bg-red-50' :
                        isReceived && !isPaid ? 'bg-emerald-50' :
                        isPaid && isReceived ? 'bg-amber-50' :
                        'bg-slate-50'
                      }`}>
                        <CalendarCheck className={`w-4 h-4 ${
                          isPaid && !isReceived ? 'text-red-500' :
                          isReceived && !isPaid ? 'text-emerald-500' :
                          isPaid && isReceived ? 'text-amber-500' :
                          'text-slate-400'
                        }`} />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-slate-900 truncate">{eng.title}</p>
                        <p className="text-xs text-slate-400 mt-0.5">{fmtDate(eng.date)}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 flex-shrink-0 ml-3">
                      <div className="text-right space-y-0.5">
                        {isPaid && (
                          <p className="text-sm font-semibold text-red-600" data-testid="eng-paid-amount">
                            {"Vous avez indemnis\u00e9 de "}{fmt(eng.paid_cents, eng.currency)}
                          </p>
                        )}
                        {isReceived && (
                          <p className="text-sm font-semibold text-emerald-600" data-testid="eng-received-amount">
                            {"Vous avez \u00e9t\u00e9 d\u00e9dommag\u00e9 de +"}{fmt(eng.received_cents, eng.currency)}
                          </p>
                        )}
                        {hasCharity && (
                          <p className="text-xs text-rose-500 font-medium">
                            {"Vous avez contribu\u00e9 \u00e0 un geste solidaire de "}{fmt(eng.charity_cents, eng.currency)}
                            {eng.charity_association_name && ` pour ${eng.charity_association_name}`}
                          </p>
                        )}
                        {!isPaid && !isReceived && (
                          <p className="text-sm text-slate-400">Aucun impact</p>
                        )}
                      </div>
                      <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-500 transition-colors" />
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </section>

        {/* ── Solidarity impact ── */}
        <section data-testid="solidarity-impact-section">
          <div className="flex items-center gap-2 mb-1">
            <Heart className="w-4.5 h-4.5 text-rose-500" />
            <h2 className="text-lg font-semibold text-slate-900">Votre impact solidaire</h2>
          </div>
          <p className="text-sm text-slate-500 mb-4">
            Les contributions generees par vos engagements et reversees aux associations.
          </p>

          {solidarity.total_charity_cents > 0 ? (
            <div className="space-y-4">
              {/* Total solidarity card */}
              <div className="bg-gradient-to-r from-rose-50 to-amber-50 border border-rose-200/60 rounded-xl p-5" data-testid="charity-total">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-rose-100 flex items-center justify-center">
                    <TrendingUp className="w-5 h-5 text-rose-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold tracking-tight text-rose-700" style={{ fontVariantNumeric: 'tabular-nums' }}>
                      {fmt(solidarity.total_charity_cents)}
                    </p>
                    <p className="text-sm text-rose-600/80">reverses a des associations</p>
                  </div>
                </div>
              </div>

              {/* Per-association breakdown */}
              {associations.length > 0 && (
                <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100 overflow-hidden">
                  {associations.map((assoc) => (
                    <div key={assoc.association_id} className="flex items-center justify-between px-4 py-3" data-testid="charity-item">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-8 h-8 rounded-full bg-rose-50 flex items-center justify-center flex-shrink-0">
                          <Heart className="w-3.5 h-3.5 text-rose-500" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-slate-900 truncate">{assoc.name}</p>
                          <p className="text-xs text-slate-400">
                            {assoc.count} engagement{assoc.count > 1 ? 's' : ''}
                          </p>
                        </div>
                      </div>
                      <p className="text-sm font-bold text-rose-600 tabular-nums flex-shrink-0 ml-3">
                        {fmt(assoc.total_cents)}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white border border-slate-200 rounded-xl p-8 text-center">
              <Heart className="w-8 h-8 text-slate-300 mx-auto mb-3" />
              <p className="text-sm text-slate-500">Aucune contribution solidaire pour le moment.</p>
              <p className="text-xs text-slate-400 mt-1">
                Les contributions seront generees automatiquement lors de vos prochains engagements.
              </p>
            </div>
          )}
        </section>

      </div>
    </div>
  );
}
