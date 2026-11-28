import { Link } from 'react-router-dom'
import EnrollForm from '../components/speakers/EnrollForm.tsx'
import SpeakerList from '../components/speakers/SpeakerList.tsx'

// Page Locuteurs (EF-11, C15) : enregistrer une voix avec consentement, voir et supprimer les
// voix enregistrées. Une analyse qui demande la tâche Locuteur compare chaque morceau de parole
// à ces voix : le nom s'il est assez proche (seuil de C15), « Inconnu » sinon.
export default function SpeakersPage() {
  return (
    <section className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-5xl leading-tight">Locuteurs</h1>
        <p className="max-w-3xl text-ink-soft">
          Enregistrez la voix d’une personne, avec son accord : EchoLens la reconnaîtra ensuite dans
          les analyses qui demandent la tâche Locuteur. Une voix trop éloignée de toutes celles
          enregistrées est déclarée « Inconnu », avec le seuil mesuré sur OpenSLR 57 (C15).
        </p>
        <p className="text-sm">
          <Link to="/cloner" className="font-semibold text-accent-ink hover:underline">
            Cloner une voix consentante
          </Link>
        </p>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <EnrollForm />
        <SpeakerList />
      </div>
    </section>
  )
}
