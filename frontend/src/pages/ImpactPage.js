import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Heart, Users, CalendarCheck, TrendingUp, ArrowRight, Shield, Loader2 } from 'lucide-react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

function fmt(cents, currency = 'eur') {
  if (!cents) return '0 €';
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency, minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(cents / 100);
}

function fmtPrecise(cents, currency = 'eur') {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency }).format(cents / 100);
}

function StatCard({ icon: Icon, value, label, accent = false }) {
  return (
    <div className={`rounded-xl p-6 text-center ${accent ? 'bg-rose-600 text-white' : 'bg-white border border-slate-200'}`}>
      <Icon className={`w-6 h-6 mx-auto mb-3 ${accent ? 'text-rose-200' : 'text-slate-400'}`} />
      <p className={`text-3xl font-bold tracking-tight ${accent ? 'text-white' : 'text-slate-900'}`} style={{fontVariantNumeric: 'tabular-nums'}}>
        {value}
      </p>
      <p className={`text-sm mt-1 ${accent ? 'text-rose-200' : 'text-slate-500'}`}>{label}</p>
    </div>
  );
}

function AssociationRow({ association, rank }) {
  const name = association.name || `Association #${rank}`;
  return (
    <div className="flex items-center justify-between py-4 px-5 bg-white rounded-lg border border-slate-100" data-testid={`assoc-row-${association.association_id}`}>
      <div className="flex items-center gap-4">
        <div className="w-9 h-9 rounded-full bg-rose-50 flex items-center justify-center flex-shrink-0">
          <Heart className="w-4 h-4 text-rose-500" />
        </div>
        <div>
          <p className="text-sm font-medium text-slate-900">{name}</p>
          <p className="text-xs text-slate-500">
            {association.distributions_count} distribution{association.distributions_count > 1 ? 's' : ''}
            {' · '}
            {association.events_count} événement{association.events_count > 1 ? 's' : ''}
          </p>
        </div>
      </div>
      <p className="text-sm font-bold text-slate-900 tabular-nums">{fmtPrecise(association.total_cents)}</p>
    </div>
  );
}

export default function ImpactPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API}/api/impact`)
      .then(res => setStats(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
      </div>
    );
  }

  const hasData = stats && stats.total_distributed_cents > 0;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Hero */}
      <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
        <div className="max-w-4xl mx-auto px-6 py-16 sm:py-24 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 text-xs font-medium text-slate-300 mb-6">
            <Shield className="w-3.5 h-3.5" />
            Données vérifiées et auditables
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight mb-4" data-testid="impact-hero-title">
            Impact NLYT
          </h1>
          <p className="text-lg text-slate-400 max-w-xl mx-auto">
            NLYT encourage la présence et la responsabilité. Chaque absence détectée génère un impact concret : dédommagement, contribution à des associations, transparence totale.
          </p>
        </div>
      </div>

      {/* KPIs */}
      <div className="max-w-4xl mx-auto px-6 -mt-8">
        {hasData ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4" data-testid="impact-kpis">
            <StatCard icon={TrendingUp} value={fmt(stats.total_distributed_cents)} label="Redistribués" />
            <StatCard icon={Heart} value={fmt(stats.total_charity_cents)} label="Aux associations" accent />
            <StatCard icon={CalendarCheck} value={stats.events_count?.toLocaleString('fr-FR') || '0'} label="Événements" />
            <StatCard icon={Users} value={stats.participants_count?.toLocaleString('fr-FR') || '0'} label="Participants" />
          </div>
        ) : (
          <div className="bg-white border border-slate-200 rounded-xl p-12 text-center" data-testid="impact-empty">
            <Heart className="w-10 h-10 text-slate-300 mx-auto mb-4" />
            <p className="text-lg font-medium text-slate-700 mb-2">L'impact commence ici</p>
            <p className="text-sm text-slate-500 max-w-md mx-auto">
              Dès que des garanties de présence seront traitées, les statistiques d'impact apparaîtront sur cette page.
            </p>
          </div>
        )}
      </div>

      {/* Associations */}
      {hasData && stats.associations?.length > 0 && (
        <div className="max-w-4xl mx-auto px-6 mt-12 mb-16">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-900" data-testid="associations-title">
              Associations soutenues
            </h2>
            <span className="text-xs text-slate-500">
              {stats.associations.length} association{stats.associations.length > 1 ? 's' : ''}
            </span>
          </div>
          <div className="space-y-2" data-testid="associations-list">
            {stats.associations.map((a, i) => (
              <AssociationRow key={a.association_id} association={a} rank={i + 1} />
            ))}
          </div>
          <div className="mt-6 text-center">
            <p className="text-xs text-slate-400">
              Total reversé aux associations : <span className="font-semibold text-slate-600">{fmtPrecise(stats.total_charity_cents)}</span>
            </p>
          </div>
        </div>
      )}

      {/* How it works */}
      {hasData && (
        <div className="bg-white border-t border-slate-200">
          <div className="max-w-4xl mx-auto px-6 py-12">
            <h2 className="text-lg font-semibold text-slate-900 mb-6 text-center">Comment ça fonctionne</h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              <div className="text-center">
                <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
                  <span className="text-sm font-bold text-slate-600">1</span>
                </div>
                <p className="text-sm font-medium text-slate-900 mb-1">Garantie de présence</p>
                <p className="text-xs text-slate-500">Chaque participant dépose une garantie financière en s'inscrivant.</p>
              </div>
              <div className="text-center">
                <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
                  <span className="text-sm font-bold text-slate-600">2</span>
                </div>
                <p className="text-sm font-medium text-slate-900 mb-1">Vérification NLYT</p>
                <p className="text-xs text-slate-500">La présence est vérifiée automatiquement. En cas d'absence, la garantie est capturée.</p>
              </div>
              <div className="text-center">
                <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
                  <span className="text-sm font-bold text-slate-600">3</span>
                </div>
                <p className="text-sm font-medium text-slate-900 mb-1">Redistribution équitable</p>
                <p className="text-xs text-slate-500">Les fonds sont redistribués : dédommagement, plateforme, et associations.</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="bg-slate-50 border-t border-slate-200 py-8">
        <div className="max-w-4xl mx-auto px-6 flex items-center justify-between">
          <p className="text-xs text-slate-400">
            {stats?.refreshed_at
              ? `Dernière mise à jour : ${new Date(stats.refreshed_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })}`
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
