import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Heart, Shield, Clock, CheckCircle, Users, Zap } from 'lucide-react';
import { Button } from '../components/ui/button';

const API = process.env.REACT_APP_BACKEND_URL;

export default function LandingPage() {
  const [impactCents, setImpactCents] = useState(0);

  useEffect(() => {
    fetch(`${API}/api/impact`)
      .then(r => r.json())
      .then(d => setImpactCents(d.total_charity_cents || 0))
      .catch(() => {});
  }, []);

  const impactFormatted = new Intl.NumberFormat('fr-FR', {
    style: 'currency', currency: 'EUR', minimumFractionDigits: 0, maximumFractionDigits: 0,
  }).format(impactCents / 100);

  return (
    <div className="min-h-screen bg-[#0A0A0B] text-white">
      {/* ── Nav ── */}
      <nav className="border-b border-white/5">
        <div className="max-w-6xl mx-auto px-6 lg:px-8 py-5 flex items-center justify-between">
          <span className="text-xl font-bold tracking-tight text-white" data-testid="nav-logo">
            NLYT
            <span className="block text-[9px] font-normal tracking-[0.2em] text-slate-500 uppercase">Never Lose Your Time</span>
          </span>
          <div className="flex items-center gap-3">
            <Link to="/impact">
              <Button variant="ghost" className="text-slate-400 hover:text-white hover:bg-white/5 h-9 text-sm" data-testid="nav-impact-btn">
                <Heart className="w-3.5 h-3.5 mr-1.5 text-rose-400" />Gestes solidaires
              </Button>
            </Link>
            <Link to="/signin">
              <Button variant="ghost" className="text-slate-400 hover:text-white hover:bg-white/5 h-9 text-sm" data-testid="nav-signin-btn">Connexion</Button>
            </Link>
            <Link to="/signup">
              <Button className="bg-white text-[#0A0A0B] hover:bg-slate-200 h-9 text-sm font-semibold" data-testid="nav-signup-btn">
                Créer un engagement
              </Button>
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="pt-28 pb-20 px-6" data-testid="hero-section">
        <div className="max-w-3xl mx-auto text-center">
          <div className="mb-6">
            <p className="text-sm tracking-[0.35em] font-semibold text-white/80 mb-1">
              <span className="text-white">N</span> · <span className="text-white">L</span> · <span className="text-white">Y</span> · <span className="text-white">T</span>
            </p>
            <p className="text-[11px] tracking-[0.25em] uppercase text-slate-500">
              Never Lose Your Time
            </p>
          </div>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-medium text-slate-400 mb-10">
            <Shield className="w-3 h-3" />
            Créateur d'engagements solidaires
          </div>
          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.05] mb-8" data-testid="hero-title">
            Votre temps<br /> ne se perd plus.
          </h1>
          <p className="text-lg sm:text-xl text-slate-400 leading-relaxed max-w-xl mx-auto mb-12" data-testid="hero-subtitle">
            Votre temps est précieux. Protégez-le.<br className="hidden sm:block" />
            Et faites que chaque absence indélicate devienne un geste solidaire.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link to="/signup">
              <Button size="lg" className="bg-white text-[#0A0A0B] hover:bg-slate-200 text-base px-8 h-13 font-semibold" data-testid="hero-cta-btn">
                Créer un engagement solidaire <ArrowRight className="ml-2 w-4 h-4" />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* ── Promesse ── */}
      <section className="py-20 px-6 border-t border-white/5" data-testid="promise-section">
        <div className="max-w-3xl mx-auto">
          <div className="grid sm:grid-cols-2 gap-6">
            <div className="p-8 rounded-2xl bg-white/[0.03] border border-white/5">
              <CheckCircle className="w-5 h-5 text-emerald-400 mb-5" />
              <p className="text-lg font-semibold text-white mb-2">Engagement tenu</p>
              <p className="text-sm text-slate-400 leading-relaxed">
                Votre temps est respecté. La garantie est libérée.
              </p>
            </div>
            <div className="p-8 rounded-2xl bg-white/[0.03] border border-white/5">
              <Heart className="w-5 h-5 text-rose-400 mb-5" />
              <p className="text-lg font-semibold text-white mb-2">Engagement non tenu</p>
              <p className="text-sm text-slate-400 leading-relaxed">
                Votre perte de temps est compensée et devient même un geste solidaire.
              </p>
            </div>
          </div>
          <p className="text-center text-sm text-slate-500 mt-8">
            Votre temps n'est plus jamais perdu.
          </p>
        </div>
      </section>

      {/* ── Comment ça marche ── */}
      <section className="py-20 px-6 border-t border-white/5" data-testid="how-section">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-center mb-16">Comment ça marche</h2>
          <div className="space-y-12">
            <div className="flex gap-6 items-start">
              <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0">
                <span className="text-sm font-bold text-white">1</span>
              </div>
              <div>
                <p className="text-base font-semibold text-white mb-1">Créez un engagement</p>
                <p className="text-sm text-slate-400">Définissez les conditions : horaire, durée, montant de l'engagement. En 2 minutes.</p>
              </div>
            </div>
            <div className="flex gap-6 items-start">
              <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0">
                <span className="text-sm font-bold text-white">2</span>
              </div>
              <div>
                <p className="text-base font-semibold text-white mb-1">Chacun confirme sa présence</p>
                <p className="text-sm text-slate-400">Les participants découvrent les conditions et confirment avec une garantie réciproque.</p>
              </div>
            </div>
            <div className="flex gap-6 items-start">
              <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0">
                <span className="text-sm font-bold text-white">3</span>
              </div>
              <div>
                <p className="text-base font-semibold text-white mb-1">Le temps crée toujours de la valeur</p>
                <p className="text-sm text-slate-400">Présent ? Garantie libérée. Absent ? Compensation automatique et geste solidaire possible.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Preuve sociale / Compteur ── */}
      {impactCents > 0 && (
        <section className="py-20 px-6 border-t border-white/5" data-testid="proof-section">
          <div className="max-w-3xl mx-auto text-center">
            <Heart className="w-5 h-5 text-rose-400 mx-auto mb-6" />
            <p className="text-4xl sm:text-5xl font-bold tracking-tight text-white mb-3" data-testid="proof-amount">
              {impactFormatted}
            </p>
            <p className="text-sm text-slate-400">
              reversés à des associations grâce aux gestes solidaires sur NLYT.
            </p>
            <Link to="/impact" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-white mt-6 transition-colors">
              Voir le détail <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </section>
      )}

      {/* ── Cas d'usage ── */}
      <section className="py-20 px-6 border-t border-white/5" data-testid="usecases-section">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight mb-4">Pour tous ceux dont le temps compte</h2>
          <p className="text-sm text-slate-400 mb-12">Coachs, consultants, thérapeutes, avocats, recruteurs, freelances...</p>
          <div className="grid sm:grid-cols-3 gap-4">
            <div className="p-6 rounded-xl bg-white/[0.03] border border-white/5">
              <Users className="w-4 h-4 text-slate-500 mb-3" />
              <p className="text-sm font-medium text-white">Consultants</p>
              <p className="text-xs text-slate-500 mt-1">Fini les créneaux bloqués pour rien</p>
            </div>
            <div className="p-6 rounded-xl bg-white/[0.03] border border-white/5">
              <Clock className="w-4 h-4 text-slate-500 mb-3" />
              <p className="text-sm font-medium text-white">Coachs</p>
              <p className="text-xs text-slate-500 mt-1">Chaque session est un vrai engagement</p>
            </div>
            <div className="p-6 rounded-xl bg-white/[0.03] border border-white/5">
              <Zap className="w-4 h-4 text-slate-500 mb-3" />
              <p className="text-sm font-medium text-white">Professions libérales</p>
              <p className="text-xs text-slate-500 mt-1">Votre temps retrouve sa juste valeur</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA Final ── */}
      <section className="py-24 px-6 border-t border-white/5" data-testid="cta-section">
        <div className="max-w-2xl mx-auto text-center">
          <p className="text-2xl sm:text-3xl font-bold tracking-tight text-white mb-4">
            Chaque occasion perdue devient une possibilité de faire une bonne action.
          </p>
          <p className="text-sm text-slate-500 mb-10">
            Votre temps est garanti. Faites en profiter qui vous voulez.
          </p>
          <Link to="/signup">
            <Button size="lg" className="bg-white text-[#0A0A0B] hover:bg-slate-200 text-base px-8 h-13 font-semibold" data-testid="footer-cta-btn">
              Créer mon premier engagement solidaire <ArrowRight className="ml-2 w-4 h-4" />
            </Button>
          </Link>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-white/5 py-10 px-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <p className="text-xs text-slate-600">© 2026 NLYT — Never Lose Your Time. Votre temps ne se perd plus.</p>
          <p className="text-xs text-slate-600">Votre temps est compté. Ne le gaspillez pas.</p>
        </div>
      </footer>
    </div>
  );
}
