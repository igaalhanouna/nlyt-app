import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, CalendarClock, Handshake, CreditCard, Gavel, ArrowRight, Heart } from 'lucide-react';
import { Button } from '../components/ui/button';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      <nav className="border-b border-border bg-white">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="text-2xl font-bold text-slate-900">NLYT</div>
          <div className="flex items-center gap-4">
            <Link to="/impact">
              <Button variant="ghost" data-testid="nav-impact-btn"><Heart className="w-4 h-4 mr-1.5 text-rose-500" />Impact</Button>
            </Link>
            <Link to="/signin">
              <Button variant="ghost" data-testid="nav-signin-btn">Connexion</Button>
            </Link>
            <Link to="/signup">
              <Button data-testid="nav-signup-btn">Créer un compte</Button>
            </Link>
          </div>
        </div>
      </nav>

      <section className="py-20 lg:py-32 px-6">
        <div className="max-w-6xl mx-auto text-center">
          <h1 className="font-serif text-5xl md:text-7xl font-bold tracking-tight leading-tight text-slate-900 mb-6">
            Fini les retards et absences non justifiés
          </h1>
          <p className="text-lg md:text-xl leading-relaxed text-slate-600 max-w-3xl mx-auto mb-12">
            NLYT transforme vos rendez-vous en engagements contraignants avec garanties financières, 
            règles de retard claires et workflows de pénalités basés sur des preuves.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link to="/signup">
              <Button size="lg" className="text-lg px-8 py-6" data-testid="hero-cta-btn">
                Commencer gratuitement <ArrowRight className="ml-2" size={20} />
              </Button>
            </Link>
            <Button size="lg" variant="outline" className="text-lg px-8 py-6" data-testid="hero-demo-btn">
              Voir la démo
            </Button>
          </div>
        </div>
      </section>

      <section className="py-20 bg-white px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl md:text-5xl font-serif font-semibold tracking-tight text-slate-900 text-center mb-16">
            Comment ça fonctionne
          </h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="p-8 border border-slate-200 rounded-lg hover:border-slate-300 transition-colors">
              <CalendarClock className="w-12 h-12 text-emerald-600 mb-4" />
              <h3 className="text-xl font-semibold text-slate-900 mb-3">1. Créez un rendez-vous</h3>
              <p className="text-slate-600 leading-relaxed">
                Définissez les règles : retard toléré, délai d'annulation, montant de la pénalité et répartition des paiements.
              </p>
            </div>
            <div className="p-8 border border-slate-200 rounded-lg hover:border-slate-300 transition-colors">
              <Handshake className="w-12 h-12 text-emerald-600 mb-4" />
              <h3 className="text-xl font-semibold text-slate-900 mb-3">2. Invitez les participants</h3>
              <p className="text-slate-600 leading-relaxed">
                Les participants reçoivent un lien, consultent le contrat et acceptent les conditions avec garantie de paiement.
              </p>
            </div>
            <div className="p-8 border border-slate-200 rounded-lg hover:border-slate-300 transition-colors">
              <ShieldCheck className="w-12 h-12 text-emerald-600 mb-4" />
              <h3 className="text-xl font-semibold text-slate-900 mb-3">3. Engagement automatique</h3>
              <p className="text-slate-600 leading-relaxed">
                NLYT collecte les preuves de présence et applique les pénalités selon les règles définies. Contestations possibles.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-20 px-6 bg-slate-900 text-white">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl md:text-5xl font-serif font-semibold mb-6">
            Prêt à éliminer les absences ?
          </h2>
          <p className="text-lg text-slate-300 mb-8">
            Rejoignez les professionnels qui valorisent leur temps et celui de leurs clients.
          </p>
          <Link to="/signup">
            <Button size="lg" variant="secondary" className="text-lg px-8 py-6" data-testid="footer-cta-btn">
              Créer mon compte gratuitement
            </Button>
          </Link>
        </div>
      </section>

      <footer className="bg-white border-t border-border py-12 px-6">
        <div className="max-w-6xl mx-auto text-center text-slate-600">
          <p>© 2026 NLYT. Tous droits réservés.</p>
        </div>
      </footer>
    </div>
  );
}