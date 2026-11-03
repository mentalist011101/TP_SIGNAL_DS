import PagePlaceholder from '../components/PagePlaceholder.tsx'

export default function ModelsPage() {
  return (
    <PagePlaceholder
      title="Modèles"
      description="Fiche de chaque modèle : métriques, matrice de confusion, calibration."
      requirements={['EF-16']}
    />
  )
}
