import PagePlaceholder from '../components/PagePlaceholder.tsx'

export default function AnalyzePage() {
  return (
    <PagePlaceholder
      title="Analyser un audio"
      description="Importez un fichier ou enregistrez depuis le micro, choisissez les tâches et le profil, puis lancez l'analyse."
      requirements={['EF-01', 'EF-02', 'EF-07']}
    />
  )
}
