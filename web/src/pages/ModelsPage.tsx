import { describeApiError, useModels } from '../api/client.ts'
import FamilyComparison from '../components/models/FamilyComparison.tsx'
import ModelTable from '../components/models/ModelTable.tsx'

// Page Modèles (EF-16) : les modèles du registre (configs/registry.yaml, S1), lus par
// GET /api/v1/models, avec leurs scores de test, leur calibration et leurs poids publiés, puis
// la comparaison des familles A et B tâche par tâche.
export default function ModelsPage() {
  const query = useModels()

  let content = <p className="text-sm text-ink-soft">Chargement des modèles…</p>
  if (query.error !== null) {
    content = <p className="text-sm text-danger">{describeApiError(query.error)}</p>
  }
  if (query.data !== undefined) {
    content = (
      <>
        <section className="space-y-3">
          <h2 className="text-base font-semibold">Registre</h2>
          <ModelTable models={query.data} />
          <p className="text-xs text-ink-soft">
            F1 macro et accuracy de test : ESC-50, moyenne des 5 tours (P3) ; émotions, moyenne des
            3 graines sur le test de CREMA-D et RAVDESS (P1). T : température de la calibration
            (ENF-06). Cliquez sur un modèle pour sa fiche : matrice de confusion, F1 par classe et
            ECE avant et après calibration.
          </p>
        </section>
        <section className="space-y-3">
          <h2 className="text-base font-semibold">Famille A contre famille B</h2>
          <FamilyComparison models={query.data} />
        </section>
      </>
    )
  }

  return (
    <section className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-5xl leading-tight">Modèles</h1>
        <p className="text-ink-soft">
          Les modèles utilisés par les analyses : leurs scores de test, leur calibration et le dépôt
          de leurs poids.
        </p>
      </div>
      {content}
    </section>
  )
}
