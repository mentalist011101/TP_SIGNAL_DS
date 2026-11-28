import CloneForm from '../components/cloning/CloneForm.tsx'
import SynthesisList from '../components/cloning/SynthesisList.tsx'

// Page Cloner (EF-18, ENF-10, C35) : faire dire un texte à une voix qui a accepté le clonage,
// avec XTTS-v2, puis réécouter, télécharger ou supprimer les extraits produits.
export default function ClonePage() {
  return (
    <section className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-5xl leading-tight">Cloner une voix</h1>
        <p className="max-w-3xl text-ink-soft">
          XTTS-v2 fait dire un texte à une voix enregistrée qui a accepté le clonage, à partir de
          ses extraits de la page Locuteurs. Chaque extrait commence par un bip et son fichier dit «
          voix synthétique » : ce n’est jamais un enregistrement réel.
        </p>
      </div>
      <div className="grid items-start gap-6 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <CloneForm />
        <SynthesisList />
      </div>
    </section>
  )
}
