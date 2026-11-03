import PagePlaceholder from '../components/PagePlaceholder.tsx'

export default function ComparePage() {
  return (
    <PagePlaceholder
      title="Comparer les modèles"
      description="Un même fichier passé dans plusieurs modèles, côte à côte : prédictions, probabilités, latence."
      requirements={['EF-15']}
    />
  )
}
