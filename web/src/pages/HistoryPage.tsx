import PagePlaceholder from '../components/PagePlaceholder.tsx'

export default function HistoryPage() {
  return (
    <PagePlaceholder
      title="Historique"
      description="Toutes les analyses passées, filtrables, réouvrables et exportables en JSON, CSV ou PDF."
      requirements={['EF-08', 'EF-09']}
    />
  )
}
