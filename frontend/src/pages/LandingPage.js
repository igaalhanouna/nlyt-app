import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Heart, Shield, Clock, CheckCircle, Users, Zap } from 'lucide-react';
import { Button } from '../components/ui/button';

const API = process.env.REACT_APP_BACKEND_URL;

export default function LandingPage() {
  const [impactCents, setImpactCents] = useState(0);

  useEffect(() => {
    fetch(`${API}/api/impact`)
      .then(r => r.text())
      .then(text => { try { return JSON.parse(text); } catch { return {}; } })
      .then(d => setImpactCents(d.total_charity_cents || 0))
      .catch(() => {});
  }, []);

  const impactFormatted = new Intl.NumberFormat('fr-FR', {
    style: 'currency', currency: 'EUR', minimumFractionDigits: 0, maximumFractionDigits: 0,
  }).format(impactCents / 100);

  return (
    <div className="min-h-screen bg-[#0A0A0B] text-white">
      {/* ── Nav ── */}
      <nav className="border-b border-white/5 overflow-hidden">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex flex-wrap items-center justify-between gap-y-3">
          <span className="text-white flex-shrink-0" data-testid="nav-logo">
            <span className="block text-lg font-bold tracking-[0.35em] text-white">N<span className="text-white/60">·</span>L<span className="text-white/60">·</span>Y<span className="text-white/60">·</span>T</span>
            <span className="block text-[10px] font-medium tracking-[0.25em] text-slate-500 uppercase">Never Lose Your Time</span>
          </span>
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <Link to="/impact">
              <Button variant="ghost" className="text-slate-400 hover:text-white hover:bg-white/5 h-9 text-xs sm:text-sm px-2 sm:px-3" data-testid="nav-impact-btn">
                <Heart className="w-3.5 h-3.5 mr-1 text-rose-400" />Gestes solidaires
              </Button>
            </Link>
            <Link to="/signin">
              <Button variant="ghost" className="text-slate-400 hover:text-white hover:bg-white/5 h-9 text-xs sm:text-sm px-2 sm:px-3" data-testid="nav-signin-btn">Connexion</Button>
            </Link>
          </div>
          <Link to="/signup" className="hidden sm:inline-block sm:w-auto order-last sm:order-none">
            <Button className="bg-white text-[#0A0A0B] hover:bg-slate-200 h-10 sm:h-9 text-xs sm:text-sm font-semibold w-full sm:w-auto" data-testid="nav-signup-btn">
              Créer un engagement
            </Button>
          </Link>
        </div>
      </nav>

      {/* ── Hero (compact on mobile, CTA above fold) ── */}
      <section className="pt-6 sm:pt-16 pb-8 sm:pb-20 px-4 sm:px-6" data-testid="hero-section">
        <div className="max-w-3xl mx-auto text-center">
          <div className="mb-8 sm:mb-24">
            <p className="text-2xl sm:text-3xl font-bold tracking-[0.4em] text-white mb-2">
              N<span className="text-white/60">·</span>L<span className="text-white/60">·</span>Y<span className="text-white/60">·</span>T
            </p>
            <p className="text-xs tracking-[0.3em] uppercase text-slate-500 font-medium">
              Créateur d'engagements solidaires
            </p>
          </div>
          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.05] mb-4 sm:mb-8" data-testid="hero-title">
            Votre temps<br /> ne se perd plus.
          </h1>
          <p className="text-base sm:text-xl text-slate-400 leading-relaxed max-w-xl mx-auto mb-6 sm:mb-12" data-testid="hero-subtitle">
            Votre temps est précieux. Protégez-le.<br />
            Et faites que chaque absence indélicate devienne un geste solidaire.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link to="/signup">
              <Button size="lg" className="bg-white text-[#0A0A0B] hover:bg-slate-200 text-base px-8 h-13 font-semibold w-full sm:w-auto" data-testid="hero-cta-btn">
                Créer un engagement solidaire <ArrowRight className="ml-2 w-4 h-4" />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* ── Comment ça marche (moved right after Hero) ── */}
      <section className="py-10 sm:py-20 px-4 sm:px-6 border-t border-white/5" data-testid="how-section">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-xl sm:text-2xl md:text-3xl font-bold tracking-tight text-center mb-8 sm:mb-16">Comment ça marche ?</h2>
          <div className="space-y-6 sm:space-y-12">
            <div className="flex gap-4 sm:gap-6 items-start">
              <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0">
                <span className="text-sm font-bold text-white">1</span>
              </div>
              <div>
                <p className="text-base font-semibold text-white mb-1">Créez un engagement</p>
                <p className="text-sm text-slate-400">Définissez les conditions : horaire, durée, montant de l'engagement. En 2 minutes.</p>
              </div>
            </div>
            <div className="flex gap-4 sm:gap-6 items-start">
              <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0">
                <span className="text-sm font-bold text-white">2</span>
              </div>
              <div>
                <p className="text-base font-semibold text-white mb-1">Chacun confirme sa présence</p>
                <p className="text-sm text-slate-400">Les participants découvrent les conditions et confirment avec une garantie réciproque.</p>
              </div>
            </div>
            <div className="flex gap-4 sm:gap-6 items-start">
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

      {/* ── Promesse (compact on mobile) ── */}
      <section className="py-10 sm:py-20 px-4 sm:px-6 border-t border-white/5" data-testid="promise-section">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-xl sm:text-2xl md:text-3xl font-bold tracking-tight text-center mb-8 sm:mb-16">Votre temps n'est plus jamais perdu.</h2>
          <div className="grid sm:grid-cols-2 gap-4 sm:gap-6">
            <div className="p-5 sm:p-8 rounded-2xl bg-white/[0.03] border border-white/5">
              <CheckCircle className="w-5 h-5 text-emerald-400 mb-3 sm:mb-5" />
              <p className="text-lg font-semibold text-white mb-2">Engagement tenu</p>
              <p className="text-sm text-slate-400 leading-relaxed">
                Votre temps est respecté. La garantie est libérée.
              </p>
            </div>
            <div className="p-5 sm:p-8 rounded-2xl bg-white/[0.03] border border-white/5">
              <Heart className="w-5 h-5 text-rose-400 mb-3 sm:mb-5" />
              <p className="text-lg font-semibold text-white mb-2">Engagement non tenu</p>
              <p className="text-sm text-slate-400 leading-relaxed">
                Votre perte de temps est compensée et devient même un geste solidaire.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Cas d'usage ── */}
      <section className="py-10 sm:py-20 px-4 sm:px-6 border-t border-white/5" data-testid="usecases-section">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight mb-4">Pour tous ceux dont le temps compte</h2>
          <p className="text-sm text-slate-400 mb-8 sm:mb-12">Coachs, consultants, thérapeutes, avocats, recruteurs, freelances...</p>
          <div className="grid grid-cols-3 gap-2 sm:gap-4">
            <div className="p-4 sm:p-6 rounded-xl bg-white/[0.03] border border-white/5">
              <Users className="w-4 h-4 text-slate-500 mb-2 sm:mb-3" />
              <p className="text-xs sm:text-sm font-medium text-white">Consultants</p>
              <p className="text-[10px] sm:text-xs text-slate-500 mt-1">Fini les créneaux bloqués pour rien</p>
            </div>
            <div className="p-4 sm:p-6 rounded-xl bg-white/[0.03] border border-white/5">
              <Clock className="w-4 h-4 text-slate-500 mb-2 sm:mb-3" />
              <p className="text-xs sm:text-sm font-medium text-white">Coachs</p>
              <p className="text-[10px] sm:text-xs text-slate-500 mt-1">Chaque session est un vrai engagement</p>
            </div>
            <div className="p-4 sm:p-6 rounded-xl bg-white/[0.03] border border-white/5">
              <Zap className="w-4 h-4 text-slate-500 mb-2 sm:mb-3" />
              <p className="text-xs sm:text-sm font-medium text-white">Professions libérales</p>
              <p className="text-[10px] sm:text-xs text-slate-500 mt-1">Votre temps retrouve sa juste valeur</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Phrase finale ── */}
      <section className="py-10 sm:py-16 px-4 sm:px-6 border-t border-white/5" data-testid="closing-section">
        <div className="max-w-2xl mx-auto text-center">
          <p className="text-xl sm:text-2xl md:text-3xl font-bold tracking-tight text-white mb-4">
            Chaque occasion perdue devient une possibilité de faire une bonne action.
          </p>
          <p className="text-sm text-slate-500">
            Votre temps est garanti. Faites en profiter qui vous voulez.
          </p>
        </div>
      </section>

      {/* ── Preuve sociale / Compteur (validation finale) ── */}
      {impactCents > 0 && (
        <section className="py-10 sm:py-20 px-4 sm:px-6 border-t border-white/5" data-testid="proof-section">
          <div className="max-w-3xl mx-auto text-center">
            <Heart className="w-5 h-5 text-rose-400 mx-auto mb-4 sm:mb-6" />
            <p className="text-4xl sm:text-5xl font-bold tracking-tight text-white mb-3" data-testid="proof-amount">
              {impactFormatted}
            </p>
            <p className="text-sm text-slate-400">
              reversés à des associations grâce aux gestes solidaires sur NLYT.
            </p>
            <Link to="/impact" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-white mt-4 sm:mt-6 transition-colors">
              Voir le détail <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </section>
      )}

      {/* ── CTA Final ── */}
      <section className="py-10 sm:py-24 px-4 sm:px-6 border-t border-white/5" data-testid="cta-section">
        <div className="max-w-2xl mx-auto text-center">
          <Link to="/signup" className="block sm:inline-block">
            <Button size="lg" className="bg-white text-[#0A0A0B] hover:bg-slate-200 text-sm sm:text-base px-6 sm:px-8 h-12 sm:h-13 font-semibold w-full sm:w-auto" data-testid="footer-cta-btn">
              Créer mon premier engagement solidaire <ArrowRight className="ml-2 w-4 h-4" />
            </Button>
          </Link>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-white/5 py-8 sm:py-10 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center sm:justify-between gap-2 text-center sm:text-left">
          <p className="text-xs text-slate-600">© 2026 NLYT — Never Lose Your Time.</p>
          <p className="text-xs text-slate-600">Votre temps est compté. Ne le gaspillez pas.</p>
        </div>
      </footer>
    </div>
  );
}
