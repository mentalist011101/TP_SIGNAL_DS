import { Link } from 'react-router-dom'
import Brand from '../components/Brand.tsx'
import ApiShowcase from '../components/home/ApiShowcase.tsx'
import Limits from '../components/home/Limits.tsx'
import Pipeline from '../components/home/Pipeline.tsx'
import RealExample from '../components/home/RealExample.tsx'
import Results from '../components/home/Results.tsx'
import Reveal from '../components/home/Reveal.tsx'
import TeamBricks from '../components/home/TeamBricks.tsx'
import ToolsBento from '../components/home/ToolsBento.tsx'
import TrustSection from '../components/home/TrustSection.tsx'
import WaveRibbon from '../components/WaveRibbon.tsx'
import { ArrowRightIcon } from '../components/icons.tsx'
import ThemeToggle from '../components/ThemeToggle.tsx'

const PRIMARY_BUTTON_CLASSES =
  'inline-flex items-center gap-2 rounded-btn bg-accent px-7 py-3.5 font-semibold text-on-accent transition-colors duration-200 ease-out-soft hover:bg-accent-deep'
const SECONDARY_BUTTON_CLASSES =
  'inline-flex items-center rounded-btn border border-rule-strong px-7 py-3.5 font-medium text-ink transition-colors duration-200 ease-out-soft hover:bg-paper-alt'
const CONTAINER_CLASSES = 'mx-auto max-w-6xl px-6'
const NAV_LINK_CLASSES = 'hidden text-ink-soft transition-colors hover:text-ink md:inline'

// Lien de bas de page qui mène vers l'application (routage React).
interface FooterLink {
  label: string
  to: string
}

const PRODUCT_LINKS: FooterLink[] = [
  { label: 'Nouvelle analyse', to: '/analyser' },
  { label: 'Historique', to: '/historique' },
]

// Menu du site public : logo, ancres des sections, thème, puis l'entrée dans l'application.
function HomeHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-rule bg-paper/80 backdrop-blur">
      <nav
        className={`${CONTAINER_CLASSES} flex items-center justify-between gap-4 py-4`}
        aria-label="Menu du site"
      >
        <Brand />
        <div className="flex items-center gap-4 text-sm sm:gap-7">
          <a href="#exemple" className={NAV_LINK_CLASSES}>
            Exemple
          </a>
          <a href="#resultats" className={NAV_LINK_CLASSES}>
            Résultats
          </a>
          <a href="#outils" className={NAV_LINK_CLASSES}>
            Outils
          </a>
          <a href="#fonctionnement" className={NAV_LINK_CLASSES}>
            Fonctionnement
          </a>
          <a href="/docs" className={NAV_LINK_CLASSES}>
            API
          </a>
          <ThemeToggle />
          <Link
            to="/analyser"
            className="rounded-btn bg-accent px-4 py-2 font-semibold text-on-accent transition-colors hover:bg-accent-deep"
          >
            <span className="sm:hidden">Ouvrir</span>
            <span className="hidden sm:inline">Ouvrir l’application</span>
          </Link>
        </div>
      </nav>
    </header>
  )
}

// Ouverture : promesse en très grand, sous-titre, appels à l'action, puis le ruban d'ondes.
function Hero() {
  return (
    <section className="pt-20 sm:pt-28">
      <Reveal className={`${CONTAINER_CLASSES} flex flex-col items-center gap-8 text-center`}>
        <span className="label-mono inline-flex items-center gap-2 rounded-btn border border-rule-strong bg-card px-3.5 py-1.5 text-ink-soft">
          <span className="h-1.5 w-1.5 rounded-full bg-brand motion-safe:animate-pulse" />
          Analyse audio par IA
        </span>
        <h1 className="max-w-5xl text-6xl leading-[0.95] sm:text-8xl lg:text-[8.5rem]">
          Écoutez ce que vos audios <em className="text-brand">racontent</em>.
        </h1>
        <p className="max-w-2xl text-lg leading-relaxed text-ink-soft sm:text-xl">
          Déposez un enregistrement : EchoLens repère les sons, lit les émotions dans la voix, et
          vous montre chaque étape de son analyse. Chaque chiffre dit quel modèle l’a produit.
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          <Link to="/analyser" className={PRIMARY_BUTTON_CLASSES}>
            Analyser un audio
            <ArrowRightIcon />
          </Link>
          <a href="#fonctionnement" className={SECONDARY_BUTTON_CLASSES}>
            Voir comment ça marche
          </a>
        </div>
        <p className="font-mono text-xs text-ink-faint">
          wav, mp3, flac, ogg, webm, m4a · jusqu’à 5 minutes · fichier ou micro
        </p>
      </Reveal>
      <div className="mt-10">
        <WaveRibbon />
      </div>
    </section>
  )
}

// Vrai exemple figé, en grand, juste après l'ouverture.
function DemoSection() {
  return (
    <section id="exemple" className={`${CONTAINER_CLASSES} pb-8`} aria-label="Exemple réel">
      <Reveal>
        <RealExample />
      </Reveal>
    </section>
  )
}

// Dernier appel à l'action, dans un grand cadre.
function FinalCta() {
  return (
    <section className={`${CONTAINER_CLASSES} py-24`}>
      <Reveal>
        <div className="dot-grid flex flex-col items-center gap-8 rounded-[28px] border border-rule-strong bg-card px-6 py-20 text-center">
          <h2 className="max-w-3xl font-display text-5xl leading-tight sm:text-7xl">
            Prêt à écouter <em className="text-brand">vraiment</em> vos audios ?
          </h2>
          <p className="max-w-xl text-lg text-ink-soft">
            Un fichier suffit. Le résultat s’ouvre tout seul dès qu’il est prêt, et reste dans votre
            historique.
          </p>
          <Link to="/analyser" className={PRIMARY_BUTTON_CLASSES}>
            Lancer ma première analyse
            <ArrowRightIcon />
          </Link>
        </div>
      </Reveal>
    </section>
  )
}

// Pied de page en colonnes : produit, ressources, projet.
function HomeFooter() {
  return (
    <footer className="border-t border-rule">
      <div className={`${CONTAINER_CLASSES} grid gap-10 py-14 sm:grid-cols-2 lg:grid-cols-4`}>
        <div className="space-y-3">
          <Brand />
          <p className="max-w-xs text-sm text-ink-soft">
            Analyse audio : événements sonores, émotions, transcription, et bientôt locuteurs.
          </p>
        </div>
        <div className="space-y-3 text-sm">
          <p className="label-mono text-ink-faint">Produit</p>
          {PRODUCT_LINKS.map((link) => (
            <Link key={link.to} to={link.to} className="block text-ink-soft hover:text-ink">
              {link.label}
            </Link>
          ))}
        </div>
        <div className="space-y-3 text-sm">
          <p className="label-mono text-ink-faint">Ressources</p>
          <a href="/docs" className="block text-ink-soft hover:text-ink">
            Documentation de l’API
          </a>
          <a
            href="https://github.com/mentalist011101/TP_SIGNAL_DS"
            className="block text-ink-soft hover:text-ink"
          >
            Code source
          </a>
        </div>
        <div className="space-y-3 text-sm">
          <p className="label-mono text-ink-faint">Projet</p>
          <p className="text-ink-soft">INF50101 · Traitement multimédia des données</p>
          <p className="text-ink-soft">ENSPY, M2 Data Science</p>
        </div>
      </div>
      <p
        className={`${CONTAINER_CLASSES} border-t border-rule py-6 font-mono text-xs text-ink-faint`}
      >
        EchoLens · 2026
      </p>
    </footer>
  )
}

// Page d'accueil publique : ouverture, vrai exemple figé, chaîne de traitement, outils,
// résultats, confiance, limites, équipe et briques, API, puis le dernier appel à l'action.
export default function HomePage() {
  return (
    <div className="min-h-screen bg-paper text-ink">
      <HomeHeader />
      <main className="dot-grid">
        <Hero />
        <DemoSection />
        <Pipeline />
        <ToolsBento />
        <Results />
        <TrustSection />
        <Limits />
        <TeamBricks />
        <ApiShowcase />
        <FinalCta />
      </main>
      <HomeFooter />
    </div>
  )
}
